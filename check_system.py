#!/usr/bin/env python3
"""
Script de diagnostic pour NovaQA
Vérifie l'installation et la configuration du système
"""

import sys
import os
import platform

def check_python_version():
    """Vérifie la version Python"""
    version = sys.version_info
    print(f"🐍 Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ requis")
        return False
    else:
        print("✅ Version Python compatible")
        return True

def check_dependencies():
    """Vérifie les dépendances"""
    required_packages = [
        "PyQt6", "numpy", "sounddevice", "soundfile", "pygame"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.lower() if package != "PyQt6" else "PyQt6")
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} manquant")
            missing.append(package)
    
    return len(missing) == 0

def check_audio_system():
    """Vérifie le système audio"""
    try:
        import sounddevice as sd
        
        # Lister les devices audio
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        
        print(f"\n🔊 Système audio:")
        print(f"   Devices trouvés: {len(devices)}")
        
        wasapi_devices = []
        for idx, dev in enumerate(devices):
            if dev.get('max_input_channels', 0) > 0:
                host_name = hostapis[dev['hostapi']]['name']
                if host_name == 'Windows WASAPI':
                    wasapi_devices.append(dev['name'])
        
        print(f"   Micros WASAPI: {len(wasapi_devices)}")
        
        if wasapi_devices:
            print("✅ Système audio compatible")
            for i, device in enumerate(wasapi_devices[:3]):  # Afficher max 3
                print(f"   - {device}")
            if len(wasapi_devices) > 3:
                print(f"   ... et {len(wasapi_devices)-3} autres")
            return True
        else:
            print("❌ Aucun microphone WASAPI trouvé")
            return False
            
    except Exception as e:
        print(f"❌ Erreur système audio: {e}")
        return False

def check_files():
    """Vérifie les fichiers requis"""
    required_files = [
        "main.py",
        "question.json", 
        "disclaimer.wav",
        "avant_de_commencer.wav",
        "interview_ended.wav",
        "ambiance.mp3"
    ]
    
    optional_dirs = [
        "generated/",
        "vosk_models/"
    ]
    
    print(f"\n📁 Fichiers requis:")
    missing_files = []
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} manquant")
            missing_files.append(file)
    
    print(f"\n📂 Dossiers optionnels:")
    for dir_path in optional_dirs:
        if os.path.exists(dir_path):
            if dir_path == "generated/":
                count = len([f for f in os.listdir(dir_path) if f.endswith('.wav')])
                print(f"✅ {dir_path} ({count} fichiers audio)")
            else:
                print(f"✅ {dir_path}")
        else:
            print(f"⚠️  {dir_path} absent")
    
    return len(missing_files) == 0

def check_question_json():
    """Vérifie le format du fichier question.json"""
    try:
        import json
        from src.config import QUESTIONS_FILE
        with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"\n📋 question.json:")
        print(f"✅ Format JSON valide")
        print(f"✅ {len(data)} questions trouvées")
        
        # Vérifier le premier élément
        if data and isinstance(data[0], dict):
            first_key = list(data[0].keys())[0]
            first_question = data[0][first_key]
            required_keys = ['question', 'file_question', 'reply']
            
            missing_keys = [key for key in required_keys if key not in first_question]
            if missing_keys:
                print(f"❌ Clés manquantes: {missing_keys}")
                return False
            else:
                print(f"✅ Structure des questions valide")
                return True
        else:
            print(f"❌ Format questions invalide")
            return False
            
            
    except FileNotFoundError:
        print(f"❌ {QUESTIONS_FILE} non trouvé")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Erreur JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur lecture questions: {e}")
        return False

def main():
    """Fonction principale du diagnostic"""
    print("🔍 DIAGNOSTIC NOVAQA")
    print("=" * 50)
    
    print(f"💻 Système: {platform.system()} {platform.release()}")
    print(f"📂 Dossier: {os.getcwd()}")
    print()
    
    checks = [
        ("Version Python", check_python_version),
        ("Dépendances", check_dependencies), 
        ("Système audio", check_audio_system),
        ("Fichiers requis", check_files),
        ("Configuration questions", check_question_json)
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n--- {name} ---")
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Erreur lors de {name}: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 RÉSUMÉ")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 Tous les tests réussis ({passed}/{total})")
        print("✅ NovaQA devrait fonctionner correctement")
        print("\n🚀 Lancement avec: python main.py")
    else:
        failed = total - passed
        print(f"⚠️  {passed}/{total} tests réussis, {failed} échec(s)")
        print("❌ Corriger les problèmes avant de lancer NovaQA")
        print("\n📖 Voir install.md pour les solutions")

if __name__ == "__main__":
    main()