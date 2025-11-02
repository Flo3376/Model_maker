"""
Gestion des questions et des périphériques audio
"""

import json
import os
from typing import List, Tuple
import sounddevice as sd

from .config import QUESTIONS_FILE, RESPONSE_FOLDER


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
            with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.questions = data
                print(f"📋 {len(self.questions)} questions chargées")
                
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


def detect_resume_index():
    """Détecte l'index de reprise AVANT le lancement de Qt"""
    try:
        # Créer le dossier s'il n'existe pas
        os.makedirs(RESPONSE_FOLDER, exist_ok=True)
        
        # Compter les questions totales (lecture rapide du JSON)
        total_questions = 0
        try:
            with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
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


def count_existing_responses():
    """Compte le nombre de réponses déjà enregistrées"""
    try:
        count = 0
        # Lire le nombre total de questions
        with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            total_questions = len(data)
        
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