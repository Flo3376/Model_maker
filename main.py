#!/usr/bin/env python3
"""
NovaQA - Model Maker
Application d'interview audio automatisée pour création d'empreinte vocale

Point d'entrée principal de l'application
"""

import sys
import pygame
from PyQt6.QtWidgets import QApplication

# Import des modules locaux
from src.config import AMBIANCE_VOLUME
from src.question_manager import detect_resume_index
from src.main_window import MainWindow, apply_dark_theme


def main():
    """Fonction principale"""
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