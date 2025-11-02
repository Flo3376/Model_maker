"""
Configuration et constantes globales pour NovaQA
"""

# === PARAMÈTRES AUDIO ===
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

# === PARAMÈTRES ENVIRONNEMENT BRUYANT ===
IMMEDIATE_RECORDING = True        # Démarrer l'enregistrement immédiatement (pas d'attente détection)
NOISE_FLOOR_ADAPTATION = True     # Adaptation automatique au bruit de fond
NOISE_FLOOR_LEARNING_SEC = 2.0    # Durée d'apprentissage du bruit de fond au début
DYNAMIC_SILENCE_DETECTION = True  # Détection de silence relative au bruit ambiant
MIN_SILENCE_DURATION_MS = 800     # Durée minimale de silence pour valider la fin (plus court pour réponses rapides)

# === PROFILS ENVIRONNEMENT ===
# Profil bureau calme
QUIET_OFFICE_PROFILE = {
    "threshold_offset": 0,         # Pas d'ajustement du seuil
    "min_silence_ms": 800,        # Silence court OK
    "learning_duration": 1.0,     # Apprentissage rapide
}

# Profil environnement bruyant  
NOISY_ENVIRONMENT_PROFILE = {
    "threshold_offset": 8,         # +8dB au-dessus du bruit
    "min_silence_ms": 1200,       # Silence plus long requis
    "learning_duration": 3.0,     # Apprentissage plus long
}

# Profil actuel (peut être changé dynamiquement)
CURRENT_PROFILE = QUIET_OFFICE_PROFILE

# === FICHIERS AUDIO SYSTÈME ===
DISCLAIMER_FILE = "disclaimer.wav"
INTRO_FILE = "avant_de_commencer.wav"
INTERVIEW_ENDED_FILE = "interview_ended.wav"
AMBIANCE_FILE = "ambiance.mp3"
GENERATED_FOLDER = "generated"
QUESTIONS_FILE = "question.json"

# === PARAMÈTRES INTERFACE ===
WINDOW_TITLE = "NovaQA"
WINDOW_GEOMETRY = (100, 100, 800, 600)
AMBIANCE_VOLUME = 0.15