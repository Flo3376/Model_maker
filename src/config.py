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