# NovaQA - Model Maker

🎤 **Application d'interview audio automatisée pour création d'empreinte vocale**

NovaQA est une application Windows qui automatise le processus d'interview pour créer des échantillons vocaux de haute qualité. Elle guide l'utilisateur à travers une série de questions prédéfinies tout en enregistrant automatiquement les réponses.

## ✨ Fonctionnalités

- **Interface intuitive** : PyQt6 avec thème sombre professionnel
- **Vue-mètre temps réel** : Surveillance audio avec affichage dBFS
- **Détection automatique** : Début/fin d'enregistrement par détection vocale
- **Reprise intelligente** : Reprend automatiquement où l'interview s'était arrêtée
- **Audio HD** : Enregistrement WAV 44.1kHz avec traitement optimisé
- **60 questions** : Série complète pour capture vocale diversifiée

## 🚀 Installation Rapide

```bash
# Cloner le projet
git clone https://github.com/Flo3376/model_maker.git
cd model_maker

# Environnement virtuel (recommandé)
python -m venv .venv
.venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
python main.py
```

📖 **[Guide d'installation détaillé](install.md)**

## 🎯 Utilisation

1. **Sélectionner un microphone** WASAPI
2. **Valider le micro** en parlant 1.5s au-dessus de -40dBFS
3. **Commencer l'interview** avec le bouton dédié
4. **Répondre aux questions** - l'enregistrement se fait automatiquement
5. **Les réponses** sont sauvées dans `sound_response/`

## 📁 Structure

```
model_maker/
├── main.py                 # Point d'entrée principal  
├── src/                    # Code source modulaire
│   ├── config.py          # Configuration centralisée
│   ├── question_manager.py # Gestion questions & reprise
│   ├── audio_workers.py   # Workers audio professionnels
│   ├── widgets.py         # Interface personnalisée
│   ├── main_window.py     # Fenêtre principale
│   └── interview_mixin.py # Logique d'interview
├── question.json           # 60 questions prédéfinies  
├── requirements.txt        # Dépendances Python
├── check_system.py        # Diagnostic système
├── generated/             # Fichiers audio questions/réponses
├── sound_response/        # Réponses enregistrées (auto-créé)
└── vosk_models/          # Modèles reconnaissance vocale
```

## ⚙️ Configuration

Paramètres audio ajustables dans `src/config.py` :

```python
VU_METER_THRESHOLD = -40.0        # Seuil détection activité (dBFS)
VU_METER_VALIDATION_TIME = 1.5    # Durée validation micro (sec)
SPEECH_SILENCE_TIMEOUT_MS = 1500  # Timeout silence fin enregistrement
```

## 🏗️ Architecture Modulaire

**Code réorganisé en modules logiques :**

- **`config.py`** - Toutes les constantes et paramètres
- **`question_manager.py`** - Gestion des questions et détection de reprise  
- **`audio_workers.py`** - Workers audio (enregistrement, lecture, VU-mètre)
- **`widgets.py`** - Composants d'interface personnalisés
- **`main_window.py`** - Interface principale et setup
- **`interview_mixin.py`** - Logique complète d'interview

**Avantages :**
- 📦 Code maintenable et extensible
- 🔧 Configuration centralisée 
- 🧪 Tests et debug facilités
- 👥 Collaboration simplifiée

## 🛠️ Dépendances

- **PyQt6** - Interface utilisateur moderne
- **sounddevice** - Enregistrement audio professionnel  
- **soundfile** - Traitement fichiers audio
- **numpy** - Calculs audio optimisés
- **pygame** - Musique d'ambiance

## 🔧 Dépannage

### Microphone non détecté
- Vérifier les paramètres audio Windows
- Redémarrer l'application  
- Utiliser "REFRESH" dans l'interface

### Audio de mauvaise qualité
- Fermer les autres applications audio
- Ajuster `VU_METER_THRESHOLD` si nécessaire
- Vérifier que le micro est configuré à 44.1kHz

## 📊 Spécifications Techniques

- **OS** : Windows 10/11 (WASAPI requis)
- **Python** : 3.8+ (recommandé 3.10+)
- **Audio** : 44.1kHz 16-bit Mono WAV
- **Détection** : Seuil RMS configurable
- **Interface** : PyQt6 avec workers audio séparés

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit les changements (`git commit -am 'Ajout nouvelle fonctionnalité'`)
4. Push vers la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer une Pull Request

## 📄 Licence

Projet personnel - Voir LICENSE pour plus de détails

## 👨‍💻 Auteur

**Flo3376** - [GitHub](https://github.com/Flo3376)

---

🎤 *Créé pour simplifier la capture d'empreintes vocales de qualité professionnelle*

