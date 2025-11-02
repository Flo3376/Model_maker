import sys
import os
import pygame
import math
import queue
import json
from typing import List, Tuple, Optional



import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt6.QtWidgets import (QApplication, QMainWindow, QDialog, QVBoxLayout, 
                            QLabel, QPushButton, QWidget, QHBoxLayout, QComboBox,
                            QGroupBox, QTextEdit)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QPalette, QColor, QPainter, QPen, QFont

DBFS_FLOOR = -60.0
UPDATE_INTERVAL_MS = 50
BLOCKSIZE = 1024
DTYPE = 'float32'

# === PARAMÈTRES DE VALIDATION MICROPHONE ===
VU_METER_THRESHOLD = -40.0        # Seuil dBFS pour détecter l'activité (essaie -35, -30)
VU_METER_VALIDATION_TIME = 1.5    # Temps requis d'activité continue (secondes)
SILENCE_DEBOUNCE_MS = 1000        # Délai avant reset du timer (millisecondes) - essaie 1000, 1500

# === PARAMÈTRES D'ENREGISTREMENT RÉPONSE ===
SPEECH_START_THRESHOLD_SEC = 0.3  # Secondes d'activité VU pour démarrer l'enregistrement (encore réduit)
SPEECH_SILENCE_TIMEOUT_MS = 1500   # ms de silence pour considérer la fin de parole
SPEECH_TOLERANCE_MS = 500         # ms de tolérance pour micro-pauses (nouveau)
RESPONSE_SAMPLE_RATE = 44100      # Fréquence d'échantillonnage pour l'enregistrement
RESPONSE_FOLDER = "sound_response" # Dossier pour les réponses enregistrées
DELAY_BEFORE_REPLY_MS = 500      # Délai avant de lancer la réponse bateau (ms)
# ===========================================

class QuestionManager:
    """Gestionnaire des questions et du flow d'interview"""
    
    def __init__(self, start_index=0):
        self.questions = []
        self.current_index = start_index  # Démarrer à l'index spécifié
        self.load_questions()
        print(f"📋 QuestionManager initialisé à l'index {start_index}")
    
    def load_questions(self):
        """Charge les questions depuis le fichier JSON"""
        try:
            with open('question.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.questions = data
                print(f"📋 {len(self.questions)} questions chargées")
                
                # Plus besoin de detect_and_resume ici, c'est fait avant Qt
                
        except Exception as e:
            print(f"❌ Erreur chargement questions: {e}")
    
    def get_current_question(self):
        """Retourne la question actuelle"""
        if 0 <= self.current_index < len(self.questions):
            question_data = self.questions[self.current_index]
            question_key = list(question_data.keys())[0]
            return question_data[question_key]
        return None
    
    def get_current_question_number(self):
        """Retourne le numéro de la question actuelle"""
        return self.current_index + 1
    
    def get_total_questions(self):
        """Retourne le nombre total de questions"""
        return len(self.questions)
    
    def next_question(self):
        """Passe à la question suivante"""
        if self.current_index < len(self.questions) - 1:
            self.current_index += 1
            return True
        return False
    
    def has_next_question(self):
        """Vérifie s'il y a une question suivante"""
        return self.current_index < len(self.questions) - 1
    
    def reset(self):
        """Remet le compteur à zéro"""
        self.current_index = 0

def list_input_devices() -> List[Tuple[int, str]]:
    """Return WASAPI devices only"""
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        items = []
        
        for idx, dev in enumerate(devices):
            if dev.get('max_input_channels', 0) > 0:
                host_name = hostapis[dev['hostapi']]['name']
                if host_name == 'Windows WASAPI':
                    device_name = dev['name']
                    label = f"{device_name} (in:{dev['max_input_channels']})"
                    items.append((idx, label))
        
        items.sort(key=lambda x: x[1])
        return items
    except Exception as e:
        print(f"Erreur liste devices: {e}")
        return []

class AudioMeterWidget(QWidget):
    """Vue-mètre horizontal"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(35)
        self.setMaximumHeight(35)
        self.setMinimumWidth(300)
        self._dbfs = -math.inf

    def set_dbfs(self, db: float):
        self._dbfs = db
        self.update()

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            rect = self.rect()
            
            # Background
            p.fillRect(rect, QColor(11, 15, 23))
            
            # Border
            pen = QPen(QColor(0, 209, 255))
            pen.setWidth(2)
            p.setPen(pen)
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)

            # Meter fill
            if np.isfinite(self._dbfs):
                frac = (self._dbfs - DBFS_FLOOR) / (0.0 - DBFS_FLOOR)
                frac = float(np.clip(frac, 0.0, 1.0))
            else:
                frac = 0.0

            if frac > 0:
                fill_width = int(frac * (rect.width() - 8))
                fill_rect = rect.adjusted(4, 4, 4 + fill_width - rect.width(), -4)
                
                # Color gradient
                if self._dbfs < -30:
                    color = QColor(0, 255, 0)
                elif self._dbfs < -12:
                    ratio = (self._dbfs + 30) / 18
                    color = QColor(int(255 * ratio), 255, 0)
                else:
                    ratio = (self._dbfs + 12) / 12
                    color = QColor(255, int(255 * (1 - ratio)), 0)
                
                p.fillRect(fill_rect, color)

            # Text
            p.setPen(QPen(QColor(230, 230, 235)))
            font = p.font()
            font.setPointSize(10)
            font.setWeight(QFont.Weight.Bold)
            p.setFont(font)
            
            label = "RMS: -∞ dBFS" if not np.isfinite(self._dbfs) else f"RMS: {self._dbfs:0.1f} dBFS"
            p.drawText(rect.adjusted(8, 4, -8, -4), Qt.AlignmentFlag.AlignCenter, label)
        except Exception as e:
            print(f"Erreur paintEvent: {e}")

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
        self.recording_active = False
        self.speech_started = False
        self.last_activity_time = None
        self.last_silence_time = None  # Nouveau: pour tolérer les micro-pauses
        self.silence_start_time = None  # Pour timeout de silence sans QTimer
        self.recording_data = []
        
        # Plus de QTimer - on utilise le timing système
        
    def run(self):
        try:
            # Préparer le fichier de sortie
            output_file = f"{RESPONSE_FOLDER}/reponse_{self.question_number:02d}.wav"
            os.makedirs(RESPONSE_FOLDER, exist_ok=True)
            
            print(f"🎤 Démarrage surveillance réponse Q{self.question_number}")
            print(f"   📁 Fichier: {output_file}")
            print(f"   ⏱️ Seuil démarrage: {SPEECH_START_THRESHOLD_SEC}s d'activité")
            print(f"   🤫 Timeout silence: {SPEECH_SILENCE_TIMEOUT_MS}ms")
            
            # Configuration audio
            if self.device_index is None:
                return
                
            dev_info = sd.query_devices(self.device_index)
            samplerate = int(dev_info.get('default_samplerate', RESPONSE_SAMPLE_RATE))
            channels = 1  # Mono pour les réponses
            
            def audio_callback(indata, frames, time_info, status):
                if self.should_stop:
                    raise sd.CallbackStop()
                
                # Calculer le niveau audio (RMS puis dBFS)
                rms = np.sqrt(np.mean(indata.astype(np.float64) ** 2))
                if rms > 0:
                    dbfs = 20.0 * np.log10(rms)
                    dbfs = max(-80.0, min(0.0, dbfs))
                else:
                    dbfs = -80.0
                
                self._process_audio_level(dbfs, indata, frames)
            
            # Démarrer le stream d'enregistrement
            with sd.InputStream(
                device=self.device_index,
                channels=channels,
                samplerate=samplerate,
                callback=audio_callback,
                blocksize=BLOCKSIZE,
                dtype=DTYPE
            ):
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
        """Traite le niveau audio pour détecter début/fin de parole"""
        import time
        current_time = time.time()
        
        # Détection d'activité vocale
        is_active = dbfs > VU_METER_THRESHOLD
        
        if is_active:
            self.last_silence_time = None  # Reset du silence
            self.silence_start_time = None  # Reset du timeout de silence
            
            # Première activité détectée
            if self.last_activity_time is None:
                self.last_activity_time = current_time
                print(f"🎤 Début activité détectée ({dbfs:.1f} dBFS)")
            
            # Vérifier si on doit démarrer l'enregistrement
            if not self.speech_started:
                activity_duration = current_time - self.last_activity_time
                if activity_duration >= SPEECH_START_THRESHOLD_SEC:
                    self._start_recording()
            
            # Si on enregistre, ajouter les données
            if self.recording_active:
                self.recording_data.append(indata.copy())
                
        else:
            # Silence détecté
            if self.last_silence_time is None:
                self.last_silence_time = current_time
            
            silence_duration = current_time - self.last_silence_time
            
            if self.speech_started and self.recording_active:
                # On enregistre déjà, continuer d'enregistrer le silence
                self.recording_data.append(indata.copy())
                
                # Gérer le timeout de silence avec timing système
                if self.silence_start_time is None:
                    self.silence_start_time = current_time
                    print(f"🤫 Silence détecté, timeout de {SPEECH_SILENCE_TIMEOUT_MS}ms activé")
                else:
                    silence_timeout_duration = (current_time - self.silence_start_time) * 1000  # en ms
                    if silence_timeout_duration >= SPEECH_SILENCE_TIMEOUT_MS:
                        self._on_silence_timeout()
            else:
                # Pas encore d'enregistrement
                if self.last_activity_time is not None:
                    # Tolérer les micro-pauses (respiration, etc.)
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
            print("=" * 50)
            print(f"� ARRÊT AUTOMATIQUE (silence de {SPEECH_SILENCE_TIMEOUT_MS}ms)")
            print("💾 Sauvegarde en cours...")
            print("=" * 50)
            self.recording_active = False
            self.silence_detected.emit()
            self.should_stop = True  # Arrêter le thread
    
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
    
    def __init__(self, audio_file, volume=0.15):
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

class WarningPopup(QDialog):
    """Popup d'avertissement"""
    
    def __init__(self, parent, title, message, audio_file):
        super().__init__(parent)
        self.audio_file = audio_file
        self.audio_player = None
        self.setup_ui(title, message)
        self.play_audio()
        
    def setup_ui(self, title, message):
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        # Force la fenêtre au premier plan
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
            }
            QLabel {
                color: white;
                font-size: 12px;
                padding: 10px;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #666;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
        """)
        
        layout = QVBoxLayout()
        
        label = QLabel(message)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        skip_button = QPushButton("Skip")
        skip_button.clicked.connect(self.skip_and_close)
        layout.addWidget(skip_button)
        
        self.setLayout(layout)
        
    def play_audio(self):
        if os.path.exists(self.audio_file):
            self.audio_player = AudioPlayer(self.audio_file)
            self.audio_player.finished.connect(self.audio_finished)
            self.audio_player.start()
    
    def audio_finished(self):
        self.accept()
    
    def skip_and_close(self):
        if self.audio_player:
            self.audio_player.stop()
        self.accept()
    
    def closeEvent(self, event):
        if self.audio_player:
            self.audio_player.stop()
        event.accept()

class MainWindow(QMainWindow):
    """Fenêtre principale"""
    
    def __init__(self, resume_index=0):
        super().__init__()
        self.ambiance_player = None
        self.audio_worker = None
        
        # Initialiser le QuestionManager avec l'index de reprise
        self.question_manager = QuestionManager(resume_index)
        
        self.current_audio_player = None
        self.response_recorder = None  # Enregistreur de réponse
        self.interview_started = False
        self.microphone_active = False
        self.vu_meter_validated = False  # Une fois validé, reste vrai
        self.vu_meter_start_time = None  # Timestamp du début d'activité
        self.vu_meter_required_duration = VU_METER_VALIDATION_TIME  # Utiliser la variable globale
        self.silence_debounce_timer = None  # Timer pour le debounce de silence
        self.silence_debounce_duration = SILENCE_DEBOUNCE_MS  # Utiliser la variable globale
        print("Initialisation interface...")
        self.setup_ui()
        self.setup_audio()
        
        # Actualiser l'affichage avec l'état de reprise après création de l'interface
        self.update_resume_status()
        
        print("Interface prête, affichage des warnings...")
        # Délai pour laisser l'interface se charger
        QTimer.singleShot(100, self.show_warnings)
        
    def setup_ui(self):
        self.setWindowTitle("NovaQA")
        self.setGeometry(100, 100, 800, 600)
        
        # Force l'affichage
        self.setWindowFlag(Qt.WindowType.Window, True)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: white;
            }
            QGroupBox {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                border-radius: 8px;
                padding-top: 10px;
                font-weight: bold;
                font-size: 12px;
            }
            QGroupBox::title {
                color: #ff9f1c;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QComboBox {
                background-color: #404040;
                color: white;
                border: 1px solid #666;
                padding: 8px;
                border-radius: 4px;
                font-size: 11px;
                min-height: 20px;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #666;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
            QPushButton.start-button {
                background-color: #2d5a2d;
                border: 1px solid #4a8a4a;
            }
            QPushButton.start-button:hover {
                background-color: #3d6a3d;
            }
            QPushButton.next-button {
                background-color: #2d4a5a;
                border: 1px solid #4a7a8a;
            }
            QPushButton.next-button:hover {
                background-color: #3d5a6a;
            }
            QPushButton.end-button {
                background-color: #5a2d2d;
                border: 1px solid #8a4a4a;
            }
            QPushButton.end-button:hover {
                background-color: #6a3d3d;
            }
            QTextEdit {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
                line-height: 1.4;
            }
        """)
        
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #1e1e1e;")
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # Section micro
        device_group = QGroupBox("SÉLECTION MICROPHONE")
        device_layout = QVBoxLayout(device_group)
        
        select_layout = QHBoxLayout()
        
        label = QLabel("Périphérique:")
        label.setMaximumWidth(80)
        select_layout.addWidget(label)
        
        self.device_combo = QComboBox()
        select_layout.addWidget(self.device_combo, 1)
        
        self.refresh_btn = QPushButton("REFRESH")
        self.refresh_btn.setMaximumWidth(100)
        select_layout.addWidget(self.refresh_btn)
        
        device_layout.addLayout(select_layout)
        main_layout.addWidget(device_group)
        
        # Section vue-mètre
        meter_group = QGroupBox("VU-MÈTRE RMS dBFS")
        meter_layout = QVBoxLayout(meter_group)
        
        self.meter = AudioMeterWidget()
        meter_layout.addWidget(self.meter)
        
        self.status_label = QLabel("Sélectionnez un microphone...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meter_layout.addWidget(self.status_label)
        
        main_layout.addWidget(meter_group)
        
        # === NOUVELLE SECTION INTERVIEW ===
        interview_group = QGroupBox("INTERVIEW")
        interview_layout = QVBoxLayout(interview_group)
        
        # Bouton commencer l'interview
        self.start_interview_btn = QPushButton("COMMENCER L'INTERVIEW")
        self.start_interview_btn.setProperty("class", "start-button")
        self.start_interview_btn.setMinimumHeight(40)
        self.start_interview_btn.clicked.connect(self.start_interview)
        interview_layout.addWidget(self.start_interview_btn)
        
        # Bouton pour recommencer à zéro
        self.reset_interview_btn = QPushButton("🔄 RECOMMENCER À ZÉRO")
        self.reset_interview_btn.setProperty("class", "warning-button")
        self.reset_interview_btn.setMinimumHeight(30)
        self.reset_interview_btn.clicked.connect(self.reset_interview)
        interview_layout.addWidget(self.reset_interview_btn)
        
        # Compteur de questions
        self.question_counter = QLabel("Question 0/60")
        self.question_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.question_counter.setStyleSheet("color: #ff9f1c; font-weight: bold; font-size: 14px;")
        interview_layout.addWidget(self.question_counter)
        
        # Zone d'affichage de la question
        self.question_display = QTextEdit()
        self.question_display.setMaximumHeight(120)
        self.question_display.setPlaceholderText("Les questions apparaîtront ici...")
        self.question_display.setReadOnly(True)
        interview_layout.addWidget(self.question_display)
        
        # Boutons de contrôle
        control_layout = QHBoxLayout()
        
        self.next_btn = QPushButton("QUESTION SUIVANTE")
        self.next_btn.setProperty("class", "next-button")
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self.next_question)
        control_layout.addWidget(self.next_btn)
        
        self.end_question_btn = QPushButton("QUESTION TERMINÉE")
        self.end_question_btn.setProperty("class", "end-button")
        self.end_question_btn.setEnabled(False)
        self.end_question_btn.clicked.connect(self.end_current_question)
        control_layout.addWidget(self.end_question_btn)
        
        interview_layout.addLayout(control_layout)
        main_layout.addWidget(interview_group)
        
        main_layout.addStretch()
        
    def setup_audio(self):
        try:
            self.audio_worker = AudioWorker()
            self.audio_worker.level.connect(self.meter.set_dbfs)
            self.audio_worker.level.connect(self.check_vu_meter_activity)  # Surveiller l'activité
            
            self.refresh_btn.clicked.connect(self.populate_devices)
            self.device_combo.currentIndexChanged.connect(self.on_device_changed)
            
            self.populate_devices()
            
            # Timer pour vérifier périodiquement l'état du bouton commencer
            self.check_timer = QTimer()
            self.check_timer.timeout.connect(self.update_start_button_state)
            self.check_timer.start(500)  # Vérifier toutes les 500ms
            
        except Exception as e:
            print(f"Erreur setup audio: {e}")
        
    def check_vu_meter_activity(self, dbfs):
        """Surveille l'activité du vue-mètre pour validation avec debounce"""
        import time
        
        # Si déjà validé, ne plus rien faire
        if self.vu_meter_validated:
            return
        
        # Debug niveau audio (afficher de temps en temps)
        if hasattr(self, '_debug_counter'):
            self._debug_counter += 1
        else:
            self._debug_counter = 0
        
        if self._debug_counter % 20 == 0:  # Afficher toutes les 20 fois (1 seconde environ)
            print(f"🔊 Niveau audio: {dbfs:.1f} dBFS (seuil: {VU_METER_THRESHOLD} dBFS)")
            
        # Seuil d'activité : utiliser la variable globale
        if dbfs > VU_METER_THRESHOLD:
            # Activité détectée - annuler le timer de silence s'il existe
            if self.silence_debounce_timer is not None:
                self.silence_debounce_timer.stop()
                self.silence_debounce_timer = None
                print(f"🔄 Activité reprise à {dbfs:.1f} dBFS - Timer de silence annulé")
            
            # Début d'activité
            if self.vu_meter_start_time is None:
                self.vu_meter_start_time = time.time()
                print(f"🎤 Début détection activité micro à {dbfs:.1f} dBFS...")
            else:
                # Vérifier la durée
                elapsed = time.time() - self.vu_meter_start_time
                if elapsed >= self.vu_meter_required_duration:
                    # Validation réussie !
                    self.vu_meter_validated = True
                    self.vu_meter_start_time = None
                    print(f"✅ Microphone validé après {elapsed:.1f}s d'activité continue")
        else:
            # Silence détecté - déclencher le debounce timer s'il n'existe pas
            if self.silence_debounce_timer is None and self.vu_meter_start_time is not None:
                elapsed = time.time() - self.vu_meter_start_time
                print(f"⏸️ Silence détecté à {dbfs:.1f} dBFS après {elapsed:.1f}s - Debounce {SILENCE_DEBOUNCE_MS}ms")
                self.silence_debounce_timer = QTimer()
                self.silence_debounce_timer.setSingleShot(True)
                self.silence_debounce_timer.timeout.connect(self.reset_vu_meter_validation)
                self.silence_debounce_timer.start(self.silence_debounce_duration)
    
    def reset_vu_meter_validation(self):
        """Réinitialise la validation après le délai de debounce"""
        if self.vu_meter_start_time is not None:
            import time
            elapsed = time.time() - self.vu_meter_start_time
            print(f"❌ Silence confirmé après {elapsed:.1f}s - Réinitialisation (debounce {SILENCE_DEBOUNCE_MS}ms)")
            self.vu_meter_start_time = None
        
        self.silence_debounce_timer = None
    
    def update_start_button_state(self):
        """Met à jour l'état du bouton commencer selon les conditions"""
        if not self.interview_started:
            micro_selected = self.device_combo.currentData() is not None
            vu_validated = self.vu_meter_validated
            
            can_start = micro_selected and vu_validated
            self.start_interview_btn.setEnabled(can_start)
            
            if not micro_selected:
                self.start_interview_btn.setText("COMMENCER L'INTERVIEW (Sélectionnez un micro)")
            elif not vu_validated:
                if self.vu_meter_start_time is not None:
                    import time
                    elapsed = time.time() - self.vu_meter_start_time
                    remaining = self.vu_meter_required_duration - elapsed
                    self.start_interview_btn.setText(f"COMMENCER L'INTERVIEW (Parlez {remaining:.1f}s)")
                else:
                    self.start_interview_btn.setText(f"COMMENCER L'INTERVIEW (Parlez {VU_METER_VALIDATION_TIME}s au-dessus de {VU_METER_THRESHOLD}dB)")
            else:
                self.start_interview_btn.setText("COMMENCER L'INTERVIEW")
        
    def populate_devices(self):
        try:
            self.device_combo.clear()
            inputs = list_input_devices()
            if not inputs:
                self.device_combo.addItem("Aucun micro trouvé", None)
            else:
                self.device_combo.addItem("-- Sélectionnez --", None)
                for idx, label in inputs:
                    self.device_combo.addItem(label, idx)
        except Exception as e:
            print(f"Erreur populate: {e}")
            self.device_combo.addItem(f"Erreur: {e}", None)
        
    def on_device_changed(self, idx: int):
        try:
            dev_index = self.device_combo.currentData()
            
            if self.audio_worker:
                self.audio_worker.stop()
            
            # Réinitialiser la validation lors du changement de micro
            self.vu_meter_validated = False
            self.vu_meter_start_time = None
            
            # Nettoyer le timer de debounce s'il existe
            if self.silence_debounce_timer is not None:
                self.silence_debounce_timer.stop()
                self.silence_debounce_timer = None
            
            print("🔄 Changement de micro - Validation réinitialisée")
            
            if dev_index is None:
                self.status_label.setText("Aucun micro sélectionné")
                return
            
            dev_info = sd.query_devices(dev_index)
            device_name = dev_info['name']
            
            self.audio_worker.device_index = dev_index
            self.audio_worker.start()
            
            self.status_label.setText(f"🎤 {device_name}")
            print(f"Micro: {device_name}")
            
        except Exception as e:
            print(f"Erreur device_changed: {e}")
            self.status_label.setText(f"Erreur: {e}")
        
    # === MÉTHODES INTERVIEW ===
    
    def start_interview(self):
        """Démarre l'interview"""
        # Double vérification des conditions
        if self.device_combo.currentData() is None:
            self.question_display.setText("⚠️ Veuillez d'abord sélectionner un microphone avant de commencer l'interview.")
            return
        
        if not self.vu_meter_validated:
            self.question_display.setText("⚠️ Veuillez parler dans le microphone pendant 3 secondes pour le valider.")
            return
        
        self.interview_started = True
        
        # NE PAS faire de reset() - on veut garder l'index de reprise !
        # self.question_manager.reset()  ← SUPPRIMÉ
        
        # Mise à jour de l'interface
        self.start_interview_btn.setEnabled(False)
        self.start_interview_btn.setText("INTERVIEW EN COURS...")
        self.next_btn.setEnabled(True)
        self.end_question_btn.setEnabled(True)
        
        # Afficher la première question
        self.display_current_question()
        print("🎬 Interview démarrée")
    
    def display_current_question(self):
        """Affiche la question actuelle"""
        question_data = self.question_manager.get_current_question()
        if question_data:
            # Mise à jour du compteur avec indication de reprise
            current = self.question_manager.get_current_question_number()
            total = self.question_manager.get_total_questions()
            
            # Vérifier s'il y a des réponses existantes
            responses_count = self.count_existing_responses()
            if responses_count > 0 and current > 1:
                self.question_counter.setText(f"Question {current}/{total} (Reprise - {responses_count} déjà répondues)")
            else:
                self.question_counter.setText(f"Question {current}/{total}")
            
            # Affichage du texte de la question
            question_text = question_data['question']
            self.question_display.setText(f"📝 {question_text}")
            
            # Lecture de l'audio de la question
            audio_file = f"generated/{question_data['file_question']}"
            if os.path.exists(audio_file):
                self.play_question_audio(audio_file)
            else:
                print(f"⚠️ Fichier audio manquant: {audio_file}")
            
            # Mise à jour bouton suivant
            self.next_btn.setEnabled(self.question_manager.has_next_question())
            
            print(f"🎤 Question {current}: {question_text}")
    
    def play_question_audio(self, audio_file):
        """Joue l'audio de la question"""
        try:
            if self.current_audio_player:
                self.current_audio_player.stop()
                self.current_audio_player.wait()
            
            self.current_audio_player = AudioPlayer(audio_file)
            self.current_audio_player.finished.connect(self.on_question_finished)
            self.current_audio_player.start()
            print(f"🔊 Lecture question: {audio_file}")
        except Exception as e:
            print(f"❌ Erreur lecture audio: {e}")
    
    def on_question_finished(self):
        """Appelé quand l'audio de la question est terminé - Démarre l'enregistrement de la réponse"""
        print("🎤 Question terminée, démarrage surveillance réponse...")
        self.start_response_recording()
    
    def start_response_recording(self):
        """Démarre l'enregistrement de la réponse utilisateur"""
        try:
            # Obtenir le numéro de question actuel
            question_number = self.question_manager.get_current_question_number()
            
            # Arrêter l'enregistrement précédent s'il existe
            if hasattr(self, 'response_recorder') and self.response_recorder:
                self.response_recorder.stop_recording()
                self.response_recorder.wait()
            
            # Créer le nouvel enregistreur
            device_index = None
            if hasattr(self, 'audio_worker') and self.audio_worker:
                device_index = self.audio_worker.device_index
            
            self.response_recorder = ResponseRecorder(question_number, device_index)
            
            # Connecter les signaux
            self.response_recorder.recording_started.connect(self.on_recording_started)
            self.response_recorder.recording_finished.connect(self.on_recording_finished)
            self.response_recorder.speech_detected.connect(self.on_speech_detected)
            self.response_recorder.silence_detected.connect(self.on_silence_detected)
            
            # Démarrer l'enregistrement
            self.response_recorder.start()
            
        except Exception as e:
            print(f"❌ Erreur démarrage enregistrement: {e}")
    
    def on_recording_started(self):
        """Appelé quand l'enregistrement a vraiment commencé"""
        print("🔴 SIGNAL: Enregistrement démarré")
        # Optionnel: changer l'interface pour indiquer l'enregistrement
    
    def on_recording_finished(self, file_path):
        """Appelé quand l'enregistrement est terminé"""
        print(f"✅ SIGNAL: Enregistrement terminé - {file_path}")
        print("=" * 60)
        print("🎯 RÉPONSE ENREGISTRÉE AVEC SUCCÈS !")
        print(f"⏳ Attente de {DELAY_BEFORE_REPLY_MS/1000:.1f}s avant la réponse de Swan...")
        print("=" * 60)
        
        # Continuer avec délai
        self.continue_after_response()
    
    def on_speech_detected(self):
        """Appelé quand une parole est détectée"""
        print("🗣️ Parole détectée")
    
    def on_silence_detected(self):
        """Appelé quand un silence prolongé est détecté"""
        print("🤫 Silence prolongé détecté")
    
    def continue_after_response(self):
        """Continue le processus après l'enregistrement de la réponse avec délai"""
        print(f"⏳ Attente de {DELAY_BEFORE_REPLY_MS}ms avant la réponse bateau...")
        
        # Utiliser QTimer pour le délai depuis le thread principal
        QTimer.singleShot(DELAY_BEFORE_REPLY_MS, self.end_current_question)
    
    def update_resume_status(self):
        """Met à jour l'affichage avec l'état de reprise détecté"""
        try:
            current = self.question_manager.get_current_question_number()
            total = self.question_manager.get_total_questions()
            responses_count = self.count_existing_responses()
            
            # Mettre à jour le compteur
            if responses_count > 0 and current > 1:
                self.question_counter.setText(f"Question {current}/{total} (Reprise - {responses_count} déjà répondues)")
                
                # Message d'information dans l'affichage
                if current <= total:
                    self.question_display.setText(
                        f"🔄 REPRISE AUTOMATIQUE DÉTECTÉE\n\n"
                        f"📊 {responses_count} réponses déjà enregistrées\n"
                        f"➡️  Prêt à reprendre à la question {current}\n\n"
                        f"Validez votre microphone puis cliquez sur 'COMMENCER L'INTERVIEW'"
                    )
                else:
                    # Toutes les questions sont terminées
                    self.question_display.setText(
                        f"✅ INTERVIEW COMPLÈTE\n\n"
                        f"🎉 Toutes les {total} questions ont été répondues !\n"
                        f"📁 {responses_count} fichiers dans {RESPONSE_FOLDER}/\n\n"
                        f"Utilisez '🔄 RECOMMENCER À ZÉRO' pour une nouvelle interview"
                    )
            else:
                # Nouvelle interview
                self.question_counter.setText(f"Question 1/{total}")
                self.question_display.setText(
                    f"🚀 NOUVELLE INTERVIEW\n\n"
                    f"📋 {total} questions vous attendent\n"
                    f"🎤 Validez votre microphone puis commencez !"
                )
                
            print(f"✅ Interface mise à jour - Q{current}/{total} ({responses_count} réponses)")
            
        except Exception as e:
            print(f"❌ Erreur mise à jour reprise: {e}")
    
    def count_existing_responses(self):
        """Compte le nombre de réponses déjà enregistrées"""
        try:
            count = 0
            total_questions = self.question_manager.get_total_questions()
            
            for i in range(total_questions):
                question_num = i + 1
                response_file = os.path.join(RESPONSE_FOLDER, f"reponse_{question_num:02d}.wav")
                if os.path.exists(response_file):
                    count += 1
                else:
                    break  # Arrêter au premier fichier manquant
            
            return count
        except Exception as e:
            print(f"❌ Erreur comptage réponses: {e}")
            return 0
    
    def end_current_question(self):
        """Termine la question actuelle et joue la réponse"""
        question_data = self.question_manager.get_current_question()
        if question_data:
            # Arrêter l'audio de la question si en cours
            if self.current_audio_player:
                self.current_audio_player.stop()
                self.current_audio_player.wait()
            
            # Afficher la réponse dans l'interface
            reply_text = question_data['reply']
            current = self.question_manager.get_current_question_number()
            self.question_display.setText(f"💬 Swan: {reply_text}")
            
            # Jouer l'audio de la réponse
            audio_file = f"generated/{question_data['file_reply']}"
            if os.path.exists(audio_file):
                self.current_audio_player = AudioPlayer(audio_file)
                # Connecter le signal pour attendre la fin AVANT de continuer
                self.current_audio_player.finished.connect(self.on_reply_finished)
                self.current_audio_player.start()
                print(f"🔊 Lecture réponse: {audio_file}")
            else:
                print(f"⚠️ Fichier réponse manquant: {audio_file}")
                QTimer.singleShot(2000, self.on_reply_finished)
            
            # Désactiver temporairement les boutons
            self.end_question_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            
            print(f"✅ Question {current} terminée - Réponse: {reply_text}")
    
    def on_reply_finished(self):
        """Appelé quand l'audio de réponse est terminé"""
        print("🔊 Réponse terminée, attente 3 secondes...")
        # Attendre 3 secondes après la fin de l'audio puis passer à la suivante
        QTimer.singleShot(3000, self.auto_next_question)
    
    def auto_next_question(self):
        """Passe automatiquement à la question suivante après la réponse"""
        if self.question_manager.has_next_question():
            self.question_manager.next_question()
            self.display_current_question()
            self.end_question_btn.setEnabled(True)
        else:
            # Fin de l'interview
            self.end_interview()
    
    def next_question(self):
        """Passe manuellement à la question suivante"""
        if self.question_manager.has_next_question():
            self.question_manager.next_question()
            self.display_current_question()
        else:
            self.end_interview()
    
    def end_interview(self):
        """Termine l'interview"""
        self.interview_started = False
        
        # Compter les réponses enregistrées
        total_responses = self.count_existing_responses()
        self.question_display.setText(f"🎉 Interview terminée ! {total_responses} réponses enregistrées dans {RESPONSE_FOLDER}/")
        self.question_counter.setText("Interview terminée")
        
        # Réactivation des boutons
        self.start_interview_btn.setEnabled(True)
        self.start_interview_btn.setText("COMMENCER L'INTERVIEW")
        self.next_btn.setEnabled(False)
        self.end_question_btn.setEnabled(False)
        
        # Arrêter l'audio en cours
        if self.current_audio_player:
            self.current_audio_player.stop()
            self.current_audio_player.wait()
    
    def reset_interview(self):
        """Remet l'interview à zéro en supprimant toutes les réponses"""
        from PyQt6.QtWidgets import QMessageBox
        
        # Demander confirmation
        reply = QMessageBox.question(
            self, 
            "Confirmer la remise à zéro",
            f"Voulez-vous vraiment supprimer toutes les réponses enregistrées ?\n\n"
            f"Cette action supprimera tous les fichiers dans {RESPONSE_FOLDER}/\n"
            f"et remettra l'interview au début.\n\n"
            f"Cette action est irréversible !",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Supprimer tous les fichiers de réponse
                deleted_count = 0
                if os.path.exists(RESPONSE_FOLDER):
                    for filename in os.listdir(RESPONSE_FOLDER):
                        if filename.startswith("reponse_") and filename.endswith(".wav"):
                            file_path = os.path.join(RESPONSE_FOLDER, filename)
                            os.remove(file_path)
                            deleted_count += 1
                            print(f"🗑️  Supprimé: {filename}")
                
                # Réinitialiser le QuestionManager à l'index 0
                self.question_manager.current_index = 0
                
                # Réinitialiser l'affichage
                self.question_counter.setText("Question 1/60")
                self.question_display.setText("📋 Interview remise à zéro. Prêt à recommencer !")
                
                print(f"✅ Interview remise à zéro - {deleted_count} fichiers supprimés")
                
            except Exception as e:
                print(f"❌ Erreur lors de la remise à zéro: {e}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Erreur", f"Erreur lors de la remise à zéro:\n{e}")
        
        print("🏁 Interview terminée")
        
    # === FIN MÉTHODES INTERVIEW ===
        
    def show_warnings(self):
        try:
            print("Affichage popup 1...")
            disclaimer_popup = WarningPopup(
                self,
                "Avertissement",
                "Ceci est un message d'avertissement important. Veuillez écouter attentivement.",
                "disclaimer.wav"
            )
            
            if disclaimer_popup.exec() == QDialog.DialogCode.Accepted:
                print("Popup 1 fermée, affichage popup 2...")
                avant_popup = WarningPopup(
                    self,
                    "Avant de commencer",
                    "Avant de commencer, voici quelques informations importantes.",
                    "avant_de_commencer.wav"
                )
                
                if avant_popup.exec() == QDialog.DialogCode.Accepted:
                    print("Popup 2 fermée, démarrage ambiance...")
                    self.start_ambiance()
        except Exception as e:
            print(f"Erreur warnings: {e}")
            # Si erreur, on démarre quand même l'ambiance
            self.start_ambiance()
    
    def start_ambiance(self):
        """Démarre la musique d'ambiance en boucle sur thread dédié"""
        try:
            if os.path.exists("ambiance.mp3"):
                self.ambiance_player = AmbiancePlayer("ambiance.mp3", volume=0.15)
                self.ambiance_player.start()
                print("🎵 Ambiance démarrée (thread dédié)")
        except Exception as e:
            print(f"❌ Erreur ambiance: {e}")
    
    def closeEvent(self, event):
        try:
            # Arrêter tous les workers audio
            if self.audio_worker:
                self.audio_worker.stop()
            if self.current_audio_player:
                self.current_audio_player.stop()
                self.current_audio_player.wait()
            if self.ambiance_player:
                self.ambiance_player.stop()
                self.ambiance_player.wait()
            
            # Arrêter les timers
            if hasattr(self, 'check_timer'):
                self.check_timer.stop()
            if self.silence_debounce_timer is not None:
                self.silence_debounce_timer.stop()
                
            pygame.mixer.quit()
        except Exception as e:
            print(f"Erreur fermeture: {e}")
        event.accept()

def apply_dark_theme(app):
    """Thème dark"""
    try:
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        app.setPalette(dark_palette)
    except Exception as e:
        print(f"Erreur thème: {e}")

def detect_resume_index():
    """Détecte l'index de reprise AVANT le lancement de Qt"""
    try:
        # Créer le dossier s'il n'existe pas
        os.makedirs(RESPONSE_FOLDER, exist_ok=True)
        
        # Compter les questions totales (lecture rapide du JSON)
        total_questions = 0
        try:
            with open('question.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                total_questions = len(data)
        except Exception as e:
            print(f"❌ Erreur lecture questions: {e}")
            return 0
        
        # Chercher le dernier fichier reponse_xx.wav existant
        last_answered = -1
        
        for i in range(total_questions):
            question_num = i + 1  # Les fichiers commencent à 01
            response_file = os.path.join(RESPONSE_FOLDER, f"reponse_{question_num:02d}.wav")
            
            if os.path.exists(response_file):
                last_answered = i
                print(f"✅ Trouvé réponse Q{question_num}: {response_file}")
            else:
                break  # Arrêter à la première réponse manquante
        
        if last_answered >= 0:
            # Reprendre à la question suivante
            next_question = last_answered + 1
            if next_question < total_questions:
                print(f"🔄 REPRISE DÉTECTÉE à la question {next_question + 1}")
                print(f"   📝 {last_answered + 1} questions déjà répondues")
                return next_question
            else:
                # Toutes les questions sont répondues
                print(f"✅ INTERVIEW COMPLÈTE - Toutes les {total_questions} questions répondues")
                return total_questions - 1  # Dernière question
        else:
            # Première fois ou aucune réponse
            print(f"🚀 NOUVELLE INTERVIEW - Début à la question 1")
            return 0
            
    except Exception as e:
        print(f"❌ Erreur détection reprise: {e}")
        return 0


def main():
    try:
        print("Démarrage NovaQA...")
        
        # ÉTAPE 1: Détecter la reprise AVANT Qt
        resume_index = detect_resume_index()
        print(f"📋 Index de reprise détecté: {resume_index}")
        
        # ÉTAPE 2: Initialiser pygame mixer UNIQUEMENT pour l'ambiance
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=2048)
        pygame.mixer.init()
        print("🎵 Pygame mixer initialisé (AMBIANCE SEULEMENT)")
        
        # ÉTAPE 3: Lancer Qt avec l'index de reprise
        app = QApplication(sys.argv)
        apply_dark_theme(app)
        
        print("Création fenêtre...")
        window = MainWindow(resume_index)  # Passer l'index au constructeur
        window.show()
        window.raise_()
        window.activateWindow()
        
        print("Interface affichée, lancement boucle...")
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()