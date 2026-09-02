"""
Case Normalization Module for Wikipedia Reference Templates.

This module normalizes the case (capitalization) of specific parameters
in Wikipedia reference templates ({{Lien web}}, {{Article}}, {{Ouvrage}},
{{Lien brisé}}).

It runs BEFORE any dead-link/archiving processing and can be independently
enabled/disabled via UI settings.

TARGET PARAMETERS (only these):
- titre=
- site=
- éditeur=
- auteur= / nom= / prénom=

SAFETY CONSTRAINTS (hard rules, never relaxed):
- Never modify URL parameters (case-sensitive)
- Never modify template structure or parameter order
- Never add or remove parameters
- Never touch any parameter outside TARGET_PARAMETERS
- Be idempotent (running twice produces no additional changes)
- When in doubt, skip modification and log as ignored

DESIGN NOTE ON PROPER-NAME DETECTION
-------------------------------------
Detecting "this is a proper name" purely from capitalization patterns in
free text is fundamentally ambiguous: an all-caps sentence ("LE ROI DE
FRANCE") and an all-caps proper name ("RACHIDA BELKACEM") are visually
identical to a word-length heuristic. No length threshold resolves this
correctly in all cases.

Rather than guessing, this module treats proper-name preservation as a
*known-data* problem: names are preserved when they match curated
reference data (official_names, domain_to_site_name) or well-defined
structural signals (e.g. the value of an `auteur=`/`nom=`/`prénom=`
parameter is *always* treated as a person's name, never as a sentence,
because that is what the parameter means on Wikipedia). For `titre=`,
where free-text ambiguity is unavoidable, the module is conservative:
it only fully normalizes text that is unambiguously all-uppercase or
all-lowercase, and leaves already-mixed-case text untouched rather than
risk corrupting a legitimate title.
"""

from __future__ import annotations

import re
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Data classes
# ----------------------------------------------------------------------


@dataclass
class NormalizationReport:
    """Report of normalization changes for a single reference template."""
    template_name: str
    parameter_changes: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # param: (before, after)
    ignored_occurrences: List[Tuple[str, str]] = field(default_factory=list)  # (param, reason)


@dataclass
class NormalizationResult:
    """Result of a case-normalization pass over a whole page of wikitext."""
    normalized_text: str
    reports: List[NormalizationReport] = field(default_factory=list)
    total_changes: int = 0
    total_ignored: int = 0


# ----------------------------------------------------------------------
# CaseNormalizer
# ----------------------------------------------------------------------


class CaseNormalizer:
    """
    Normalizes case for Wikipedia reference template parameters.

    Follows French typographic conventions while preserving:
    - Acronyms (ONU, USA, etc.)
    - Known official names (companies, media outlets, institutions)
    - Person names in auteur=/nom=/prénom= (always treated as names)
    - URLs and identifiers (never modified)
    - Parameters not in the target list (never touched)

    Reference data is loaded from case_normalization_data.yaml so it can be
    maintained without touching code.
    """

    # Parameters that should be normalized. Matching is done on the
    # normalized key (lowercased, trailing digit stripped) so that
    # auteur1=, auteur2=, nom3=, prénom2= etc. are all covered without
    # having to enumerate every numbered variant by hand.
    TARGET_PARAMETER_BASES = {
        'titre',
        'site',
        'éditeur', 'editeur', 'publisher',
        'auteur',
        'auteur prénom', 'auteur nom',
        'nom', 'prénom', 'prenom',
    }

    # Parameters to NEVER modify (URLs, identifiers, and anything where
    # case is semantically significant or where altering it could break
    # a link or a lookup).
    PROTECTED_PARAMETERS = {
        'url', 'archive-url', 'archiveurl', 'lire en ligne', 'url texte',
        'lien', 'doi', 'isbn', 'issn', 'oclc', 'pmid', 'pmcid', 'arxiv',
        'bibcode', 'jstor', 'hdl', 's2cid', 'wikidata', 'id',
    }

    # Known template names this module operates on (case-insensitive,
    # underscores treated as spaces).
    KNOWN_TEMPLATES = {
        'lien web': 'Lien web',
        'article': 'article',
        'ouvrage': 'ouvrage',
        'lien brisé': 'Lien brisé',
        'lien archive': 'Lien archive',
    }

    # A value is only ever fully rewritten to sentence/title case when it
    # is unambiguously ALL-UPPERCASE or all-lowercase. Anything already
    # mixed-case is left untouched (see design note above) — this is the
    # single biggest source of robustness against corrupting legitimate
    # titles that happen to contain proper names, acronyms, or foreign
    # words we don't have curated data for.
    _MIN_ALPHA_CHARS_TO_JUDGE = 2  # below this, casing is undecidable (e.g. "A", "?")

    def __init__(self, enabled: bool = True, config_path: Optional[str] = None, enable_ner_title_normalization: bool = False, normalize_with_ai: bool = False):
        """
        Args:
            enabled: If False, all normalization is skipped (text returned as-is).
            config_path: Path to the YAML config file. If None, uses the default path.
            enable_ner_title_normalization: If True, use spaCy NER to detect person names in titles.
            normalize_with_ai: If True, use Gemini AI for additional normalization (only if enabled=True).
        """
        self.enabled = enabled
        self.enable_ner_title_normalization = enable_ner_title_normalization
        self.normalize_with_ai = normalize_with_ai
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._load_reference_data(config_path)
        
        # Lazy-loading for spaCy NER model
        self._nlp = None
        self._spacy_available = False
        self._spacy_warning_logged = False
        
        # Lazy-loading for Gemini client
        self._gemini_client = None
        self._gemini_available = False
        self._gemini_warning_logged = False
        
        if self.enable_ner_title_normalization:
            self._load_spacy_model()
        
        if self.normalize_with_ai:
            self._load_gemini_client()

    # -- Reference data loading -----------------------------------------

    def _load_reference_data(self, config_path: Optional[str] = None) -> None:
        """
        Load reference data from the YAML configuration file.

        If the file is missing or malformed, normalization is disabled
        entirely for this instance rather than running with empty (and
        therefore unsafe) reference sets.
        """
        if config_path is None:
            project_root = Path(__file__).parent.parent.parent.parent
            config_path = project_root / "config" / "case_normalization_data.yaml"
        self._config_path = Path(config_path)

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            if not isinstance(data, dict):
                raise ValueError("Reference data file must contain a YAML mapping at the top level")

            self.common_acronyms = self._as_str_set(data.get('acronyms', []))
            self.official_names = self._as_str_set(data.get('official_names', []))
            self.particles = {p.lower() for p in self._as_str_set(data.get('particles', []))}
            self.preserved_expressions = self._as_str_set(data.get('preserved_expressions', []))
            self.domain_to_site_name = {
                str(k): str(v) for k, v in (data.get('domain_to_site_name', {}) or {}).items()
            }

            # Pre-sort longer official names / expressions first so that
            # substring containment checks prefer the most specific match
            # (e.g. "Radio France Internationale" before "France").
            self._official_names_sorted = sorted(self.official_names, key=len, reverse=True)
            self._preserved_expressions_sorted = sorted(self.preserved_expressions, key=len, reverse=True)

            self._logger.info(f"Loaded reference data from {self._config_path}")
            self._logger.debug(
                f"Acronyms: {len(self.common_acronyms)}, "
                f"Official names: {len(self.official_names)}, "
                f"Particles: {len(self.particles)}, "
                f"Preserved expressions: {len(self.preserved_expressions)}, "
                f"Domain mappings: {len(self.domain_to_site_name)}"
            )
        except FileNotFoundError:
            self._logger.error(
                f"Config file not found at {self._config_path}. Disabling case normalization for safety."
            )
            self._disable_with_empty_data()
        except Exception as e:
            self._logger.error(
                f"Failed to load reference data from {self._config_path}: {e}. "
                f"Disabling case normalization for safety."
            )
            self._disable_with_empty_data()

    def _disable_with_empty_data(self) -> None:
        self.enabled = False
        self.common_acronyms = set()
        self.official_names = set()
        self.particles = set()
        self.preserved_expressions = set()
        self.domain_to_site_name = {}
        self._official_names_sorted = []
        self._preserved_expressions_sorted = []

    @staticmethod
    def _as_str_set(items) -> set:
        if not isinstance(items, (list, set, tuple)):
            return set()
        return {str(item).strip() for item in items if str(item).strip()}

    def reload_reference_data(self, config_path: Optional[str] = None) -> None:
        """Reload reference data without restarting the application."""
        self._logger.info("Reloading reference data...")
        self._load_reference_data(config_path or self._config_path)
        self._logger.info("Reference data reloaded successfully")

    # -- spaCy NER loading -----------------------------------------------

    def _load_spacy_model(self) -> None:
        """
        Load spaCy French NER model for person name detection.
        
        Logs a warning once if spaCy or the model is not available,
        and degrades gracefully to the current behavior (ignoring all-caps titles).
        """
        try:
            import spacy
            try:
                self._nlp = spacy.load("fr_core_news_sm")
                self._spacy_available = True
                self._logger.info("spaCy NER model 'fr_core_news_sm' loaded successfully for title normalization")
            except OSError:
                # Model not installed
                if not self._spacy_warning_logged:
                    self._logger.warning(
                        "spaCy NER model 'fr_core_news_sm' not found. "
                        "Install it with: python -m spacy download fr_core_news_sm. "
                        "Falling back to conservative behavior (ignoring all-caps titles)."
                    )
                    self._spacy_warning_logged = True
        except ImportError:
            if not self._spacy_warning_logged:
                self._logger.warning(
                    "spaCy not installed. Install it with: pip install spacy. "
                    "Falling back to conservative behavior (ignoring all-caps titles)."
                )
                self._spacy_warning_logged = True

    def _load_gemini_client(self) -> None:
        """
        Load Gemini client for AI-assisted normalization.

        Logs a warning once if Gemini is not available,
        and degrades gracefully to classical normalization only.
        """
        try:
            from wikipedia_maintenance.utils.gemini_client import GeminiClient
            import os
            import yaml

            # Load API key from environment variables (.env) first, then config.yaml
            api_key = os.environ.get('GEMINI_API_KEY')
            project_id = os.environ.get('GEMINI_PROJECT_ID')
            model = os.environ.get('GEMINI_MODEL')

            # Fallback to config.yaml if not in .env
            if not api_key:
                config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        if config and 'ai' in config and 'gemini' in config['ai']:
                            api_key = config['ai']['gemini'].get('api_key')
                            if not project_id:
                                project_id = config['ai']['gemini'].get('project_id')
                            if not model:
                                model = config['ai']['gemini'].get('model', 'gemini-flash-lite-latest')
                except Exception as e:
                    self._logger.warning(f"Failed to load Gemini config from config.yaml: {e}")

            if not api_key or api_key == 'null':
                if not self._gemini_warning_logged:
                    self._logger.warning(
                        "Gemini API key not configured in .env or config.yaml. "
                        "AI normalization will be disabled. Falling back to classical normalization."
                    )
                    self._gemini_warning_logged = True
                return

            # Create Gemini client with normalization prompt
            self._gemini_client = GeminiClient(
                api_key=api_key,
                project_id=project_id,
                model=model,
                prompt=self._get_normalization_prompt()
            )
            self._gemini_available = True
            self._logger.info(f"Gemini client loaded successfully for AI normalization (model: {model})")

        except ImportError:
            if not self._gemini_warning_logged:
                self._logger.warning(
                    "Gemini client not available. "
                    "AI normalization will be disabled. Falling back to classical normalization."
                )
                self._gemini_warning_logged = True
        except Exception as e:
            if not self._gemini_warning_logged:
                self._logger.warning(
                    f"Failed to load Gemini client: {e}. "
                    "AI normalization will be disabled. Falling back to classical normalization."
                )
                self._gemini_warning_logged = True

    def _get_normalization_prompt(self) -> str:
        """
        Get the prompt for AI-assisted normalization.
        
        This prompt is specifically designed for conservative normalization
        of Wikipedia reference template parameters, distinct from the
        typographic correction prompt used in the main LIA workflow.
        
        The prompt now requests JSON output for structured, controlled normalization.
        """
        return """Tu es un module de normalisation pour les paramètres de modèles de référence Wikipédia.

Ta tâche UNIQUE est de normaliser la CASSE (majuscules/minuscules) des valeurs de paramètres
dans les modèles de référence Wikipédia ({{Lien web}}, {{Article}}, {{Ouvrage}}, {{Lien brisé}}).

PARAMÈTRES CIBLÉS (uniquement ceux-ci) :
- titre
- site
- éditeur
- auteur
- nom
- prénom

RÈGLES DE NORMALISATION CONSERVATRICES :
1. Conserver le sens original exactement
2. NE JAMAIS inventer d'information
3. NE JAMAIS ajouter d'information non présente dans l'entrée
4. NE JAMAIS supprimer une information simplement parce qu'elle semble inhabituelle
5. Appliquer les conventions typographiques françaises :
   - Noms propres : première lettre en majuscule, reste en minuscules (sauf exceptions connues)
   - Titres d'œuvres : première lettre en majuscule, reste en minuscules (sauf exceptions)
   - Noms d'institutions/entreprises : respecter la graphie officielle connue
6. Préserver les sigles et acronymes connus (ONU, USA, UNESCO, etc.)
7. NE JAMAIS modifier les URLs, identifiants, ou paramètres techniques
8. Si aucune normalisation n'est nécessaire, retourner les valeurs inchangées

INTERDICTIONS ABSOLUES :
- Ne modifier en aucun cas les URLs
- Ne modifier en aucun cas les références
- Ne modifier en aucun cas les catégories
- Ne modifier en aucun cas les liens Wikipédia
- Ne modifier en aucun cas le texte encyclopédique
- Ne modifier aucun autre paramètre de modèle
- Ne jamais ajouter ou supprimer des paramètres
- Ne jamais reformuler une phrase ou remplacer un mot par un synonyme

FORMAT DE RÉPONSE : JSON strict avec les champs suivants uniquement :
{{
  "titre": "valeur normalisée ou inchangée",
  "site": "valeur normalisée ou inchangée",
  "éditeur": "valeur normalisée ou inchangée",
  "auteur": "valeur normalisée ou inchangée",
  "nom": "valeur normalisée ou inchangée",
  "prénom": "valeur normalisée ou inchangée"
}}

Si un champ n'est pas présent dans les données d'entrée, ne l'inclus pas dans le JSON de sortie.
Ne retourne JAMAIS d'autres champs que ceux-ci.
Ne retourne JAMAIS de texte explicatif ou de commentaire.

=== VALEURS À NORMALISER (JSON) ===
{values_json}
=== FIN DES VALEURS ===

JSON normalisé :"""

    def _extract_person_entities(self, text: str) -> List[Tuple[int, int, str]]:
        """
        Extract person name entities from text using spaCy NER.
        
        Args:
            text: The text to analyze (should be in readable mixed case for best NER performance).
            
        Returns:
            List of (start, end, text) tuples for each PER entity detected.
            Returns empty list if spaCy is not available or no entities found.
        """
        if not self._spacy_available or self._nlp is None:
            return []
        
        try:
            doc = self._nlp(text)
            person_entities = []
            for ent in doc.ents:
                if ent.label_ == "PER":  # Person entity in French spaCy model
                    person_entities.append((ent.start_char, ent.end_char, ent.text))
            return person_entities
        except Exception as e:
            self._logger.warning(f"spaCy NER failed on text '{text[:50]}...': {e}")
            return []

    # -- Public entry point ----------------------------------------------

    def normalize_text(self, text: str) -> NormalizationResult:
        """
        Normalize case in reference templates within the given wikitext.
        

        Only the TARGET_PARAMETER_BASES parameters inside recognized
        reference templates are ever modified. Everything else in the
        article — prose, other templates, wikilinks, categories — is
        returned byte-for-byte identical.
        """
        if not self.enabled:
            self._logger.info("Case normalization disabled - returning text as-is")
            return NormalizationResult(normalized_text=text)

        if not text:
            return NormalizationResult(normalized_text=text)

        templates = self._find_reference_templates(text)
        if not templates:
            self._logger.debug("No reference templates found for normalization")
            return NormalizationResult(normalized_text=text)

        normalized_text = text
        reports: List[NormalizationReport] = []
        total_changes = 0
        total_ignored = 0

        # Process in reverse order to maintain valid offsets
        for template_start, template_end, template_name, parameters in reversed(templates):
            report = NormalizationReport(template_name=template_name)
            modified_params: Dict[str, Tuple[str, str]] = {}

            for param_name, param_value in parameters.items():
                base_key = self._parameter_base(param_name)

                if base_key in {self._parameter_base(p) for p in self.PROTECTED_PARAMETERS}:
                    continue  # never touch protected parameters, no matter the name

                if base_key not in self.TARGET_PARAMETER_BASES:
                    continue  # not a parameter this module is allowed to change

                normalized_value, reason = self._normalize_parameter_value(param_value, base_key)

                if normalized_value != param_value:
                    modified_params[param_name.lower()] = (param_value, normalized_value)
                    report.parameter_changes[param_name] = (param_value, normalized_value)
                    total_changes += 1
                elif reason:
                    report.ignored_occurrences.append((param_name, reason))
                    total_ignored += 1

            if modified_params:
                template_text = text[template_start:template_end]
                modified_template = self._rebuild_template(template_text, modified_params)
                if modified_template != template_text:
                    normalized_text = (
                        normalized_text[:template_start]
                        + modified_template
                        + normalized_text[template_end:]
                    )
                else:
                    # _rebuild_template declined the change (e.g. duplicate
                    # parameter safety check) — don't count it as applied.
                    for key in list(modified_params.keys()):
                        old_value, new_value = report.parameter_changes.pop(key, (None, None))
                        if old_value is not None:
                            report.ignored_occurrences.append((key, "template rebuild declined (safety check)"))
                            total_changes -= 1
                            total_ignored += 1

            if report.parameter_changes or report.ignored_occurrences:
                reports.append(report)

        self._logger.info(
            f"Classical case normalization complete: {total_changes} changes, "
            f"{total_ignored} ignored across {len(reports)} templates"
        )

        # Apply AI normalization if enabled and available
        if self.normalize_with_ai and self._gemini_available:
            self._logger.info("AI normalization enabled - applying Gemini normalization")
            normalized_text = self._apply_ai_normalization(normalized_text, text, total_changes)
        elif self.normalize_with_ai and not self._gemini_available:
            self._logger.warning("AI normalization requested but Gemini not available - using classical result only")

        return NormalizationResult(
            normalized_text=normalized_text,
            reports=reports,
            total_changes=total_changes,
            total_ignored=total_ignored,
        )

    def _apply_ai_normalization(self, current_text: str, original_text: str, classical_changes: int) -> str:
        """
        Apply AI-assisted normalization using Gemini with controlled scope.
        
        Args:
            current_text: Text after classical normalization
            original_text: Original text before any normalization
            classical_changes: Number of changes made by classical normalization
            
        Returns:
            Normalized text (AI result if successful, otherwise classical result)
        """
        self._logger.info("ai_normalization_started")
        
        try:
            # Check if there are any changes to normalize
            if current_text == original_text and classical_changes == 0:
                self._logger.info("No changes needed - skipping AI normalization")
                return current_text
            
            # Extract authorized parameter values from templates
            templates = self._find_reference_templates(current_text)
            if not templates:
                self._logger.info("No reference templates found - skipping AI normalization")
                return current_text
            
            # Extract values for AI normalization
            values_to_normalize = self._extract_authorized_values(templates)
            if not values_to_normalize:
                self._logger.info("No authorized parameter values found - skipping AI normalization")
                return current_text
            
            self._logger.debug(f"Values to normalize: {values_to_normalize}")
            
            # Check if values are already properly normalized (classical normalization already handled it)
            # If no values need AI normalization, skip
            needs_ai_normalization = False
            for param_name, param_value in values_to_normalize.items():
                # Check if value is all uppercase or all lowercase (needs normalization)
                if param_value.isupper() or param_value.islower():
                    needs_ai_normalization = True
                    break
            
            if not needs_ai_normalization:
                self._logger.info("Values already properly normalized - skipping AI normalization")
                return current_text
            
            # Convert to JSON for prompt
            import json
            values_json = json.dumps(values_to_normalize, ensure_ascii=False)
            self._logger.debug(f"Values JSON for prompt: {values_json}")
            
            # Update prompt with values
            prompt = self._get_normalization_prompt().format(values_json=values_json)
            
            # Call Gemini with updated prompt
            success, ai_response, error = self._call_gemini_with_custom_prompt(prompt)
            
            if not success:
                self._logger.warning(f"AI normalization failed: {error} - ai_normalization_fallback")
                return current_text
            
            # Parse JSON response
            try:
                # Clean the response to extract JSON only
                cleaned_response = ai_response.strip()
                
                self._logger.debug(f"Raw AI response: {ai_response[:500]}")
                
                # Remove markdown code blocks if present
                if "```" in cleaned_response:
                    # Extract content between ``` and ```
                    import re
                    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', cleaned_response, re.DOTALL)
                    if match:
                        cleaned_response = match.group(1)
                    else:
                        # Fallback: remove all ``` markers
                        cleaned_response = re.sub(r'```(?:json)?\s*', '', cleaned_response)
                        cleaned_response = cleaned_response.replace('```', '')
                
                # Remove any text before the first { or [
                json_start = cleaned_response.find('{')
                if json_start == -1:
                    json_start = cleaned_response.find('[')
                
                if json_start != -1:
                    cleaned_response = cleaned_response[json_start:]
                
                # Remove any text after the last } or ]
                json_end = cleaned_response.rfind('}')
                if json_end == -1:
                    json_end = cleaned_response.rfind(']')
                
                if json_end != -1:
                    cleaned_response = cleaned_response[:json_end + 1]
                
                self._logger.debug(f"Cleaned JSON: {cleaned_response[:500]}")
                
                # Parse the cleaned JSON
                normalized_values = json.loads(cleaned_response)
                
                # Strip whitespace from keys and values
                normalized_values = {k.strip(): v.strip() if isinstance(v, str) else v 
                                    for k, v in normalized_values.items()}
                
                self._logger.debug(f"Parsed normalized values: {normalized_values}")
                
            except json.JSONDecodeError as e:
                self._logger.warning(f"AI normalization JSON parsing failed: {e} - ai_normalization_fallback")
                self._logger.warning(f"AI response that failed parsing: {ai_response[:500]}")
                return current_text
            
            # Validate JSON structure
            is_valid, validation_error = self._validate_ai_json_response(normalized_values, values_to_normalize)
            if not is_valid:
                self._logger.warning(f"AI normalization JSON validation failed: {validation_error} - ai_normalization_fallback")
                return current_text
            
            self._logger.debug("JSON validation passed, proceeding to reinjection")
            
            # Reinject normalized values into text
            final_text = self._reinject_normalized_values(current_text, templates, normalized_values)
            
            self._logger.debug("Reinjection completed, proceeding to scope validation")
            
            # Validate that only authorized parameters changed
            is_safe, safety_error = self._validate_scope_safety(current_text, final_text)
            if not is_safe:
                self._logger.warning(f"AI normalization scope validation failed: {safety_error} - ai_normalization_fallback")
                return current_text
            
            self._logger.info("AI normalization successful - ai_normalization_completed")
            return final_text
            
        except Exception as e:
            self._logger.error(f"AI normalization error: {e} - ai_normalization_fallback")
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
            return current_text

    def _extract_authorized_values(self, templates: List[Tuple[int, int, str, Dict[str, str]]]) -> Dict[str, str]:
        """
        Extract authorized parameter values from reference templates.
        
        Returns a dict mapping parameter names to their values.
        Numbered parameters are included (e.g., auteur1, nom2).
        """
        values = {}
        for _, _, _, parameters in templates:
            for param_name, param_value in parameters.items():
                base_key = self._parameter_base(param_name)
                if base_key in self.TARGET_PARAMETER_BASES:
                    # Use the full parameter name (including number) as key
                    values[param_name] = param_value
        return values

    def _call_gemini_with_custom_prompt(self, prompt: str) -> Tuple[bool, str, Optional[str]]:
        """
        Call Gemini with a custom prompt and return the raw response.
        
        This bypasses the standard corriger_article method to use JSON output.
        """
        try:
            # Check length limit
            ok, nb_caracteres = self._gemini_client.verifier_longueur(prompt)
            if not ok:
                return False, "", f"Prompt too long ({nb_caracteres} characters)"
            
            # Calculate timeout
            from wikipedia_maintenance.utils.verif_longueur import calculer_timeout
            timeout = calculer_timeout(nb_caracteres)
            
            # Prepare request
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": self._gemini_client.temperature,
                    "maxOutputTokens": 8192,
                }
            }
            
            # Call API with retry
            response = self._gemini_client._appeler_api_avec_retry(payload, timeout)
            data = response.json()
            
            # Extract response
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    text = candidate["content"]["parts"][0].get("text", "").strip()
                    return True, text, None
            
            return False, "", "No valid response from Gemini"
            
        except Exception as e:
            return False, "", str(e)

    def _validate_ai_json_response(self, normalized_values: Dict, original_values: Dict) -> Tuple[bool, str]:
        """
        Validate that the AI JSON response only contains authorized fields.
        """
        authorized_fields = {'titre', 'site', 'éditeur', 'auteur', 'nom', 'prénom'}
        
        self._logger.debug(f"Validating AI response: {normalized_values}")
        
        # Check for unexpected fields
        for field in normalized_values.keys():
            # Strip whitespace from field name
            field_clean = field.strip()
            # Allow numbered variants (auteur1, nom2, etc.)
            base_key = self._parameter_base(field_clean)
            if base_key not in authorized_fields:
                self._logger.warning(f"Unauthorized field in AI response: {field_clean} (base: {base_key})")
                return False, f"forbidden_parameter_modified: {field_clean}"
        
        # Check that all values are strings
        for key, value in normalized_values.items():
            if not isinstance(value, str):
                self._logger.warning(f"Invalid value type for {key}: {type(value)}")
                return False, f"invalid_value_type: {key}"
        
        self._logger.debug("AI response validation passed")
        return True, ""

    def _reinject_normalized_values(self, text: str, templates: List[Tuple[int, int, str, Dict[str, str]]],
                                   normalized_values: Dict[str, str]) -> str:
        """
        Reinject normalized values into the text, replacing only authorized parameters.
        """
        result = text
        self._logger.debug(f"Reinjecting normalized values: {normalized_values}")

        # Process in reverse order to maintain valid offsets
        for template_start, template_end, template_name, parameters in reversed(templates):
            modified_params = {}
            self._logger.debug(f"Processing template {template_name} with parameters: {list(parameters.keys())}")

            for param_name, param_value in parameters.items():
                base_key = self._parameter_base(param_name)
                # Try both exact match and case-insensitive match
                if base_key in self.TARGET_PARAMETER_BASES:
                    # Try exact match first
                    if param_name in normalized_values:
                        new_value = normalized_values[param_name]
                        if new_value != param_value:
                            modified_params[param_name.lower()] = (param_value, new_value)
                            self._logger.debug(f"Modifying {param_name}: '{param_value}' -> '{new_value}'")
                    # Try case-insensitive match
                    else:
                        for norm_key, norm_value in normalized_values.items():
                            if norm_key.lower() == param_name.lower():
                                if norm_value != param_value:
                                    modified_params[param_name.lower()] = (param_value, norm_value)
                                    self._logger.debug(f"Modifying {param_name} (case-insensitive): '{param_value}' -> '{norm_value}'")
                                break

            if modified_params:
                template_text = text[template_start:template_end]
                self._logger.debug(f"Rebuilding template with modified params: {modified_params}")
                try:
                    modified_template = self._rebuild_template(template_text, modified_params)
                    if modified_template != template_text:
                        result = (
                            result[:template_start]
                            + modified_template
                            + result[template_end:]
                        )
                except Exception as e:
                    self._logger.warning(f"Template rebuild failed: {e} - skipping this template")
                    continue

        return result

    def _validate_scope_safety(self, before: str, after: str) -> Tuple[bool, str]:
        """
        Validate that only authorized parameters changed between before and after.
        
        This is a deterministic code-level validation, independent of the prompt.
        """
        # Extract URLs before and after
        urls_before = self._extract_urls(before)
        urls_after = self._extract_urls(after)
        
        if urls_before != urls_after:
            return False, "url_modified"
        
        # Extract references before and after
        refs_before = self._extract_references(before)
        refs_after = self._extract_references(after)
        
        if refs_before != refs_after:
            return False, "reference_modified"
        
        # Extract categories before and after
        cats_before = self._extract_categories(before)
        cats_after = self._extract_categories(after)
        
        if cats_before != cats_after:
            return False, "category_modified"
        
        # Extract all parameters before and after
        templates_before = self._find_reference_templates(before)
        templates_after = self._find_reference_templates(after)
        
        # Compare protected parameters
        for _, _, _, params_before in templates_before:
            for param_name, param_value in params_before.items():
                base_key = self._parameter_base(param_name)
                if base_key in {self._parameter_base(p) for p in self.PROTECTED_PARAMETERS}:
                    # This is a protected parameter - should not change
                    # Find corresponding parameter in after
                    found_after = False
                    for _, _, _, params_after in templates_after:
                        if param_name in params_after:
                            if params_after[param_name] != param_value:
                                return False, f"protected_parameter_modified: {param_name}"
                            found_after = True
                            break
        
        return True, ""

    def _extract_urls(self, text: str) -> set:
        """Extract all URLs from text."""
        import re
        url_pattern = r'https?://[^\s<>\}\]]+'
        return set(re.findall(url_pattern, text))

    def _extract_references(self, text: str) -> set:
        """Extract all reference tags from text."""
        import re
        ref_pattern = r'<ref[^>]*>.*?</ref>'
        return set(re.findall(ref_pattern, text, re.DOTALL | re.IGNORECASE))

    def _extract_categories(self, text: str) -> set:
        """Extract all category links from text."""
        import re
        cat_pattern = r'\[\[(?:Catégorie|Category):[^\]]+\]\]'
        return set(re.findall(cat_pattern, text, re.IGNORECASE))

    @staticmethod
    def _parameter_base(param_name: str) -> str:
        """
        Normalize a parameter name to its "base" form for matching against
        TARGET_PARAMETER_BASES / PROTECTED_PARAMETERS, e.g.:
            'auteur1'   -> 'auteur'
            'nom2'      -> 'nom'
            'prénom3'   -> 'prénom'
            'éditeur'   -> 'éditeur'
            'Site'      -> 'site'
        """
        key = param_name.strip().lower()
        # Strip a single trailing run of digits (auteur1, nom12, ...)
        key = re.sub(r'\d+$', '', key).strip()
        return key

    # -- Template discovery -----------------------------------------------

    def _find_reference_templates(self, text: str) -> List[Tuple[int, int, str, Dict[str, str]]]:
        """Find all recognized reference templates and their parameters."""
        templates = []
        i = 0
        while i < len(text):
            start = text.find('{{', i)
            if start == -1:
                break

            end = self._find_matching_braces(text, start)
            if end is None:
                i = start + 2
                continue

            template_content = text[start:end + 2]

            name_match = re.match(r'\{\{\s*([^|{}]+?)\s*(?:\||\}\})', template_content)
            if not name_match:
                i = start + 2
                continue

            raw_name = name_match.group(1).strip()
            normalized_name = raw_name.lower().replace('_', ' ')
            template_name = self.KNOWN_TEMPLATES.get(normalized_name)

            if template_name:
                parameters = self._parse_parameters(template_content)
                templates.append((start, end + 2, template_name, parameters))

            i = start + 2

        return templates

    def _find_matching_braces(self, text: str, start: int) -> Optional[int]:
        """Find the index of the matching closing '}}' for a '{{' at start."""
        depth = 0
        i = start
        while i < len(text) - 1:
            two = text[i:i + 2]
            if two == '{{':
                depth += 1
                i += 2
            elif two == '}}':
                depth -= 1
                if depth == 0:
                    return i
                i += 2
            else:
                i += 1
        return None

    def _parse_parameters(self, template_content: str) -> Dict[str, str]:
        """
        Parse parameters from a template content string.

        Note: if the same parameter key appears more than once (case-insensitive),
        only the LAST occurrence is kept here for lookup purposes — but
        _rebuild_template independently detects duplicates and refuses to
        touch the template at all in that case, so a duplicate key never
        results in a partial/inconsistent edit.
        """
        if not (template_content.startswith('{{') and template_content.endswith('}}')):
            return {}

        inner = template_content[2:-2]
        segments = self._split_top_level(inner, '|')

        parameters: Dict[str, str] = {}
        for segment in segments[1:]:
            eq_pos = segment.find('=')
            if eq_pos > 0:
                key = segment[:eq_pos].strip()
                value = segment[eq_pos + 1:].strip()
                if key:
                    # Normalize key to case-insensitive form to detect duplicates
                    normalized_key = key.lower()
                    parameters[normalized_key] = value

        return parameters

    def _split_top_level(self, text: str, delimiter: str) -> List[str]:
        """Split text by delimiter, respecting nested {{ }} and [[ ]] structures."""
        segments = []
        current = []
        depth_template = 0
        depth_link = 0

        for char in text:
            if char == '{' and current and current[-1] == '{':
                depth_template += 1
                current.append(char)
            elif char == '}' and current and current[-1] == '}':
                depth_template = max(0, depth_template - 1)
                current.append(char)
            elif char == '[' and current and current[-1] == '[':
                depth_link += 1
                current.append(char)
            elif char == ']' and current and current[-1] == ']':
                depth_link = max(0, depth_link - 1)
                current.append(char)
            elif char == delimiter and depth_template == 0 and depth_link == 0:
                segments.append(''.join(current))
                current = []
            else:
                current.append(char)

        if current:
            segments.append(''.join(current))

        return segments

    # -- Per-parameter normalization dispatch -----------------------------

    def _normalize_parameter_value(self, value: str, base_key: str) -> Tuple[str, Optional[str]]:
        """
        Normalize a single parameter value based on its (base) parameter name.

        Returns (normalized_value, ignore_reason). ignore_reason is None
        when the value was changed (or was already fine and needed no
        change); it is a short human-readable string when the value was
        deliberately left untouched out of caution.
        """
        if not value or not value.strip():
            return value, None

        if base_key == 'titre':
            return self._normalize_title(value)
        elif base_key in ('site', 'éditeur', 'editeur', 'publisher'):
            return self._normalize_site_or_publisher(value)
        elif base_key in ('auteur', 'auteur prénom', 'auteur nom', 'nom', 'prénom', 'prenom'):
            return self._normalize_person_name(value)

        # Should not happen: base_key was already filtered against
        # TARGET_PARAMETER_BASES upstream. Kept as a safe no-op fallback.
        return value, "paramètre non reconnu"

    # -- Shared helpers -----------------------------------------------------

    def _contains_acronym(self, text: str) -> bool:
        """Whole-word (case-insensitive) match against known acronyms."""
        for acronym in self.common_acronyms:
            if re.search(r'\b' + re.escape(acronym) + r'\b', text, re.IGNORECASE):
                return True
        return False

    def _find_official_name_match(self, text: str) -> Optional[str]:
        """
        Return the longest known official name found as a whole-word
        (word-boundary-respecting) substring of `text`, or None.
        """
        for official_name in self._official_names_sorted:
            if re.search(r'\b' + re.escape(official_name) + r'\b', text, re.IGNORECASE):
                return official_name
        return None

    def _find_preserved_expression_match(self, text: str) -> Optional[str]:
        """Same as _find_official_name_match but for preserved_expressions."""
        for expression in self._preserved_expressions_sorted:
            if re.search(r'\b' + re.escape(expression) + r'\b', text, re.IGNORECASE):
                return expression
        return None

    def _is_all_uppercase(self, text: str) -> bool:
        letters = [c for c in text if c.isalpha()]
        return len(letters) >= self._MIN_ALPHA_CHARS_TO_JUDGE and all(c.isupper() for c in letters)

    def _is_all_lowercase(self, text: str) -> bool:
        letters = [c for c in text if c.isalpha()]
        return len(letters) >= self._MIN_ALPHA_CHARS_TO_JUDGE and all(c.islower() for c in letters)

    def _has_internal_capitals(self, text: str) -> bool:
        """
        True if the text is genuinely mixed-case: contains at least one
        lowercase letter AND at least one uppercase letter that is not
        simply "first letter of the whole string". This deliberately
        excludes all-uppercase text (which has plenty of "capitals after
        the first character" but is not mixed case) and all-lowercase
        text — both of those are handled by the dedicated
        _is_all_uppercase / _is_all_lowercase checks instead.
        """
        letters = [c for c in text if c.isalpha()]
        if not letters:
            return False
        has_upper = any(c.isupper() for c in letters)
        has_lower = any(c.islower() for c in letters)
        return has_upper and has_lower

    # -- titre= -----------------------------------------------------------

    def _normalize_title(self, title: str) -> Tuple[str, Optional[str]]:
        """
        Normalize a title towards French sentence case, conservatively.

        Only rewrites text that is unambiguously ALL-UPPERCASE or
        all-lowercase. Anything already mixed-case is left untouched: we
        cannot reliably tell a legitimate title ("Le Système solaire")
        from a proper name ("Rachida Belkacem") from a stylised title
        ("PlayStation 5 : le test") using capitalization alone, so we do
        not attempt to rewrite those and risk corrupting a legitimate
        title. This trade-off favours never damaging a correct title over
        catching every malformed one.
        """
        # An exact known official name/expression as the *entire* value:
        # preserve verbatim (e.g. titre=Wikipédia).
        if title in self.official_names or title in self.preserved_expressions:
            return title, None

        if self._contains_acronym(title):
            return title, "sigle détecté"

        official_match = self._find_official_name_match(title)
        expression_match = self._find_preserved_expression_match(title)
        if official_match or expression_match:
            # The title contains a known official name/expression; rather
            # than risk mangling it with a blanket case rewrite, leave the
            # whole title untouched — the presence of curated proper-noun
            # data is itself a strong signal this text needs care.
            return title, f"contient un nom protégé ({official_match or expression_match})"

        if self._has_internal_capitals(title):
            # Already mixed case — could be a correct title, a proper name,
            # a brand, a foreign-language title, etc. Do not touch it.
            return title, None

        if self._is_all_uppercase(title):
            # Try NER-based normalization if enabled and available
            if self.enable_ner_title_normalization and self._spacy_available:
                return self._normalize_allcaps_title_with_ner(title)
            # Otherwise, conservative fallback: don't touch it
            return title, "titre tout en majuscules — normalisation désactivée (ambiguïté nom propre)"

        if self._is_all_lowercase(title):
            return self._capitalize_first_letter_only(title), None

        # Anything else (too short to judge, punctuation-only, digits, ...)
        return title, None

    def _normalize_allcaps_title_with_ner(self, title: str) -> Tuple[str, Optional[str]]:
        """
        Normalize an all-caps title using spaCy NER to preserve person names.
        
        Strategy:
        1. Apply naive title-case to make text readable for NER
        2. Run NER to detect PER (person) entities
        3. Reconstruct title: preserve person names in proper case, title-case the rest
        
        Args:
            title: All-caps title string (e.g., "DEBATS MICHEL BEAUD")
            
        Returns:
            Tuple of (normalized_title, reason_for_ignoring_or_None)
        """
        # Step 1: Apply naive title-case for NER readability
        # Use _apply_title_case which capitalizes each word (preserves particles, acronyms)
        readable_text = self._apply_title_case(title)
        
        # Step 2: Extract person entities
        person_entities = self._extract_person_entities(readable_text)
        
        if not person_entities:
            # No person entities detected, fallback to conservative behavior
            return title, "titre tout en majuscules — NER n'a détecté aucune personne"
        
        # Step 3: Reconstruct title preserving person names
        # Sort entities by position (reverse order to avoid offset issues when replacing)
        person_entities_sorted = sorted(person_entities, key=lambda x: x[0], reverse=True)
        
        # Build the final title
        result = readable_text
        preserved_names = []
        
        for start, end, entity_text in person_entities_sorted:
            # Preserve the entity text as detected by NER (already properly cased)
            # Replace the corresponding span in result
            result = result[:start] + entity_text + result[end:]
            preserved_names.append(entity_text)
        
        # Step 4: Log for traceability
        reason = f"titre normalisé via NER, entités préservées: {', '.join(preserved_names)}"
        self._logger.debug(f"NER normalization: '{title}' -> '{result}' ({reason})")
        
        return result, reason

    def _apply_sentence_case_with_separators(self, text: str) -> str:
        """
        Apply sentence case to ALL-UPPERCASE text, treating ':', '–', '—',
        '-' as subtitle separators so each clause starts with a capital,
        matching standard French subtitle punctuation conventions
        (e.g. "TITRE : SOUS-TITRE" -> "Titre : Sous-titre").
        """
        parts = re.split(r'([：:–—-])', text)
        normalized_parts = []
        for i, part in enumerate(parts):
            if i % 2 == 1:  # separator
                normalized_parts.append(part)
            elif part.strip():
                normalized_parts.append(self._capitalize_first_letter_only(part))
            else:
                normalized_parts.append(part)
        return ''.join(normalized_parts)

    def _capitalize_first_letter_only(self, text: str) -> str:
        """Capitalize only the first alphabetic character; lowercase the rest."""
        if not text:
            return text

        leading_ws = ''
        i = 0
        while i < len(text) and text[i].isspace():
            leading_ws += text[i]
            i += 1
        rest = text[i:]
        if not rest:
            return leading_ws

        return leading_ws + rest[0].upper() + rest[1:].lower()

    # -- site= / éditeur= ----------------------------------------------------

    def _normalize_site_or_publisher(self, value: str) -> Tuple[str, Optional[str]]:
        """
        Normalize a site/publisher name, preserving official brand stylings.

        Priority order:
        1. Exact known official name -> preserved verbatim.
        2. Value looks like a bare domain (e.g. "lemonde.fr") that has a
           curated mapping -> replaced with the official site name.
        3. Value looks like a bare domain WITHOUT a curated mapping ->
           left untouched. Domain names are conventionally all-lowercase;
           there is no correct "title case" for a raw domain, so guessing
           one (e.g. "gdrw.eu" -> "Gdrw.eu") would just be wrong. Only a
           known official name should ever change a site='s casing.
        4. Contains a known official name as substring -> preserved as-is
           (do not risk mangling a name we recognize).
        5. Contains an acronym -> preserved as-is.
        6. Has intentional mixed case (eBay, i-D, theSkimm) -> preserved as-is.
           This protects official brand stylings that deliberately use
           non-standard capitalization.
        7. Otherwise (a human-readable name, not domain-shaped): apply
           conservative title case only if the value is unambiguously
           all-uppercase or all-lowercase.
        """
        if value in self.official_names:
            return value, None

        domain_match = self._match_domain_mapping(value)
        if domain_match:
            return domain_match, None

        if self._looks_like_domain(value):
            # No curated mapping for this domain — leave it exactly as-is
            # rather than inventing a "title case" that doesn't apply to
            # domain names.
            return value, "domaine sans correspondance connue"

        if self._find_official_name_match(value):
            return value, "contient un nom officiel connu"

        if self._contains_acronym(value):
            return value, "sigle détecté"

        if self._has_intentional_brand_styling(value):
            # Preserve official brand stylings like eBay, i-D, theSkimm
            return value, "graphie officielle préservée"

        if self._is_all_uppercase(value) or self._is_all_lowercase(value):
            return self._apply_title_case(value), None

        return value, None

    def _has_intentional_brand_styling(self, value: str) -> bool:
        """
        Detect intentional brand stylings that should be preserved.

        Patterns that indicate deliberate non-standard capitalization:
        - Lowercase letter followed by uppercase (eBay, iPhone, iPad)
        - Uppercase letter followed by hyphen and uppercase (i-D, X-Men)
        - Lowercase word followed by uppercase (theSkimm, theGuardian)
        - CamelCase with specific patterns (YouTube, PlayStation)
        """
        if not value or len(value) < 3:
            return False

        # Pattern: lowercase letter followed by uppercase letter
        # (eBay, iPhone, iPad, macOS, iOS, etc.)
        if re.search(r'[a-z][A-Z]', value):
            return True

        # Pattern: uppercase letter followed by hyphen and uppercase
        # (i-D, X-Men, T-Shirt, etc.)
        if re.search(r'[A-Z]-[A-Z]', value):
            return True

        # Pattern: lowercase word followed by uppercase word
        # (theSkimm, theGuardian, etc.)
        if re.search(r'[a-z]+\s+[A-Z][a-z]+', value):
            return True

        # Known brand-specific patterns that are intentional
        # (these are common enough to hardcode as safety)
        brand_patterns = [
            r'youtube',  # YouTube
            r'playstation',  # PlayStation
            r'facebook',  # Facebook
            r'linkedin',  # LinkedIn
            r'wordpress',  # WordPress
            r'javascript',  # JavaScript
            r'typescript',  # TypeScript
            r'github',  # GitHub
            r'gitlab',  # GitLab
            r'bitbucket',  # Bitbucket
        ]
        for pattern in brand_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return True

        return False

    @staticmethod
    def _looks_like_domain(value: str) -> bool:
        """
        Heuristic: does `value` look like a bare domain name (optionally
        prefixed with a URL scheme and/or 'www.', optionally followed by
        a path)? Used to avoid ever "title-casing" a raw domain that has
        no curated official name.
        """
        candidate = value.strip()
        candidate = re.sub(r'^https?://', '', candidate, flags=re.IGNORECASE)
        candidate = candidate.split('/')[0]
        if ' ' in candidate or not candidate:
            return False
        # A domain: labels of letters/digits/hyphens separated by dots,
        # ending in a plausible TLD of at least 2 letters, optionally
        # followed by a port.
        return bool(re.match(
            r'^([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}(:\d+)?$',
            candidate,
        ))

    def _match_domain_mapping(self, value: str) -> Optional[str]:
        """
        If `value` looks like a bare domain name (with or without a
        leading 'www.' or a URL scheme) that matches a curated
        domain_to_site_name entry, return the official site name.
        Otherwise return None. This never touches the URL parameter
        itself — only the separate site=/éditeur= value, which
        occasionally gets filled in with the raw domain by mistake.
        """
        if not self.domain_to_site_name:
            return None

        candidate = value.strip().lower()
        candidate = re.sub(r'^https?://', '', candidate)
        candidate = candidate.split('/')[0]  # drop any path
        if not candidate or ' ' in candidate:
            return None  # not domain-shaped

        if candidate in self.domain_to_site_name:
            return self.domain_to_site_name[candidate]

        # Try without a leading "www."
        if candidate.startswith('www.'):
            bare = candidate[4:]
            if bare in self.domain_to_site_name:
                return self.domain_to_site_name[bare]

        return None

    def _apply_title_case(self, text: str) -> str:
        """Apply title case, keeping particles lowercase and acronyms intact."""
        words = text.split()
        if not words:
            return text

        result = []
        for i, word in enumerate(words):
            stripped = word.strip('.,;:!?()[]{}"\'')
            if i == 0:
                result.append(word.capitalize())
            elif stripped.lower() in self.particles:
                result.append(word.lower())
            elif self._contains_acronym(word):
                result.append(word)
            else:
                result.append(word.capitalize())

        return ' '.join(result)

    # -- auteur= / nom= / prénom= -------------------------------------------

    def _normalize_person_name(self, name: str) -> Tuple[str, Optional[str]]:
        """
        Normalize a person's name.

        Unlike titre=, this parameter's *meaning* is unambiguous — it is
        always a person's name, never a sentence — so it is safe to apply
        title-case-per-word logic even when the value doesn't already
        have internal capitals, without the "could this be a real
        sentence" risk that titre= carries.

        Handles:
        - Multi-word names, each word capitalized
        - Particles (de, van, von, la, ...) lowercase except in first position
        - Hyphenated names ("Jean-Pierre" -> each part capitalized)
        - Known acronyms/initials preserved as-is
        """
        if not name or not name.strip():
            return name, None

        if self._contains_acronym(name):
            return name, "sigle détecté"

        if name in self.official_names:
            return name, None

        # Already has internal capitals and isn't all-uppercase noise:
        # trust the existing formatting (e.g. "McDonald", "O'Brien").
        if self._has_internal_capitals(name) and not self._is_all_uppercase(name):
            return name, None

        parts = name.split()
        if not parts:
            return name, None

        result = []
        for i, part in enumerate(parts):
            if i == 0:
                result.append(self._capitalize_name_part(part))
            elif part.lower() in self.particles:
                result.append(part.lower())
            elif self._contains_acronym(part):
                result.append(part)
            else:
                result.append(self._capitalize_name_part(part))

        normalized = ' '.join(result)
        return normalized, None

    @staticmethod
    def _capitalize_name_part(part: str) -> str:
        """
        Capitalize a single name token, handling internal hyphens and
        apostrophes correctly (e.g. "jean-pierre" -> "Jean-Pierre",
        "o'brien" -> "O'Brien", "d'artagnan" -> "D'Artagnan").
        """
        if not part:
            return part

        def cap_segment(seg: str) -> str:
            return seg[:1].upper() + seg[1:].lower() if seg else seg

        # Split on hyphens, keeping the hyphen; then on apostrophes within
        # each hyphen-segment, keeping the apostrophe.
        hyphen_segments = re.split(r'(-)', part)
        rebuilt = []
        for seg in hyphen_segments:
            if seg == '-':
                rebuilt.append(seg)
                continue
            apostrophe_segments = re.split(r"(['’])", seg)
            rebuilt.append(''.join(
                cap_segment(s) if s not in ("'", "’") else s
                for s in apostrophe_segments
            ))
        return ''.join(rebuilt)

    # -- Template rebuilding ------------------------------------------------

    def _rebuild_template(self, template_text: str, modified_params: Dict[str, Tuple[str, str]]) -> str:
        """
        Rebuild a template with modified parameter values, preserving the
        original parameter order and every untouched parameter exactly.

        Safety check: if the template contains a duplicate parameter key (case-insensitive),
        the entire template is returned unchanged (no partial edit),
        because it's impossible to know which occurrence a given
        modification was meant to target without risking touching the
        wrong one.
        """
        segments = self._split_top_level(template_text[2:-2], '|')
        if not segments:
            return template_text

        result = [segments[0]]
        used_keys = set()

        for segment in segments[1:]:
            eq_pos = segment.find('=')
            if eq_pos <= 0:
                result.append(segment)
                continue

            key = segment[:eq_pos].strip()
            value = segment[eq_pos + 1:].strip()
            normalized_key = key.lower()

            if normalized_key in used_keys:
                self._logger.warning(
                    f"Duplicate parameter '{key}' (case-insensitive) detected in template — "
                    f"skipping entire template unchanged for safety."
                )
                return template_text
            used_keys.add(normalized_key)

            if normalized_key in modified_params:
                old_value, new_value = modified_params[normalized_key]
                if value == old_value:
                    result.append(f"{key}={new_value}")
                else:
                    # Value in the live text no longer matches what we
                    # analyzed (shouldn't happen given single-pass
                    # processing, but fail safe rather than overwrite
                    # something we didn't actually validate).
                    result.append(segment)
            else:
                result.append(segment)

        return '{{' + '|'.join(result) + '}}'