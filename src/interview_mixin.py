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
            audio_file = f"{GENERATED_FOLDER}/{question_data['file_reply']}"
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