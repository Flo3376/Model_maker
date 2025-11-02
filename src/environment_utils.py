"""
Utilitaires pour la gestion des environnements audio
"""

from .config import (
    QUIET_OFFICE_PROFILE, NOISY_ENVIRONMENT_PROFILE, VU_METER_THRESHOLD,
    MIN_SILENCE_DURATION_MS, NOISE_FLOOR_LEARNING_SEC
)


class EnvironmentManager:
    """Gestionnaire des profils d'environnement audio"""
    
    def __init__(self):
        self.current_profile = QUIET_OFFICE_PROFILE.copy()
        self.base_threshold = VU_METER_THRESHOLD
        
    def set_quiet_environment(self):
        """Configure pour un environnement calme (bureau, maison)"""
        self.current_profile = QUIET_OFFICE_PROFILE.copy()
        print("🔇 Profil ENVIRONNEMENT CALME activé")
        print(f"   📊 Seuil: {self.base_threshold} dBFS (base)")
        print(f"   ⏱️ Silence minimum: {self.current_profile['min_silence_ms']}ms")
        print(f"   🎓 Apprentissage: {self.current_profile['learning_duration']}s")
        
    def set_noisy_environment(self):
        """Configure pour un environnement bruyant (open space, café)"""
        self.current_profile = NOISY_ENVIRONMENT_PROFILE.copy()
        print("🔊 Profil ENVIRONNEMENT BRUYANT activé")
        print(f"   📊 Seuil adaptatif: +{self.current_profile['threshold_offset']} dBFS au-dessus du bruit")
        print(f"   ⏱️ Silence minimum: {self.current_profile['min_silence_ms']}ms (plus long)")
        print(f"   🎓 Apprentissage: {self.current_profile['learning_duration']}s (plus précis)")
        
    def get_adapted_threshold(self, noise_floor):
        """Calcule le seuil adapté selon l'environnement et le bruit mesuré"""
        if noise_floor > -80.0:  # Si on a mesuré du bruit
            adapted = noise_floor + self.current_profile['threshold_offset'] + 6.0  # +6dB base
            return max(adapted, self.base_threshold)  # Jamais en dessous du minimum
        return self.base_threshold
    
    def get_silence_duration(self):
        """Retourne la durée de silence adaptée à l'environnement"""
        return self.current_profile['min_silence_ms']
    
    def get_learning_duration(self):
        """Retourne la durée d'apprentissage adaptée"""
        return self.current_profile['learning_duration']
    
    def analyze_environment(self, noise_samples):
        """Analyse les échantillons de bruit et suggère un profil"""
        if not noise_samples:
            return "unknown"
            
        import numpy as np
        avg_noise = np.mean(noise_samples)
        noise_variation = np.std(noise_samples)
        
        if avg_noise < -50.0 and noise_variation < 3.0:
            return "quiet"  # Environnement calme et stable
        elif avg_noise > -35.0 or noise_variation > 8.0:
            return "noisy"  # Environnement bruyant ou variable
        else:
            return "moderate"  # Environnement modéré
    
    def auto_configure(self, noise_samples):
        """Configuration automatique basée sur l'analyse"""
        env_type = self.analyze_environment(noise_samples)
        
        if env_type == "quiet":
            self.set_quiet_environment()
            return "quiet"
        elif env_type == "noisy":
            self.set_noisy_environment() 
            return "noisy"
        else:
            print("🔀 Profil ENVIRONNEMENT MODÉRÉ (configuration par défaut)")
            return "moderate"


# Instance globale
environment_manager = EnvironmentManager()