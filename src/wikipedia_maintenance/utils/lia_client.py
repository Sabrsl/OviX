"""
Client pour l'intégration avec LIA/Ollama pour le traitement d'articles Wikipédia.

Ce module permet d'envoyer un article à un modèle LIA/Ollama avec un prompt
spécifique, en vérifiant d'abord la longueur de l'article par regex.
"""

import requests
import json
from typing import Optional, Tuple
from pathlib import Path
import logging

from .verif_longueur import verifier, LIMITE_CARACTERES, calculer_timeout, verifier_fidelite
from .lia_logger import log_lia_operation

logger = logging.getLogger(__name__)


class LIAOllamaClient:
    """Client pour communiquer avec Ollama/LIA pour le traitement d'articles."""
    
    def __init__(
        self,
        base_url: str = None,
        model: str = None,
        fallback_model: str = None,
        prompt: Optional[str] = None,
        limite_caracteres: int = None,
    ):
        """
        Args:
            base_url: URL du serveur Ollama (défaut depuis config.yaml ou http://localhost:11434)
            model: Nom du modèle principal à utiliser (défaut depuis config.yaml ou mistral:instruct)
            fallback_model: Nom du modèle de fallback (défaut depuis config.yaml ou llama3:instruct)
            prompt: Prompt système à envoyer avant l'article
            limite_caracteres: Limite de caractères pour l'article
        """
        # Load defaults from config.yaml
        import yaml
        default_base_url = "http://localhost:11434"
        default_model = "mistral:instruct"
        default_fallback = "llama3:instruct"
        default_limit = LIMITE_CARACTERES
        
        try:
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config:
                        if 'ai' in config and 'ollama' in config['ai']:
                            if 'url' in config['ai']['ollama']:
                                default_base_url = config['ai']['ollama']['url']
                            if 'model' in config['ai']['ollama']:
                                default_model = config['ai']['ollama']['model']
                            if 'fallback' in config['ai']['ollama']:
                                default_fallback = config['ai']['ollama']['fallback']
                        if 'other' in config and 'character_limit' in config['other']:
                            default_limit = config['other']['character_limit']
        except Exception:
            pass
        
        self.base_url = (base_url or default_base_url).rstrip("/")
        self.model = model or default_model
        self.fallback_model = fallback_model or default_fallback
        self.prompt = prompt or self._default_prompt()
        self.limite_caracteres = limite_caracteres or default_limit
        self.api_timeout = 10
        self.temperature = 0.1  # Température basse pour tâche déterministe de correction
        
        # Load timeout from config.yaml
        try:
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and 'timeouts' in config and 'ollama_api' in config['timeouts']:
                        self.api_timeout = config['timeouts']['ollama_api']
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
    
    def corriger_article(self, article: str) -> Tuple[bool, str, Optional[str]]:
        """
        Envoie l'article au modèle LIA/Ollama pour correction.
        Essaie d'abord le modèle principal, puis le fallback en cas d'échec.

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

        # Essayer d'abord le modèle principal
        for model_to_try in [self.model, self.fallback_model]:
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model_to_try,
                        "prompt": full_prompt,
                        "stream": False,
                        "temperature": self.temperature,
                    },
                    timeout=timeout,
                )
                response.raise_for_status()

                data = response.json()
                article_corrige = data.get("response", "").strip()

                # Nettoyer la réponse (enlever les éventuels commentaires du modèle)
                try:
                    article_corrige = self._nettoyer_reponse(article_corrige)
                except ValueError as e:
                    logger.warning(f"Réponse rejetée pour le modèle {model_to_try}: {e}")
                    log_lia_operation("unknown", "rejet_reponse", {"model": model_to_try, "reason": str(e)})
                    # Continuer avec le modèle de fallback
                    continue

                # Vérifier la fidélité du texte utile
                fidelite_ok = verifier_fidelite(article, article_corrige)
                if not fidelite_ok:
                    logger.warning(f"Fidélité insuffisante pour le modèle {model_to_try}, tentative avec fallback")
                    log_lia_operation("unknown", "fidelite_insuffisante", {"model": model_to_try})
                    # Continuer avec le modèle de fallback
                    continue

                logger.info(f"Correction réussie avec le modèle: {model_to_try}")
                log_lia_operation("unknown", "correction_success", {"model": model_to_try, "caracteres_sortie": len(article_corrige)})
                return True, article_corrige, None

            except requests.exceptions.RequestException as e:
                logger.warning(f"Erreur avec le modèle {model_to_try}: {e}")
                log_lia_operation("unknown", "erreur_connexion", {"model": model_to_try, "error": str(e)})
                if model_to_try == self.fallback_model:
                    # Dernier essai échoué
                    logger.error(f"Tous les modèles ont échoué")
                    log_lia_operation("unknown", "erreur_finale", {"reason": "Tous les modèles ont échoué", "error": str(e)})
                    return False, "", f"Erreur de connexion à Ollama (modèles {self.model} et {self.fallback_model} échoués): {e}"
                # Continuer avec le modèle de fallback
                continue
            except json.JSONDecodeError as e:
                logger.warning(f"Erreur de décodage JSON avec le modèle {model_to_try}: {e}")
                log_lia_operation("unknown", "erreur_json", {"model": model_to_try, "error": str(e)})
                if model_to_try == self.fallback_model:
                    # Dernier essai échoué
                    logger.error(f"Tous les modèles ont échoué")
                    log_lia_operation("unknown", "erreur_finale", {"reason": "Erreur de décodage JSON", "error": str(e)})
                    return False, "", f"Erreur de réponse Ollama (modèles {self.model} et {self.fallback_model} échoués): {e}"
                # Continuer avec le modèle de fallback
                continue
    
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

        # Vérifier si la réponse contient des commentaires explicites (rejet)
        commentaire_patterns = ["Voici", "Correction", "Voici le", "Correction du", "Le wikicode", "Wikicode corrigé", "Résultat", "Réponse", "C'est tout", "Fin", "Voici le wikicode corrigé", "Voici la correction"]
        for pattern in commentaire_patterns:
            if pattern in reponse:
                raise ValueError(f"La réponse contient des commentaires (pattern: '{pattern}')")

        # Nettoyer les balises spécifiques <<<WIKICODE_START>>> et <<<WIKICODE_END>>> (au cas où le modèle les ajoute quand même)
        reponse = re.sub(r'<<<WIKICODE_START>>>', '', reponse, flags=re.IGNORECASE)
        reponse = re.sub(r'<<<WIKICODE_END>>>', '', reponse, flags=re.IGNORECASE)

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
        Teste la connexion au serveur Ollama.
        
        Returns:
            (ok, erreur) - True si connexion OK, False sinon
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=self.api_timeout)
            response.raise_for_status()
            return True, None
        except requests.exceptions.RequestException as e:
            return False, f"Impossible de connecter à Ollama ({self.base_url}): {e}"
