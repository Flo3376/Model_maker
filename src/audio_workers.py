"""
Workers audio pour NovaQA
Gère l'enregistrement, la lecture et le monitoring audio
"""

import os
import math
import queue
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
import pygame
from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal

from .config import (
    DBFS_FLOOR, UPDATE_INTERVAL_MS, BLOCKSIZE, DTYPE,
    VU_METER_THRESHOLD, SPEECH_START_THRESHOLD_SEC, SPEECH_SILENCE_TIMEOUT_MS,
    SPEECH_TOLERANCE_MS, RESPONSE_SAMPLE_RATE, RESPONSE_FOLDER, AMBIANCE_VOLUME,
    IMMEDIATE_RECORDING, NOISE_FLOOR_ADAPTATION, NOISE_FLOOR_LEARNING_SEC,
    DYNAMIC_SILENCE_DETECTION, MIN_SILENCE_DURATION_MS
)
from .environment_utils import environment_manager


class AudioWorker(QObject):
    """Worker audio simplifié"""
    level = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.device_index = None
        self._stream = None
        self._q = queue.Queue(maxsize=8)
        self._timer = QTimer()
        self._timer.timeout.connect(self._process_queue)
        self._timer.start(UPDATE_INTERVAL_MS)

    def _audio_callback(self, indata, frames, time, status):
        try:
            data = np.mean(indata.astype(np.float32), axis=1)
            try:
                self._q.put_nowait(data.copy())
            except queue.Full:
                pass
        except Exception as e:
            print(f"Erreur callback: {e}")

    def _process_queue(self):
        try:
            if self._q.empty():
                return
            buf = []
            while not self._q.empty():
                try:
                    buf.append(self._q.get_nowait())
                except queue.Empty:
                    break
            if not buf:
                return
            x = np.concatenate(buf)
            rms = float(np.sqrt(np.mean(np.square(x), dtype=np.float64)))
            if rms <= 1e-9 or not np.isfinite(rms):
                dbfs = -math.inf
            else:
                dbfs = 20.0 * math.log10(rms)
                dbfs = max(DBFS_FLOOR, min(0.0, dbfs))
            self.level.emit(dbfs)
        except Exception as e:
            print(f"Erreur process_queue: {e}")

    def is_running(self) -> bool:
        return self._stream is not None

    def start(self):
        try:
            self.stop()
            if self.device_index is None:
                return
            dev_info = sd.query_devices(self.device_index)
            sr = dev_info.get('default_samplerate', 48000) or 48000
            ch = min(1, max(1, dev_info.get('max_input_channels', 1)))
            self._stream = sd.InputStream(
                device=self.device_index,
                channels=ch,
                samplerate=sr,
                blocksize=BLOCKSIZE,
                dtype=DTYPE,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as e:
            print(f"Erreur start stream: {e}")

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            finally:
                self._stream = None


class ResponseRecorder(QThread):
    """Enregistreur de réponse avec détection automatique de début/fin de parole"""
    recording_started = pyqtSignal()
    recording_finished = pyqtSignal(str)  # Émet le chemin du fichier enregistré
    speech_detected = pyqtSignal()
    silence_detected = pyqtSignal()
    
    def __init__(self, question_number, device_index=None):
        super().__init__()
        self.question_number = question_number
        self.device_index = device_index
        self.should_stop = False
        
        # État de l'enregistrement
        self.recording_active = IMMEDIATE_RECORDING  # Démarrer immédiatement si configuré
        self.speech_started = IMMEDIATE_RECORDING    # Idem
        self.last_activity_time = None
        self.last_silence_time = None
        self.silence_start_time = None
        self.recording_data = []
        
        # Gestion environnement bruyant
        self.noise_floor = -60.0  # Plancher de bruit initial (sera appris)
        self.noise_samples = []   # Échantillons pour apprentissage du bruit
        self.learning_phase = NOISE_FLOOR_ADAPTATION
        self.learning_start_time = None
        self.dynamic_threshold = VU_METER_THRESHOLD
        
    def run(self):
        try:
            # Préparer le fichier de sortie
            output_file = f"{RESPONSE_FOLDER}/reponse_{self.question_number:02d}.wav"
            os.makedirs(RESPONSE_FOLDER, exist_ok=True)
            
            print(f"🎤 Démarrage surveillance réponse Q{self.question_number}")
            print(f"   📁 Fichier: {output_file}")
            if IMMEDIATE_RECORDING:
                print(f"   🚀 ENREGISTREMENT IMMÉDIAT activé")
                print(f"   🤫 Timeout silence: {MIN_SILENCE_DURATION_MS}ms (optimisé réponses courtes)")
            else:
                print(f"   ⏱️ Seuil démarrage: {SPEECH_START_THRESHOLD_SEC}s d'activité")
                print(f"   🤫 Timeout silence: {SPEECH_SILENCE_TIMEOUT_MS}ms")
            
            if NOISE_FLOOR_ADAPTATION:
                print(f"   🔇 Adaptation au bruit ambiant: {NOISE_FLOOR_LEARNING_SEC}s d'apprentissage")
            
            # Configuration audio optimisée pour qualité
            if self.device_index is None:
                return
                
            # Forcer 44.1kHz pour éviter les problèmes de resampling
            samplerate = RESPONSE_SAMPLE_RATE  # Toujours 44100, pas de device auto
            channels = 1  # Mono pour les réponses
            
            print(f"   🎚️ Audio config: {samplerate}Hz, {channels}ch, blocksize={BLOCKSIZE}")
            
            def audio_callback(indata, frames, time_info, status):
                if self.should_stop:
                    raise sd.CallbackStop()
                
                # Vérifier les erreurs de status
                if status:
                    print(f"⚠️ Audio callback status: {status}")
                
                # Utiliser directement float32 sans conversion multiple
                audio_data = indata.astype(np.float32)
                
                # Calculer le niveau audio (RMS puis dBFS) de manière optimisée
                rms = np.sqrt(np.mean(audio_data ** 2))
                if rms > 1e-10:  # Éviter log(0)
                    dbfs = 20.0 * np.log10(rms)
                    dbfs = np.clip(dbfs, -80.0, 0.0)  # Plus efficace que max/min
                else:
                    dbfs = -80.0
                
                self._process_audio_level(dbfs, audio_data, frames)
            
            # Démarrer le stream d'enregistrement avec paramètres optimisés
            with sd.InputStream(
                device=self.device_index,
                channels=channels,
                samplerate=samplerate,
                callback=audio_callback,
                blocksize=BLOCKSIZE,
                dtype=DTYPE,
                latency='low',        # Latence faible pour réduire les hachures
                extra_settings=sd.WasapiSettings(exclusive=False)  # Mode partagé plus stable
            ):
                if IMMEDIATE_RECORDING:
                    print("🔴 ENREGISTREMENT DÉMARRÉ IMMÉDIATEMENT")
                    print("🎤 Parlez maintenant, la détection de fin est automatique")
                    self.recording_started.emit()
                    self.speech_detected.emit()
                else:
                    print("🎤 Stream d'enregistrement actif, en attente de parole...")
                
                # Attendre jusqu'à arrêt
                while not self.should_stop:
                    self.msleep(50)
            
            # Sauvegarder l'enregistrement si on a des données
            if self.recording_data:
                self._save_recording(output_file, samplerate)
                
        except Exception as e:
            print(f"❌ Erreur enregistrement réponse: {e}")
    
    def _process_audio_level(self, dbfs, indata, frames):
        """Traite le niveau audio pour détecter début/fin de parole avec gestion du bruit"""
        current_time = time.time()
        
        # Phase d'apprentissage du bruit de fond
        if self.learning_phase and NOISE_FLOOR_ADAPTATION:
            if self.learning_start_time is None:
                self.learning_start_time = current_time
                print(f"🔇 Début apprentissage bruit de fond...")
            
            learning_duration = current_time - self.learning_start_time
            if learning_duration < NOISE_FLOOR_LEARNING_SEC:
                # Collecter échantillons de bruit
                self.noise_samples.append(dbfs)
                return  # Ne pas traiter pendant l'apprentissage
            else:
                # Finir apprentissage
                if self.noise_samples:
                    self.noise_floor = np.percentile(self.noise_samples, 75)  # 75ème percentile
                    
                    # Auto-configuration selon l'environnement détecté
                    env_type = environment_manager.auto_configure(self.noise_samples)
                    self.dynamic_threshold = environment_manager.get_adapted_threshold(self.noise_floor)
                    
                    print(f"✅ Bruit de fond appris: {self.noise_floor:.1f} dBFS")
                    print(f"📊 Nouveau seuil adaptatif: {self.dynamic_threshold:.1f} dBFS")
                    print(f"🎯 Environnement détecté: {env_type}")
                else:
                    print("⚠️ Pas d'échantillons de bruit, utilisation seuil par défaut")
                    self.dynamic_threshold = VU_METER_THRESHOLD
                
                self.learning_phase = False
                self.noise_samples = []  # Libérer mémoire
        
        # Utiliser le seuil adaptatif ou fixe
        threshold = self.dynamic_threshold if DYNAMIC_SILENCE_DETECTION else VU_METER_THRESHOLD
        is_active = dbfs > threshold
        
        # Si enregistrement immédiat, toujours enregistrer (optimisé)
        if IMMEDIATE_RECORDING and self.recording_active:
            # Éviter copy() inutile si on a déjà les bonnes données
            self.recording_data.append(indata if indata.dtype == np.float32 else indata.astype(np.float32))
        
        if is_active:
            self.last_silence_time = None
            self.silence_start_time = None
            
            # Mode détection classique (si pas d'enregistrement immédiat)
            if not IMMEDIATE_RECORDING:
                if self.last_activity_time is None:
                    self.last_activity_time = current_time
                    print(f"🎤 Début activité détectée ({dbfs:.1f} dBFS, seuil: {threshold:.1f})")
                
                if not self.speech_started:
                    activity_duration = current_time - self.last_activity_time
                    if activity_duration >= SPEECH_START_THRESHOLD_SEC:
                        self._start_recording()
                
                if self.recording_active:
                    # Optimiser la copie des données
                    self.recording_data.append(indata if indata.dtype == np.float32 else indata.astype(np.float32))
            
        else:
            # Silence détecté
            if self.last_silence_time is None:
                self.last_silence_time = current_time
            
            if self.recording_active:
                # Continuer d'enregistrer le silence pour un résultat naturel (optimisé)
                self.recording_data.append(indata if indata.dtype == np.float32 else indata.astype(np.float32))
                
                # Mode automatique normal - détection de fin par silence
                silence_timeout = environment_manager.get_silence_duration() if IMMEDIATE_RECORDING else SPEECH_SILENCE_TIMEOUT_MS
                
                if self.silence_start_time is None:
                    self.silence_start_time = current_time
                    print(f"🤫 Silence détecté, timeout de {silence_timeout}ms activé")
                else:
                    silence_duration = (current_time - self.silence_start_time) * 1000
                    if silence_duration >= silence_timeout:
                        self._on_silence_timeout()
            else:
                # Pas encore en enregistrement (mode classique uniquement)
                if not IMMEDIATE_RECORDING and self.last_activity_time is not None:
                    silence_duration = current_time - self.last_silence_time
                    if silence_duration > (SPEECH_TOLERANCE_MS / 1000.0):
                        print(f"🔄 Reset timer activité après {silence_duration*1000:.0f}ms de silence")
                        self.last_activity_time = None
    
    def _start_recording(self):
        """Démarre l'enregistrement effectif"""
        if not self.speech_started:
            self.speech_started = True
            self.recording_active = True
            self.recording_data = []
            print("=" * 50)
            print(f"🔴 ENREGISTREMENT DÉMARRÉ !")
            print(f"🎤 Parlez clairement, silence de {SPEECH_SILENCE_TIMEOUT_MS}ms pour arrêter")
            print("=" * 50)
            self.recording_started.emit()
            self.speech_detected.emit()
    
    def _on_silence_timeout(self):
        """Appelé quand le timeout de silence est atteint"""
        if self.recording_active:
            silence_timeout = environment_manager.get_silence_duration() if IMMEDIATE_RECORDING else SPEECH_SILENCE_TIMEOUT_MS
            print("=" * 50)
            print(f"🔇 ARRÊT AUTOMATIQUE (silence de {silence_timeout}ms)")
            print("💾 Sauvegarde en cours...")
            print("=" * 50)
            self.recording_active = False
            self.silence_detected.emit()
            self.should_stop = True
    
    def _save_recording(self, output_file, samplerate):
        """Sauvegarde l'enregistrement dans un fichier WAV"""
        try:
            if not self.recording_data:
                print("⚠️ Aucune donnée à sauvegarder")
                return
                
            # Concaténer toutes les données
            audio_data = np.concatenate(self.recording_data, axis=0)
            
            # Sauvegarder avec soundfile
            sf.write(output_file, audio_data, samplerate)
            
            duration = len(audio_data) / samplerate
            print(f"💾 Réponse sauvegardée: {output_file}")
            print(f"   📊 Durée: {duration:.2f}s, {len(audio_data)} échantillons")
            
            self.recording_finished.emit(output_file)
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde: {e}")
    
    def stop_recording(self):
        """Arrête l'enregistrement immédiatement"""
        self.should_stop = True


class AudioPlayer(QThread):
    """Thread pour audio (questions/réponses) - Utilise sounddevice/soundfile"""
    finished = pyqtSignal()
    
    def __init__(self, audio_file):
        super().__init__()
        self.audio_file = audio_file
        self.should_stop = False
        self.stream = None
        
    def run(self):
        try:
            # Utiliser soundfile pour lire le fichier et sounddevice pour jouer
            # Complètement indépendant de pygame
            data, samplerate = sf.read(self.audio_file, dtype='float32')
            
            # Si mono, convertir en stéréo
            if len(data.shape) == 1:
                data = np.column_stack((data, data))
            
            self.current_frame = 0
            total_frames = len(data)
            
            def audio_callback(outdata, frames, time_info, status):
                if self.should_stop:
                    raise sd.CallbackStop()
                
                start = self.current_frame
                end = min(start + frames, total_frames)
                
                if start >= total_frames:
                    # Fin du fichier
                    outdata[:] = 0
                    raise sd.CallbackStop()
                
                # Copier les données audio
                chunk_size = end - start
                outdata[:chunk_size] = data[start:end]
                
                # Si on n'a pas assez de données, remplir de zéros
                if chunk_size < frames:
                    outdata[chunk_size:] = 0
                
                self.current_frame = end
            
            # Démarrer le stream sounddevice
            with sd.OutputStream(
                samplerate=samplerate, 
                channels=data.shape[1],
                callback=audio_callback,
                blocksize=1024,
                latency='low'
            ) as self.stream:
                print(f"🎤 Lecture sounddevice: {os.path.basename(self.audio_file)}")
                
                # Attendre que le stream se termine
                while self.stream.active and not self.should_stop:
                    sd.sleep(50)  # Dormir 50ms
                    
        except Exception as e:
            print(f"❌ Erreur lecture sounddevice {self.audio_file}: {e}")
        finally:
            self.finished.emit()
    
    def stop(self):
        self.should_stop = True
        if hasattr(self, 'stream') and self.stream:
            try:
                self.stream.abort()
            except:
                pass


class AmbiancePlayer(QThread):
    """Thread dédié EXCLUSIVEMENT pour la musique d'ambiance"""
    
    def __init__(self, audio_file, volume=AMBIANCE_VOLUME):
        super().__init__()
        self.audio_file = audio_file
        self.volume = volume
        self.should_stop = False
        
    def run(self):
        try:
            # pygame.mixer.music N'EST PLUS EN CONFLIT car sounddevice gère le reste
            pygame.mixer.music.load(self.audio_file)
            pygame.mixer.music.set_volume(self.volume)
            pygame.mixer.music.play(-1)  # Boucle infinie
            print(f"🎵 Ambiance pygame.music démarrée: {os.path.basename(self.audio_file)}")
            
            # Surveillance simple
            while not self.should_stop:
                if not pygame.mixer.music.get_busy():
                    print("🎵 Redémarrage ambiance...")
                    pygame.mixer.music.play(-1)
                pygame.time.wait(500)  # Vérifier toutes les 500ms
                
        except Exception as e:
            print(f"❌ Erreur ambiance: {e}")
    
    def stop(self):
        self.should_stop = True
        try:
            pygame.mixer.music.stop()
            print("🎵 Ambiance arrêtée")
        except:
            pass