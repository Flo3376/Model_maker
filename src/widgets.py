"""
Widgets personnalisés pour l'interface NovaQA
"""

import math
import numpy as np
from PyQt6.QtWidgets import QWidget, QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
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