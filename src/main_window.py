"""
Fenêtre principale de NovaQA
"""

import os
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QVBoxLayout, QLabel, QPushButton, 
    QWidget, QHBoxLayout, QComboBox, QGroupBox, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPalette, QColor

from .config import (
    WINDOW_TITLE, WINDOW_GEOMETRY, VU_METER_THRESHOLD, VU_METER_VALIDATION_TIME,
    SILENCE_DEBOUNCE_MS, DELAY_BEFORE_REPLY_MS, DISCLAIMER_FILE, INTRO_FILE,
    AMBIANCE_FILE, GENERATED_FOLDER, RESPONSE_FOLDER
)
from .question_manager import QuestionManager, list_input_devices, count_existing_responses
from .widgets import AudioMeterWidget, WarningPopup
from .audio_workers import AudioWorker, ResponseRecorder, AudioPlayer, AmbiancePlayer
from .interview_mixin import InterviewMixin


class MainWindow(QMainWindow, InterviewMixin):
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
        self.setWindowTitle(WINDOW_TITLE)
        self.setGeometry(*WINDOW_GEOMETRY)
        
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
            import sounddevice as sd
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
    
    def check_vu_meter_activity(self, dbfs):
        """Surveille l'activité du vue-mètre pour validation avec debounce"""
        
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
                    elapsed = time.time() - self.vu_meter_start_time
                    remaining = self.vu_meter_required_duration - elapsed
                    self.start_interview_btn.setText(f"COMMENCER L'INTERVIEW (Parlez {remaining:.1f}s)")
                else:
                    self.start_interview_btn.setText(f"COMMENCER L'INTERVIEW (Parlez {VU_METER_VALIDATION_TIME}s au-dessus de {VU_METER_THRESHOLD}dB)")
            else:
                self.start_interview_btn.setText("COMMENCER L'INTERVIEW")
    
    def show_warnings(self):
        try:
            print("Affichage popup 1...")
            disclaimer_popup = WarningPopup(
                self,
                "Avertissement",
                "Ceci est un message d'avertissement important. Veuillez écouter attentivement.",
                DISCLAIMER_FILE
            )
            
            if disclaimer_popup.exec() == QDialog.DialogCode.Accepted:
                print("Popup 1 fermée, affichage popup 2...")
                avant_popup = WarningPopup(
                    self,
                    "Avant de commencer",
                    "Avant de commencer, voici quelques informations importantes.",
                    INTRO_FILE
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
            if os.path.exists(AMBIANCE_FILE):
                self.ambiance_player = AmbiancePlayer(AMBIANCE_FILE)
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
                
            import pygame
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