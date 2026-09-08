"""
OllamaSupervisor - Module de supervision des corrections automatiques via Ollama.

Ce module utilise le modèle mistral:instruct pour valider les corrections
automatiques du bot en respectant les conventions Wikipedia en français.
"""

import requests
import json
import subprocess
import time
import hashlib
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class SupervisorDecision:
    """Décision du superviseur sur une correction."""
    action: str  # "approve", "reject", "modify"
    reason: str  # Explication de la décision
    modified_text: Optional[str] = None  # Texte modifié si action="modify"


class OllamaSupervisor:
    """Superviseur de corrections automatiques utilisant Ollama."""
    
    def __init__(self, model: str = "mistral:instruct", host: str = "http://localhost:11434", auto_start: bool = True, max_validations: Optional[int] = None):
        """
        Initialise le superviseur Ollama.
        
        Args:
            model: Modèle Ollama à utiliser (défaut: mistral:instruct)
            host: URL du serveur Ollama (défaut: http://localhost:11434)
            auto_start: Démarrer Ollama automatiquement s'il n'est pas disponible
            max_validations: Nombre maximum de validations (None = illimité)
        """
        self.model = model
        self.host = host
        self.api_url = f"{host}/api/generate"
        self.enabled = True
        self.ollama_process = None
        self.max_validations = max_validations
        self.validation_count = 0
        self.cache: Dict[str, SupervisorDecision] = {}  # Cache des décisions
        
        # Vérifier la connexion au démarrage
        if not self._check_ollama_available():
            if auto_start:
                print("🚀 Ollama non disponible, tentative de démarrage automatique...")
                if self._start_ollama():
                    print("✅ Ollama démarré avec succès")
                    # Vérifier que le modèle est disponible
                    if not self._ensure_model():
                        print(f"⚠️ Modèle {model} non disponible, tentative de téléchargement...")
                        if self._pull_model():
                            print(f"✅ Modèle {model} téléchargé avec succès")
                        else:
                            print(f"⚠️ Impossible de télécharger le modèle {model}")
                            self.enabled = False
                else:
                    print("⚠️ Impossible de démarrer Ollama")
                    self.enabled = False
            else:
                print(f"⚠️ Ollama non disponible sur {host}")
                self.enabled = False
    
    def _check_ollama_available(self) -> bool:
        """Vérifie si Ollama est disponible."""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def _start_ollama(self) -> bool:
        """Démarre le serveur Ollama."""
        try:
            # Démarrer ollama serve en arrière-plan
            self.ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            # Attendre que le serveur soit prêt
            for _ in range(30):  # 30 secondes max
                time.sleep(1)
                if self._check_ollama_available():
                    return True
            
            return False
        except Exception as e:
            print(f"⚠️ Erreur lors du démarrage d'Ollama: {e}")
            return False
    
    def _ensure_model(self) -> bool:
        """Vérifie si le modèle est disponible."""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                return any(self.model in name for name in model_names)
            return False
        except Exception:
            return False
    
    def _pull_model(self) -> bool:
        """Télécharge le modèle Ollama."""
        try:
            process = subprocess.Popen(
                ["ollama", "pull", self.model],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            process.wait(timeout=300)  # 5 minutes max pour le téléchargement
            return process.returncode == 0
        except Exception as e:
            print(f"⚠️ Erreur lors du téléchargement du modèle: {e}")
            return False
    
    def _build_prompt(self, context: str, original: str, suggested: str, issue_type: str, description: str) -> str:
        """
        Construit le prompt pour le modèle (version optimisée).
        
        Args:
            context: Contexte minimal autour de la correction (50-100 caractères avant/après)
            original: Texte original à corriger
            suggested: Texte suggéré par le bot
            issue_type: Type du problème détecté
            description: Description du problème
            
        Returns:
            Prompt formaté pour le modèle
        """
        prompt = f"""Valide cette correction Wikipedia FR.
Type: {issue_type}
Desc: {description}
Original: "{original}"
Suggéré: "{suggested}"

Règles: typographie FR, citations §8.1, titres œuvres (italique=œuvre, guillemets=épisode), pas corruption wikicode.

JSON uniquement:
{{"action":"approve|reject|modify","reason":"court","modified_text":null si pas modify}}"""
        
        return prompt
    
    def review_correction(
        self,
        full_content: str,
        position: int,
        original: str,
        suggested: str,
        issue_type: str,
        description: str
    ) -> SupervisorDecision:
        """
        Soumet une correction au superviseur pour validation.
        
        Args:
            full_content: Contenu complet de l'article
            position: Position de la correction dans l'article
            original: Texte original
            suggested: Texte suggéré
            issue_type: Type du problème
            description: Description du problème
            
        Returns:
            SupervisorDecision avec l'action et la raison
        """
        if not self.enabled:
            # Si Ollama n'est pas disponible, approuve par défaut
            return SupervisorDecision(
                action="approve",
                reason="Ollama non disponible - validation par défaut"
            )
        
        # Vérifier la limite de validations
        if self.max_validations is not None and self.validation_count >= self.max_validations:
            return SupervisorDecision(
                action="default",
                reason=f"Limite de validations atteinte ({self.max_validations}) - validation par défaut"
            )
        
        # Créer une clé de cache basée sur la correction
        cache_key = hashlib.md5(
            f"{issue_type}:{original}:{suggested}".encode()
        ).hexdigest()
        
        # Vérifier le cache
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Extraire le contexte minimal (50 caractères avant/après)
        context_start = max(0, position - 50)
        context_end = min(len(full_content), position + len(original) + 50)
        context = full_content[context_start:context_end]
        
        # Construire le prompt
        prompt = self._build_prompt(context, original, suggested, issue_type, description)
        
        try:
            # Incrémenter le compteur
            self.validation_count += 1
            
            # Appeler l'API Ollama
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json"
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=300  # Timeout de 300 secondes (5 minutes) pour les modèles plus lents
            )
            
            if response.status_code != 200:
                print(f"⚠️ Erreur Ollama: {response.status_code}")
                return SupervisorDecision(
                    action="approve",
                    reason="Erreur API Ollama - validation par défaut"
                )
            
            # Parser la réponse JSON
            result = response.json()
            response_text = result.get("response", "")
            
            # Extraire le JSON de la réponse
            try:
                # Nettoyer la réponse pour extraire le JSON
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    decision_data = json.loads(json_str)
                    
                    action = decision_data.get("action", "approve")
                    reason = decision_data.get("reason", "")
                    modified_text = decision_data.get("modified_text")
                    
                    # Valider l'action
                    if action not in ["approve", "reject", "modify"]:
                        action = "approve"
                    
                    decision = SupervisorDecision(
                        action=action,
                        reason=reason,
                        modified_text=modified_text if action == "modify" else None
                    )
                    
                    # Mettre en cache
                    self.cache[cache_key] = decision
                    
                    return decision
                else:
                    raise ValueError("JSON non trouvé dans la réponse")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"⚠️ Erreur parsing réponse Ollama: {e}")
                return SupervisorDecision(
                    action="approve",
                    reason="Erreur parsing - validation par défaut"
                )
                
        except requests.Timeout:
            print("⚠️ Timeout Ollama")
            return SupervisorDecision(
                action="approve",
                reason="Timeout - validation par défaut"
            )
        except Exception as e:
            print(f"⚠️ Erreur inattendue Ollama: {e}")
            return SupervisorDecision(
                action="approve",
                reason="Erreur inattendue - validation par défaut"
            )
    
    def is_available(self) -> bool:
        """Vérifie si Ollama est disponible."""
        return self.enabled
