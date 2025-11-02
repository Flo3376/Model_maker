# Guide du Développeur - NovaQA

## 🏗️ Architecture du Code

### Structure Modulaire

Le projet a été réorganisé en modules logiques pour faciliter la maintenance et le développement :

```
src/
├── config.py              # 🔧 Configuration centralisée
├── question_manager.py    # 📋 Gestion des questions 
├── audio_workers.py       # 🎤 Workers audio
├── widgets.py             # 🎨 Composants UI
├── main_window.py         # 🪟 Interface principale
└── interview_mixin.py     # 🎬 Logique d'interview
```

### Responsabilités des Modules

#### `config.py`
**Centralise toute la configuration**
- Paramètres audio (seuils, timeouts)
- Chemins des fichiers
- Constantes de l'interface
- Facilite les ajustements sans modifier le code

#### `question_manager.py`  
**Gestion intelligente des questions**
- Chargement depuis JSON
- Navigation dans les questions
- **Détection automatique de reprise** 
- Comptage des réponses existantes

#### `audio_workers.py`
**Workers audio professionnels**
- `AudioWorker` - Monitoring temps réel du VU-mètre
- `ResponseRecorder` - Enregistrement intelligent avec détection parole
- `AudioPlayer` - Lecture questions/réponses via sounddevice  
- `AmbiancePlayer` - Musique d'ambiance via pygame

#### `widgets.py`
**Composants d'interface personnalisés**
- `AudioMeterWidget` - VU-mètre graphique avec gradient
- `WarningPopup` - Popups avec lecture audio automatique

#### `main_window.py`
**Interface utilisateur principale**
- Setup de l'interface PyQt6
- Gestion des périphériques audio
- Validation du microphone
- Thème sombre

#### `interview_mixin.py`
**Logique complète de l'interview**
- Démarrage/arrêt interview
- Gestion des questions/réponses
- Enregistrement automatique
- Reprise intelligente

## 🔄 Flux de Fonctionnement

### 1. Démarrage (`main.py`)
```python
# 1. Détection de reprise (avant Qt)
resume_index = detect_resume_index()

# 2. Initialisation pygame (ambiance uniquement)
pygame.mixer.init()

# 3. Lancement interface Qt
window = MainWindow(resume_index)
```

### 2. Interface (`MainWindow`)
```python
# 1. Setup interface
setup_ui()              # Création widgets
setup_audio()           # Configuration audio workers

# 2. Validation microphone
check_vu_meter_activity()  # Surveillance continue
update_start_button_state() # État dynamique du bouton

# 3. Affichage warnings
show_warnings()         # Popups d'avertissement
start_ambiance()        # Musique de fond
```

### 3. Interview (`InterviewMixin`)
```python
# 1. Démarrage
start_interview()       # Validation + premier affichage

# 2. Cycle question/réponse
display_current_question()    # Affichage + lecture audio
start_response_recording()    # Enregistrement intelligent  
end_current_question()        # Lecture réponse Swan
auto_next_question()          # Passage automatique

# 3. Fin
end_interview()              # Récapitulatif + nettoyage
```

## 🎤 Système Audio

### Architecture Multi-Threaded
- **Thread principal** - Interface PyQt6
- **AudioWorker** - Monitoring VU-mètre (QObject + QTimer)
- **ResponseRecorder** - Enregistrement réponses (QThread)
- **AudioPlayer** - Lecture questions/réponses (QThread)
- **AmbiancePlayer** - Musique de fond (QThread)

### Détection Parole Intelligente
```python
# Paramètres ajustables dans config.py
VU_METER_THRESHOLD = -40.0        # Seuil détection activité
SPEECH_START_THRESHOLD_SEC = 0.3  # Durée avant démarrage
SPEECH_SILENCE_TIMEOUT_MS = 1500  # Timeout fin d'enregistrement
SPEECH_TOLERANCE_MS = 500         # Tolérance micro-pauses
```

### Évitement des Conflits Audio
- **sounddevice** - Enregistrement/lecture principale
- **pygame** - Musique d'ambiance UNIQUEMENT
- Streams séparés - Pas d'interférence

## 🔧 Points de Configuration

### Seuils Audio
```python
# config.py
VU_METER_THRESHOLD = -40.0        # Plus bas = plus sensible
VU_METER_VALIDATION_TIME = 1.5    # Durée validation micro
SILENCE_DEBOUNCE_MS = 1000        # Anti-rebond silence
```

### Interface
```python
# config.py  
WINDOW_TITLE = "NovaQA"
WINDOW_GEOMETRY = (100, 100, 800, 600)
AMBIANCE_VOLUME = 0.15
```

### Fichiers
```python
# config.py
RESPONSE_FOLDER = "sound_response"
GENERATED_FOLDER = "generated" 
QUESTIONS_FILE = "question.json"
```

## 🧪 Tests et Debug

### Script de Diagnostic
```bash
python check_system.py
```
Vérifie :
- Version Python compatible
- Dépendances installées
- Périphériques audio WASAPI
- Fichiers requis présents
- Format JSON des questions

### Debug Audio
```python
# Activer logs détaillés dans audio_workers.py
self._debug_counter % 20 == 0  # Modifiez la fréquence
```

### Test Modulaire
```python
# Tester un module individuellement
from src.question_manager import QuestionManager
qm = QuestionManager()
print(qm.get_total_questions())
```

## 🚀 Ajout de Fonctionnalités

### Nouvelle Question
1. Modifier `question.json`
2. Ajouter fichiers audio dans `generated/`
3. Format : `question_XX.wav` + `reply_XX.wav`

### Nouveau Paramètre
1. Ajouter dans `src/config.py`
2. Utiliser dans le module concerné
3. Documenter dans README.md

### Nouveau Widget
1. Créer dans `src/widgets.py`
2. Hériter de QWidget
3. Ajouter dans `main_window.py`

### Nouvelle Logique d'Interview
1. Ajouter méthode dans `interview_mixin.py`
2. Connecter signaux dans `main_window.py`
3. Tester avec cas d'usage variés

## 📦 Distribution

### Préparation
```bash
# Vérifier structure
python check_system.py

# Test complet
python main.py

# Nettoyage
git add src/ main.py
git commit -m "Architecture modulaire"
```

### Points d'Attention
- Garder `interview_ended.wav` dans Git
- Exclure `sound_response/` (données utilisateur)
- Inclure tous les modules `src/`
- Documenter les changements

## 🔮 Évolutions Futures

### Modularité Avancée
- Plugin system pour nouveaux types de questions
- Configuration via fichier YAML
- Interface de paramétrage graphique

### Audio Amélioré  
- Support formats multiples (MP3, FLAC)
- Effets audio temps réel
- Normalisation automatique

### Intelligence
- Détection émotions dans la voix
- Adaptation dynamique des questions
- Analyse qualité des réponses

---

**Architecture robuste, maintenable et extensible ! 🚀**