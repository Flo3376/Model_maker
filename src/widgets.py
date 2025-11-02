"""
Widgets personnalisés pour l'interface NovaQA
"""

import math
import numpy as np
from PyQt6.QtWidgets import QWidget, QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QFont

from .config import DBFS_FLOOR


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


class EnvironmentAnalysisPopup(QDialog):
    """Popup d'analyse de l'environnement audio avec barre de progression"""
    analysis_complete = pyqtSignal(bool, float)  # is_stable, noise_variation
    
    def __init__(self, parent, audio_worker, duration=5.0):
        super().__init__(parent)
        self.audio_worker = audio_worker
        self.duration = duration
        self.samples = []
        self.start_time = None
        self.timer = None
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Analyse de l'environnement")
        self.setModal(True)
        self.setFixedSize(450, 200)
        
        # Force la fenêtre au premier plan
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
                border: 2px solid #ff9f1c;
            }
            QLabel {
                color: white;
                font-size: 12px;
                padding: 5px;
            }
            QProgressBar {
                border: 1px solid #666;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #ff9f1c;
                border-radius: 3px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Titre
        title = QLabel("🔍 ANALYSE DE L'ENVIRONNEMENT AUDIO")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ff9f1c;")
        layout.addWidget(title)
        
        # Instructions
        instruction = QLabel("Restez silencieux pendant que le système\névalue le niveau de bruit ambiant...")
        instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instruction)
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Informations temps réel
        self.info_label = QLabel("Préparation...")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("font-size: 10px; color: #cccccc;")
        layout.addWidget(self.info_label)
        
        self.setLayout(layout)
        
    def start_analysis(self):
        """Démarre l'analyse de l'environnement"""
        import time
        self.start_time = time.time()
        self.samples = []
        
        # Connecter au signal audio
        if self.audio_worker:
            self.audio_worker.level.connect(self.collect_sample)
        
        # Timer pour mettre à jour l'interface
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(100)  # Update toutes les 100ms
        
        self.info_label.setText("Analyse en cours... Restez silencieux")
        
    def collect_sample(self, dbfs):
        """Collecte un échantillon audio"""
        if self.start_time is not None:
            self.samples.append(dbfs)
    
    def update_progress(self):
        """Met à jour la barre de progression et vérifie la fin"""
        if self.start_time is None:
            return
            
        import time
        elapsed = time.time() - self.start_time
        progress = min(100, int((elapsed / self.duration) * 100))
        self.progress_bar.setValue(progress)
        
        # Mettre à jour les infos
        remaining = max(0, self.duration - elapsed)
        if remaining > 0:
            self.info_label.setText(f"Analyse en cours... {remaining:.1f}s restantes")
        else:
            self.finish_analysis()
    
    def finish_analysis(self):
        """Termine l'analyse et émet le résultat"""
        if self.timer:
            self.timer.stop()
            
        # Déconnecter du signal audio
        if self.audio_worker:
            try:
                self.audio_worker.level.disconnect(self.collect_sample)
            except:
                pass
        
        # Analyser les échantillons
        is_stable, variation = self.analyze_samples()
        
        # Afficher le résultat brièvement
        if is_stable:
            self.info_label.setText(f"✅ Environnement stable (variation: {variation:.1f}dB)")
        else:
            self.info_label.setText(f"⚠️ Environnement bruyant (variation: {variation:.1f}dB)")
        
        # Émettre le résultat après un petit délai
        QTimer.singleShot(1000, lambda: self.emit_result(is_stable, variation))
    
    def analyze_samples(self):
        """Analyse les échantillons collectés"""
        if len(self.samples) < 10:
            return False, 99.0  # Pas assez d'échantillons, considérer comme instable
        
        import numpy as np
        from .config import ENVIRONMENT_STABILITY_THRESHOLD
        
        # Calculer la variation (écart-type)
        variation = np.std(self.samples)
        is_stable = variation <= ENVIRONMENT_STABILITY_THRESHOLD
        
        print(f"📊 Analyse environnement:")
        print(f"   🎤 {len(self.samples)} échantillons collectés")
        print(f"   📈 Niveau moyen: {np.mean(self.samples):.1f} dBFS")
        print(f"   📊 Variation (écart-type): {variation:.1f} dB")
        print(f"   ✅ Stable: {is_stable} (seuil: {ENVIRONMENT_STABILITY_THRESHOLD} dB)")
        
        return is_stable, variation
    
    def emit_result(self, is_stable, variation):
        """Émet le résultat et ferme la popup"""
        self.analysis_complete.emit(is_stable, variation)
        self.accept()
    
    def closeEvent(self, event):
        """Nettoyage à la fermeture"""
        if self.timer:
            self.timer.stop()
        if self.audio_worker:
            try:
                self.audio_worker.level.disconnect(self.collect_sample)
            except:
                pass
        event.accept()


class ManualModeWarningPopup(QDialog):
    """Popup d'avertissement pour le passage en mode manuel"""
    
    def __init__(self, parent, variation):
        super().__init__(parent)
        self.variation = variation
        self.audio_player = None
        self.setup_ui()
        self.play_warning_sound()
        
    def setup_ui(self):
        self.setWindowTitle("⚠️ PASSAGE EN MODE MANUEL")
        self.setModal(True)
        self.setFixedSize(500, 300)
        
        # Force la fenêtre au premier plan
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: white;
                border: 3px solid #ff4444;
            }
            QLabel {
                color: white;
                font-size: 12px;
                padding: 5px;
            }
            QPushButton {
                background-color: #ff4444;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Titre avec icône
        title = QLabel("⚠️ ENVIRONNEMENT BRUYANT DÉTECTÉ")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff4444; padding: 10px;")
        layout.addWidget(title)
        
        # Message principal
        message = QLabel(f"""L'analyse révèle un environnement audio instable 
(variation: {self.variation:.1f} dB).

🔴 L'ARRÊT AUTOMATIQUE EST DÉSACTIVÉ

Pour chaque question:
1️⃣ Répondez normalement
2️⃣ Cliquez sur "QUESTION TERMINÉE" quand vous avez fini
3️⃣ Attendez la réponse de Swan
4️⃣ Cliquez sur "QUESTION SUIVANTE"

Cette méthode évite les coupures prématurées 
dues au bruit ambiant.""")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        layout.addWidget(message)
        
        # Bouton de confirmation
        ok_button = QPushButton("J'AI COMPRIS - CONTINUER")
        ok_button.clicked.connect(self.accept)
        layout.addWidget(ok_button)
        
        self.setLayout(layout)
    
    def play_warning_sound(self):
        """Joue le son d'avertissement s'il existe"""
        import os
        from .config import MANUAL_MODE_SOUND_FILE, GENERATED_FOLDER
        
        sound_file = f"{GENERATED_FOLDER}/{MANUAL_MODE_SOUND_FILE}"
        if os.path.exists(sound_file):
            from .audio_workers import AudioPlayer
            self.audio_player = AudioPlayer(sound_file)
            self.audio_player.start()
    
    def closeEvent(self, event):
        if self.audio_player:
            self.audio_player.stop()
        event.accept()


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
        import os
        if os.path.exists(self.audio_file):
            from .audio_workers import AudioPlayer
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