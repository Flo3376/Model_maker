# Installation et Configuration - NovaQA

## Prérequis Système

### Windows (recommandé)
- Windows 10/11
- Python 3.8+ (recommandé : 3.10 ou 3.11)
- Microphone fonctionnel (compatible WASAPI)

### Audio
- Le projet utilise **WASAPI** (Windows Audio Session API) pour l'audio
- Assure-toi que ton microphone est détecté par Windows

## Installation

### 1. Cloner le projet
```bash
git clone https://github.com/Flo3376/model_maker.git
cd model_maker
```

### 2. Créer un environnement virtuel (recommandé)
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Vérifier les fichiers audio requis
Assure-toi que ces fichiers sont présents dans le dossier principal :
- `disclaimer.wav`
- `avant_de_commencer.wav` 
- `interview_ended.wav`
- `ambiance.mp3`
- `generated/` (dossier contenant question_XX.wav)

## Structure du Projet

```
model_maker/
├── main.py                 # Point d'entrée principal (simplifié)
├── src/                    # Code source modulaire
│   ├── __init__.py
│   ├── config.py          # Configuration et constantes
│   ├── question_manager.py # Gestion des questions et reprise
│   ├── audio_workers.py   # Workers audio (enregistrement/lecture)
│   ├── widgets.py         # Widgets personnalisés (VU-mètre, popups)
│   ├── main_window.py     # Fenêtre principale et interface
│   └── interview_mixin.py # Logique d'interview
├── question.json           # Questions de l'interview
├── requirements.txt        # Dépendances Python
├── check_system.py        # Script de diagnostic
├── README.md              # Documentation
├── ambiance.mp3           # Musique d'ambiance
├── disclaimer.wav         # Audio d'avertissement
├── avant_de_commencer.wav # Audio intro
├── interview_ended.wav    # Audio de fin d'interview
├── generated/             # Fichiers audio des questions
│   ├── question_01.wav
│   ├── reply_01.wav
│   └── ...
├── sound_response/        # Réponses enregistrées (créé automatiquement)
│   └── reponse_XX.wav
└── vosk_models/          # Modèles de reconnaissance vocale
    └── vosk-model-small-fr-0.22/
```

## Lancement

```bash
python main.py
```

## Fonctionnalités

### Interface NovaQA
- **Vue-mètre audio** : Surveillance du niveau micro en temps réel
- **Validation micro** : Parler 1.5s au-dessus de -40dBFS pour valider
- **Interview automatique** : 60 questions avec enregistrement auto des réponses
- **Reprise intelligente** : Détection automatique où reprendre après interruption

### Enregistrement Audio
- Format : WAV 44.1kHz Mono
- Détection auto début/fin de parole
- Sauvegarde dans `sound_response/reponse_XX.wav`

### Paramètres Ajustables
Dans `main.py`, tu peux modifier :
```python
VU_METER_THRESHOLD = -40.0        # Seuil détection activité (dBFS)
VU_METER_VALIDATION_TIME = 1.5    # Durée validation micro (sec)
SPEECH_START_THRESHOLD_SEC = 0.3  # Seuil démarrage enregistrement
SPEECH_SILENCE_TIMEOUT_MS = 1500  # Timeout silence fin d'enregistrement
```

## Dépannage

### Problème : Aucun microphone détecté
1. Vérifier que le micro fonctionne dans Windows
2. Redémarrer l'application
3. Cliquer sur "REFRESH" dans l'interface

### Problème : Audio coupé ou mauvaise qualité
1. Fermer autres applications utilisant le micro
2. Vérifier les paramètres audio Windows
3. Ajuster `VU_METER_THRESHOLD` si trop sensible

### Problème : Erreur au lancement
```bash
# Réinstaller les dépendances
pip uninstall -r requirements.txt -y
pip install -r requirements.txt
```

### Problème : pygame/audio en conflit
- Le projet utilise **sounddevice** pour l'enregistrement/lecture questions
- **pygame** est utilisé UNIQUEMENT pour la musique d'ambiance
- Pas de conflit normalement

## Développement

### Ajout de questions
1. Modifier `question.json`
2. Ajouter les fichiers audio correspondants dans `generated/`
3. Format : `question_XX.wav` et `reply_XX.wav`

### Modification de l'interface
- Interface PyQt6 dans `MainWindow`
- Thème sombre appliqué automatiquement
- Workers audio séparés pour éviter les blocages

## Support

Pour signaler un bug ou demander une fonctionnalité :
1. Vérifier les logs console en cas d'erreur
2. Noter la configuration système (Windows version, Python version)
3. Créer une issue GitHub avec le maximum de détails