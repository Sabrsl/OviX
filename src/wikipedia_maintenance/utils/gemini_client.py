"""
Client pour l'intégration avec Google Gemini API pour le traitement d'articles Wikipédia.

Ce module permet d'envoyer un article à un modèle Gemini avec un prompt
spécifique, en vérifiant d'abord la longueur de l'article par regex.
"""

import requests
import json
import time
from typing import Optional, Tuple
from pathlib import Path
import logging

from .verif_longueur import verifier, LIMITE_CARACTERES, calculer_timeout, verifier_fidelite
from .lia_logger import log_lia_operation

logger = logging.getLogger(__name__)


class GeminiClient:
    """Client pour communiquer avec Google Gemini API pour le traitement d'articles."""
    
    def __init__(
        self,
        api_key: str,
        project_id: str = None,
        model: str = None,
        prompt: Optional[str] = None,
        limite_caracteres: int = None,
    ):
        """
        Args:
            api_key: Clé API Google Gemini
            project_id: ID du projet Google Cloud (défaut depuis config.yaml)
            model: Nom du modèle à utiliser (défaut depuis config.yaml)
            prompt: Prompt système à envoyer avant l'article
            limite_caracteres: Limite de caractères pour l'article (défaut depuis config.yaml)
        """
        # Load defaults from config.yaml
        import yaml
        default_project_id = "804175778135"
        default_model = "gemini-flash-lite-latest"
        default_limit = LIMITE_CARACTERES
        api_url_template = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        try:
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config:
                        if 'ai' in config and 'gemini' in config['ai']:
                            if 'project_id' in config['ai']['gemini']:
                                default_project_id = config['ai']['gemini']['project_id']
                            if 'model' in config['ai']['gemini']:
                                default_model = config['ai']['gemini']['model']
                            if 'limit' in config['ai']['gemini']:
                                default_limit = config['ai']['gemini']['limit']
                        if 'api_urls' in config and 'gemini' in config['api_urls']:
                            api_url_template = config['api_urls']['gemini']
                        if 'other' in config and 'character_limit' in config['other']:
                            default_limit = config['other']['character_limit']
        except Exception:
            pass
        
        self.api_key = api_key
        self.project_id = project_id or default_project_id
        self.model = model or default_model
        self.prompt = prompt or self._default_prompt()
        self.limite_caracteres = limite_caracteres or default_limit
        self.base_url = api_url_template.format(model=self.model)
        self.api_timeout = 10
        self.temperature = 0.1  # Température basse pour tâche déterministe de correction
        
        # Configuration des réessais avec délai exponentiel
        self.max_retries = 3
        self.retry_delay = 2  # délai initial en secondes
        self.retry_backoff_factor = 2  # facteur multiplicatif pour le délai
        
        # Load timeout from config.yaml
        try:
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and 'timeouts' in config and 'gemini_api' in config['timeouts']:
                        self.api_timeout = config['timeouts']['gemini_api']
                    # Charger les paramètres de réessai depuis la config
                    if config and 'api_throttling' in config:
                        if 'max_retries' in config['api_throttling']:
                            self.max_retries = config['api_throttling']['max_retries']
                        if 'retry_delay' in config['api_throttling']:
                            self.retry_delay = config['api_throttling']['retry_delay']
                        if 'retry_backoff_factor' in config['api_throttling']:
                            self.retry_backoff_factor = config['api_throttling']['retry_backoff_factor']
        except Exception:
            pass
        
    def _default_prompt(self) -> str:
        """Prompt par défaut pour la correction typographique."""
        return """Tu es un correcteur typographique expert pour Wikipédia en français (WP:CT, WP:TYPO).

Corrige uniquement la typographie : espaces insécables (U+00A0 avant ; : ? ! » et
après «), espace fine insécable U+202F pour les séparateurs de milliers (jamais
U+00A0 à cet usage), tiret demi-cadratin – sans espace pour les intervalles
numériques (1914–1918, p. 12–18), tiret cadratin — uniquement si déjà présent dans
le texte original. Ne jamais toucher aux traits d'union internes aux mots
(Jean-Pierre). Aucune autre insertion ou remplacement d'espace ou de tiret n'est
autorisé.

Diff minimal : chaque caractère modifié doit être justifié par une règle explicite
ci-dessus ; toute autre modification est interdite. Ne corrige jamais une même zone
deux fois. Si aucune correction autorisée n'est nécessaire, renvoie le wikicode
strictement identique à l'entrée, caractère pour caractère. Ne jamais reformuler
une phrase ni remplacer un mot par un synonyme.

Ne jamais modifier, sous aucun prétexte, y compris la casse :
- le sens du texte
- le contenu des <ref>...</ref>
- les liens [[...]], externes [https://...] (y compris URLs, même casse ou
  encodage inhabituels)
- le contenu des modèles {{...}}, y compris leur ponctuation interne
- les lignes [[Catégorie:...]] et {{Portail|...}}
- le contenu des commentaires <!-- ... -->
- le contenu de <syntaxhighlight>, <source>, <code>, <math>, <nowiki>, <pre>,
  <gallery>, <timeline>, <graph>, <includeonly>, <noinclude>, <onlyinclude>
- la structure des tableaux wiki ({| ... |})
- les bandeaux de maintenance (ex: {{Référence nécessaire}}, {{À sourcer}},
  {{À vérifier}}, {{À recycler}}, {{À wikifier}}, etc.) — ne jamais les
  supprimer ni les altérer
- ne jamais ajouter de source ou de <ref>

En cas de conflit entre deux règles, la préservation intégrale du wikicode
prévaut toujours sur la correction typographique. Si tu détectes une ambiguïté ou
un risque de modifier autre chose que la typographie autorisée, renvoie le texte
inchangé. Un article non corrigé vaut toujours mieux qu'un article tronqué ou
corrompu.

Interdits absolus :
- ne duplique aucun mot, balise, section
- le nombre d'occurrences de {{ }}, [[ ]], <ref>, </ref> doit rester strictement
  identique
- n'introduis aucun caractère hors espaces/tirets autorisés
- ne tronque jamais le texte : traite l'article en entier, du premier au dernier
  caractère
- aucun markdown, aucun texte avant/après/au milieu du wikicode : ni
  introduction, ni résumé, ni excuse, ni formule du type "Voici le wikicode
  corrigé", "J'espère que...", "Note :" — rien, jamais

Avant de répondre, vérifie que : aucune ligne n'a disparu ni été ajoutée ; tous
les modèles, liens et <ref> sont équilibrés ; ta réponse commence exactement au
premier caractère de l'entrée et se termine exactement à son dernier caractère.

FORMAT DE RÉPONSE : uniquement le wikicode complet, rien d'autre."""
    
    def verifier_longueur(self, article: str) -> Tuple[bool, int]:
        """
        Vérifie si l'article respecte la limite de caractères.
        
        Args:
            article: Contenu de l'article
            
        Returns:
            (ok, nombre_caracteres) - True si OK, False si trop long
        """
        return verifier(article, self.limite_caracteres)
    
    def update_limite_caracteres(self, new_limit: int):
        """
        Met à jour la limite de caractères pour l'analyse.
        
        Args:
            new_limit: Nouvelle limite de caractères
        """
        self.limite_caracteres = new_limit
    
    def _appeler_api_avec_retry(self, payload: dict, timeout: int) -> requests.Response:
        """
        Appelle l'API Gemini avec logique de réessai et délai exponentiel.
        
        Args:
            payload: Payload JSON à envoyer à l'API
            timeout: Timeout pour la requête
            
        Returns:
            Response object
            
        Raises:
            requests.exceptions.RequestException: Si tous les essais échouent
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}?key={self.api_key}",
                    json=payload,
                    timeout=(30, timeout),  # 30s pour connexion, timeout calculé pour lecture
                )
                response.raise_for_status()
                return response
                
            except requests.exceptions.HTTPError as e:
                last_exception = e
                status_code = e.response.status_code if hasattr(e, 'response') and e.response else None
                
                # Réessayer uniquement pour les erreurs 503, 502, 504 (erreurs de serveur temporaires)
                # et 429 (rate limiting)
                if status_code in [503, 502, 504, 429]:
                    if attempt < self.max_retries - 1:  # Ne pas attendre après le dernier essai
                        delay = self.retry_delay * (self.retry_backoff_factor ** attempt)
                        logger.warning(f"Erreur {status_code} - Tentative {attempt + 1}/{self.max_retries}. "
                                     f"Nouvel essai dans {delay}s...")
                        time.sleep(delay)
                        continue
                else:
                    # Pour les autres erreurs HTTP, ne pas réessayer
                    raise
                    
            except (requests.exceptions.ConnectionError, 
                   requests.exceptions.Timeout) as e:
                last_exception = e
                if attempt < self.max_retries - 1:  # Ne pas attendre après le dernier essai
                    delay = self.retry_delay * (self.retry_backoff_factor ** attempt)
                    logger.warning(f"Erreur de connexion - Tentative {attempt + 1}/{self.max_retries}. "
                                 f"Nouvel essai dans {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    raise
        
        # Si on arrive ici, tous les essais ont échoué
        raise last_exception
    
    def _valider_sortie_ia(self, original: str, corrected: str) -> tuple[bool, str]:
        """
        P0 CRITICAL FIX: Valide que la sortie IA est du wikicode valide.
        
        Args:
            original: Article original
            corrected: Article corrigé par l'IA
            
        Returns:
            (is_valid, error_message) - True si la sortie est valide
        """
        # Vérifier que la réponse n'est pas vide
        if not corrected or not corrected.strip():
            return False, "Réponse IA vide"
        
        # Vérifier que la réponse n'est pas identique à l'original (mais ne bloque pas, peut être correct)
        if corrected == original:
            logger.info("Réponse IA identique à l'original (pas de corrections nécessaires)")
            return True, ""
        
        # Vérifier que la réponse n'est pas beaucoup plus longue que l'original
        len_original = len(original)
        len_corrected = len(corrected)
        
        if len_corrected > len_original * 2:
            return False, f"Réponse IA trop longue ({len_corrected} vs {len_original} originaux)"
        
        if len_corrected < len_original / 2:
            return False, f"Réponse IA trop courte ({len_corrected} vs {len_original} originaux)"
        
        # Vérifier que les délimiteurs de modèles sont équilibrés
        template_count_original = original.count('{{') + original.count('}}')
        template_count_corrected = corrected.count('{{') + corrected.count('}}')
        
        if template_count_original != template_count_corrected:
            return False, f"Déséquilibre des modèles ({template_count_original} vs {template_count_corrected})"
        
        # Vérifier que les liens sont équilibrés
        link_count_original = original.count('[[') + original.count(']]')
        link_count_corrected = corrected.count('[[') + corrected.count(']]')
        
        if link_count_original != link_count_corrected:
            return False, f"Déséquilibre des liens ({link_count_original} vs {link_count_corrected})"
        
        # Vérifier que les références sont équilibrées
        ref_count_original = original.count('<ref') + original.count('</ref>')
        ref_count_corrected = corrected.count('<ref') + corrected.count('</ref>')
        
        if ref_count_original != ref_count_corrected:
            return False, f"Déséquilibre des références ({ref_count_original} vs {ref_count_corrected})"
        
        # Vérifier que les catégories sont équilibrées
        cat_count_original = original.count('[[Catégorie:') + original.count('[[Category:')
        cat_count_corrected = corrected.count('[[Catégorie:') + corrected.count('[[Category:')
        
        if cat_count_original != cat_count_corrected:
            return False, f"Déséquilibre des catégories ({cat_count_original} vs {cat_count_corrected})"
        
        # Vérifier l'absence de patterns suspects (instructions système)
        patterns_suspects = [
            r'Voici.*réponse',
            r'Changes made',
            r'Here is',
            r'I will',
            r'My correction',
        ]
        
        import re
        for pattern in patterns_suspects:
            if re.search(pattern, corrected, re.IGNORECASE):
                return False, f"Pattern suspect détecté: {pattern}"
        
        return True, ""
    
    def corriger_article(self, article: str) -> Tuple[bool, str, Optional[str]]:
        """
        Envoie l'article au modèle Gemini pour correction.

        Args:
            article: Contenu de l'article à corriger

        Returns:
            (succes, article_corrige, erreur) - True si succès, False sinon
        """
        # Vérifier la longueur d'abord
        ok, nb_caracteres = self.verifier_longueur(article)
        if not ok:
            log_lia_operation("unknown", "erreur", {"reason": f"Article trop long ({nb_caracteres} caractères, limite = {self.limite_caracteres})"})
            return False, "", f"Article trop long ({nb_caracteres} caractères, limite = {self.limite_caracteres})"

        # Calculer le timeout en fonction des paliers
        timeout = calculer_timeout(nb_caracteres)
        logger.info(f"Timeout calculé: {timeout}s pour {nb_caracteres} caractères")
        log_lia_operation("unknown", "correction_start", {"caracteres": nb_caracteres, "timeout": timeout, "model": self.model})

        # Construire le prompt complet
        full_prompt = f"{self.prompt}\n\n=== ARTICLE À CORRIGER ===\n{article}\n=== FIN DE L'ARTICLE ===\n\nWikicode corrigé :"

        try:
            # Préparer la requête pour Gemini API
            payload = {
                "contents": [{
                    "parts": [{
                        "text": full_prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": 8192,
                }
            }
            
            # Appeler l'API avec logique de réessai
            response = self._appeler_api_avec_retry(payload, timeout)

            data = response.json()
            
            # Extraire la réponse de Gemini
            if "candidates" in data and len(data["candidates"]) > 0:
                article_corrige = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                logger.error("Réponse Gemini sans contenu")
                log_lia_operation("unknown", "erreur_reponse", {"reason": "Réponse sans contenu"})
                return False, "", "Réponse Gemini sans contenu"

            # Nettoyer la réponse (enlever les éventuels commentaires du modèle)
            try:
                article_corrige = self._nettoyer_reponse(article_corrige)
            except ValueError as e:
                logger.warning(f"Réponse rejetée: {e}")
                log_lia_operation("unknown", "rejet_reponse", {"reason": str(e)})
                return False, "", f"Réponse rejetée: {e}"

            # Vérifier la fidélité du texte utile
            fidelite_ok = verifier_fidelite(article, article_corrige)
            if not fidelite_ok:
                logger.warning("Fidélité insuffisante")
                log_lia_operation("unknown", "fidelite_insuffisante", {})
                return False, "", "Fidélité insuffisante"
            
            # P0 CRITICAL FIX: Valider la sortie IA avant de la retourner
            is_valid, validation_error = self._valider_sortie_ia(article, article_corrige)
            if not is_valid:
                logger.error(f"VALIDATION IA ÉCHOUÉE: {validation_error}")
                log_lia_operation("unknown", "validation_failed", {"reason": validation_error})
                return False, "", f"Validation IA échouée: {validation_error}"
            logger.info("Validation IA réussie")

            logger.info(f"Correction réussie avec Gemini")
            log_lia_operation("unknown", "correction_success", {"model": self.model, "caracteres_sortie": len(article_corrige)})
            return True, article_corrige, None

        except requests.exceptions.RequestException as e:
            logger.warning(f"Erreur avec Gemini: {e}")
            log_lia_operation("unknown", "erreur_connexion", {"error": str(e)})
            return False, "", f"Erreur de connexion à Gemini: {e}"
        except json.JSONDecodeError as e:
            logger.warning(f"Erreur de décodage JSON avec Gemini: {e}")
            log_lia_operation("unknown", "erreur_json", {"error": str(e)})
            return False, "", f"Erreur de réponse Gemini: {e}"
    
    def _nettoyer_reponse(self, reponse: str) -> str:
        """
        Nettoie la réponse du modèle pour extraire uniquement le wikicode.
        Extrait le wikicode si du markdown est présent, supprime les lignes de commentaire.

        Args:
            reponse: Réponse brute du modèle

        Returns:
            Wikicode nettoyé

        Raises:
            ValueError: Si la réponse contient des commentaires explicites
        """
        import re

        # Nettoyer automatiquement les lignes de préambule courantes
        # au lieu de rejeter toute la réponse
        preamble_patterns = [
            r'^(Voici|Correction|Voici le|Correction du|Le wikicode|Wikicode corrigé|Résultat|Réponse|C\'est tout|Fin|Voici le wikicode corrigé|Voici la correction)\s*:?.*\n',
            r'^(Voici|Correction|Voici le|Correction du|Le wikicode|Wikicode corrigé|Résultat|Réponse|C\'est tout|Fin|Voici le wikicode corrigé|Voici la correction)\s*:?.*$'
        ]
        
        original_length = len(reponse)
        for pattern in preamble_patterns:
            reponse = re.sub(pattern, '', reponse, flags=re.MULTILINE)
        
        if len(reponse) != original_length:
            logger.info(f"Lignes de préambule supprimées automatiquement ({original_length - len(reponse)} caractères)")
        
        # Nettoyer les balises spécifiques <<<WIKICODE_START>>> et <<<WIKICODE_END>>>
        reponse = re.sub(r'<<<WIKICODE_START>>>', '', reponse, flags=re.IGNORECASE)
        reponse = re.sub(r'<<<WIKICODE_END>>>', '', reponse, flags=re.IGNORECASE)
        
        # Vérifier si la réponse ne contient que des commentaires (rejet)
        if not reponse.strip():
            raise ValueError("La réponse ne contient que des commentaires, aucun wikicode")

        # Si du markdown est présent, extraire le wikicode entre les balises
        if "```" in reponse:
            # Chercher le contenu entre ``` et ```
            match = re.search(r'```(?:wikicode|wikipedia|mediawiki)?\s*\n(.*?)\n```', reponse, re.DOTALL)
            if match:
                wikicode = match.group(1)
                logger.info(f"Wikicode extrait du markdown ({len(wikicode)} caractères)")
                return self._nettoyer_lignes_commentaire(wikicode.strip())
            # Si pas de balises fermantes, essayer d'extraire après la première balise
            match = re.search(r'```(?:wikicode|wikipedia|mediawiki)?\s*\n(.*)', reponse, re.DOTALL)
            if match:
                wikicode = match.group(1)
                logger.info(f"Wikicode extrait après balise markdown ({len(wikicode)} caractères)")
                return self._nettoyer_lignes_commentaire(wikicode.strip())
            # Si toujours pas, supprimer toutes les balises markdown
            wikicode = re.sub(r'```(?:wikicode|wikipedia|mediawiki)?\s*\n?', '', reponse)
            logger.info(f"Balises markdown supprimées ({len(wikicode)} caractères)")
            return self._nettoyer_lignes_commentaire(wikicode.strip())

        # Si pas de markdown, nettoyer les lignes de commentaire et retourner
        return self._nettoyer_lignes_commentaire(reponse.strip())

    def _nettoyer_lignes_commentaire(self, wikicode: str) -> str:
        """
        Supprime les lignes de commentaire au début et à la fin du wikicode.

        Args:
            wikicode: Wikicode potentiellement avec des lignes de commentaire

        Returns:
            Wikicode nettoyé
        """
        lignes = wikicode.split("\n")
        wikicode_nettoye = []

        # Patterns de début de wikicode valide
        debut_patterns = ["{{", "[[", "'''", "==", "*", ";", "#", "|", "<", "!"]

        # Trouver le début du wikicode
        debut_trouve = False
        for ligne in lignes:
            ligne_stripped = ligne.strip()
            if not debut_trouve:
                # Ignorer les lignes de commentaire
                if ligne_stripped.startswith(("#", "//")):
                    continue
                # Ignorer les lignes vides
                if not ligne_stripped:
                    continue
                # Vérifier si c'est du wikicode valide
                if any(ligne_stripped.startswith(p) for p in debut_patterns):
                    debut_trouve = True
                    wikicode_nettoye.append(ligne)
                else:
                    # Si ça ressemble à du commentaire, ignorer
                    if any(mot in ligne_stripped.lower() for mot in ["diff", "correction", "wikicode", "résultat"]):
                        continue
                    # Sinon, considérer comme début du wikicode
                    debut_trouve = True
                    wikicode_nettoye.append(ligne)
            else:
                wikicode_nettoye.append(ligne)

        # Retourner le wikicode nettoyé
        return "\n".join(wikicode_nettoye).strip()
    
    def tester_connexion(self) -> Tuple[bool, Optional[str]]:
        """
        Teste la connexion à l'API Gemini.
        
        Returns:
            (ok, erreur) - True si connexion OK, False sinon
        """
        try:
            # Test simple avec une requête minimale
            payload = {
                "contents": [{
                    "parts": [{
                        "text": "Test"
                    }]
                }]
            }
            
            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                json=payload,
                timeout=self.api_timeout,
            )
            response.raise_for_status()
            return True, None
        except requests.exceptions.RequestException as e:
            return False, f"Impossible de connecter à Gemini: {e}"
