"""
Méthodes d'interview pour MainWindow
Ce fichier contient toutes les méthodes liées à la gestion de l'interview
"""

import os
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox

from .config import DELAY_BEFORE_REPLY_MS, GENERATED_FOLDER, RESPONSE_FOLDER
from .audio_workers import AudioPlayer, ResponseRecorder
from .question_manager import count_existing_responses


class InterviewMixin:
    """Mixin contenant toutes les méthodes d'interview"""
    
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
            responses_count = count_existing_responses()
            if responses_count > 0 and current > 1:
                self.question_counter.setText(f"Question {current}/{total} (Reprise - {responses_count} déjà répondues)")
            else:
                self.question_counter.setText(f"Question {current}/{total}")
            
            # Affichage du texte de la question
            question_text = question_data['question']
            self.question_display.setText(f"📝 {question_text}")
            
            # Lecture de l'audio de la question
            audio_file = f"{GENERATED_FOLDER}/{question_data['file_question']}"
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
        print("🔊 [INTERFACE] Question audio terminée")
        print("🎤 [INTERFACE] Démarrage de l'enregistrement de la réponse...")
        self.start_response_recording()
    
    def start_response_recording(self):
        """Démarre l'enregistrement de la réponse utilisateur"""
        try:
            print("🔄 [INTERFACE] Préparation enregistrement réponse...")
            
            # Obtenir le numéro de question actuel
            question_number = self.question_manager.get_current_question_number()
            
            # Arrêter l'enregistrement précédent s'il existe
            if hasattr(self, 'response_recorder') and self.response_recorder:
                print("🛑 [INTERFACE] Arrêt enregistrement précédent...")
                self.response_recorder.stop_recording()
                self.response_recorder.wait()
            
            # Créer le nouvel enregistreur (mode manuel supprimé)
            device_index = None
            if hasattr(self, 'audio_worker') and self.audio_worker:
                device_index = self.audio_worker.device_index
            
            print(f"🎤 [INTERFACE] Création ResponseRecorder pour Q{question_number}")
            
            # Passer la fréquence pré-testée si disponible
            preferred_samplerate = getattr(self, 'best_audio_frequency', None)
            if preferred_samplerate:
                print(f"📊 [INTERFACE] Utilisation fréquence pré-testée: {preferred_samplerate}Hz")
            
            self.response_recorder = ResponseRecorder(question_number, device_index, preferred_samplerate)
            
            # Connecter les signaux
            self.response_recorder.recording_started.connect(self.on_recording_started)
            self.response_recorder.recording_finished.connect(self.on_recording_finished)
            self.response_recorder.speech_detected.connect(self.on_speech_detected)
            self.response_recorder.silence_detected.connect(self.on_silence_detected)
            
            # Démarrer l'enregistrement
            print("▶️ [INTERFACE] Lancement du thread d'enregistrement...")
            self.response_recorder.start()
            
        except Exception as e:
            print(f"❌ [INTERFACE] Erreur démarrage enregistrement: {e}")
    
    def on_recording_started(self):
        """Appelé quand l'enregistrement a vraiment commencé"""
        print("✅ [INTERFACE] Signal reçu: enregistrement confirmé démarré")
        self.show_recording_indicator()  # Afficher le voyant
    
    def on_recording_finished(self, file_path):
        """Appelé quand l'enregistrement est terminé"""
        print(f"📁 [INTERFACE] Signal reçu: enregistrement terminé -> {file_path}")
        self.hide_recording_indicator()  # Masquer le voyant
        print("=" * 60)
        print("🎯 [INTERFACE] RÉPONSE ENREGISTRÉE AVEC SUCCÈS !")
        print("=" * 60)
        
        # NE PLUS continuer automatiquement - l'utilisateur doit cliquer
        print("👆 [INTERFACE] Cliquez sur 'QUESTION TERMINÉE' quand vous avez fini de parler")
    
    def on_speech_detected(self):
        """Appelé quand une parole est détectée"""
        print("🗣️ [INTERFACE] Signal reçu: parole détectée")
    
    def on_silence_detected(self):
        """Appelé quand un silence prolongé est détecté"""
        print("🤫 [INTERFACE] Signal reçu: silence prolongé détecté")
    
    def update_resume_status(self):
        """Met à jour l'affichage avec l'état de reprise détecté"""
        try:
            current = self.question_manager.get_current_question_number()
            total = self.question_manager.get_total_questions()
            responses_count = count_existing_responses()
            
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
    
    def end_current_question(self):
        """Termine la question actuelle et joue la réponse"""
        print("🔘 [INTERFACE] BOUTON 'QUESTION TERMINÉE' cliqué")
        
        question_data = self.question_manager.get_current_question()
        if question_data:
            # Arrêter l'audio de la question si en cours
            if self.current_audio_player:
                print("🛑 [INTERFACE] Arrêt lecture question en cours...")
                self.current_audio_player.stop()
                self.current_audio_player.wait()
            
            # Arrêter l'enregistrement en cours
            if hasattr(self, 'response_recorder') and self.response_recorder:
                print("🛑 [INTERFACE] Demande d'arrêt de l'enregistrement...")
                self.response_recorder.stop_recording()
                self.hide_recording_indicator()  # Masquer le voyant
            
            # Afficher la réponse dans l'interface
            reply_text = question_data['reply']
            current = self.question_manager.get_current_question_number()
            self.question_display.setText(f"💬 Swan: {reply_text}")
            
            # Jouer l'audio de la réponse après un petit délai
            print("⏱️ [INTERFACE] Délai 500ms avant lecture réponse Swan...")
            QTimer.singleShot(500, lambda: self._play_current_reply(question_data))
            
            # Désactiver temporairement les boutons
            self.end_question_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            
            print(f"✅ [INTERFACE] Question {current} marquée terminée - Réponse: {reply_text}")
    
    def _play_current_reply(self, question_data):
        """Joue la réponse de la question actuelle"""
        print("🔊 [INTERFACE] Début lecture réponse Swan...")
        
        # Jouer l'audio de la réponse
        audio_file = f"{GENERATED_FOLDER}/{question_data['file_reply']}"
        if os.path.exists(audio_file):
            print(f"📂 [INTERFACE] Fichier audio trouvé: {audio_file}")
            self.current_audio_player = AudioPlayer(audio_file)
            # Connecter le signal pour attendre la fin AVANT de continuer
            self.current_audio_player.finished.connect(self.on_reply_finished)
            self.current_audio_player.start()
            print(f"▶️ [INTERFACE] Lecture démarrée: {audio_file}")
        else:
            print(f"❌ [INTERFACE] Fichier réponse manquant: {audio_file}")
            print("⏱️ [INTERFACE] Délai 2s puis simulation fin réponse...")
            QTimer.singleShot(2000, self.on_reply_finished)
    
    def on_reply_finished(self):
        """Appelé quand l'audio de réponse est terminé - PLUS de passage automatique"""
        print("🔊 [INTERFACE] Réponse Swan terminée")
        print("👆 [INTERFACE] Cliquez sur 'QUESTION SUIVANTE' pour continuer")
        
        # Réactiver les boutons pour que l'utilisateur puisse continuer manuellement
        self.next_btn.setEnabled(self.question_manager.has_next_question())
        if not self.question_manager.has_next_question():
            # Dernière question, activer le bouton de fin d'interview
            print("🏁 [INTERFACE] Dernière question - Bouton 'TERMINER L'INTERVIEW' activé")
            self.next_btn.setText("TERMINER L'INTERVIEW")
            self.next_btn.setEnabled(True)
    
    def next_question(self):
        """Passe manuellement à la question suivante (SEULE méthode maintenant)"""
        print("🔘 [INTERFACE] BOUTON 'QUESTION SUIVANTE' cliqué")
        
        # ARRÊTER D'ABORD L'ENREGISTREMENT EN COURS
        if hasattr(self, 'response_recorder') and self.response_recorder:
            print("🛑 [INTERFACE] Arrêt enregistrement avant question suivante...")
            self.response_recorder.stop_recording()
            self.response_recorder.wait()  # Attendre que l'arrêt soit effectif
        
        if self.question_manager.has_next_question():
            print("➡️ [INTERFACE] Passage à la question suivante...")
            self.question_manager.next_question()
            self.display_current_question()
            # Réactiver le bouton de fin de question pour la nouvelle question
            self.end_question_btn.setEnabled(True)
            # Remettre le texte normal du bouton
            self.next_btn.setText("QUESTION SUIVANTE")
        else:
            # Fin de l'interview
            print("🏁 [INTERFACE] Fin de l'interview demandée")
            self.end_interview()
    
    def end_interview(self):
        """Termine l'interview"""
        self.interview_started = False
        
        # Compter les réponses enregistrées
        total_responses = count_existing_responses()
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
                QMessageBox.warning(self, "Erreur", f"Erreur lors de la remise à zéro:\n{e}")
        
        print("🏁 Interview terminée")