Je vais réaliser un audit architectural complet du système DeadLink. Commençons par explorer la structure du projet pour identifier tous les fichiers pertinents.

Je vais continuer l'analyse en lisant d'autres fichiers clés pour comprendre l'ensemble du système.

# AUDIT ARCHITECTURAL COMPLET DU SYSTÈME DEADLINK

## 1. CARTOGRAPHIE COMPLÈTE DES FICHIERS

### A. Détection
- **dead_links.py** (analyzers) - Analyseur principal DeadLink, détecte les liens morts via URL_PATTERN
- **http_links.py** (analyzers) - Détecte les liens HTTP pour conversion HTTPS
- **url_extraction.py** (utils) - Extrait les URLs du wikicode via regex URL_PATTERN

### B. Validation HTTP
- **link_checker.py** (utils) - Valide les liens HTTP avec retry, classifie les codes HTTP
- **link_validator.py** (utils) - Coordonne validation et décisions de réparation
- **redirect_finder.py** (utils) - Détecte les redirects valides
- **content_verifier.py** (utils) - Vérifie que le contenu correspond entre URLs

### C. Classification
- **link_checker.py** (utils) - Classifie les liens en: HEALTHY, DEAD, TEMPORARY_ERROR, RATE_LIMITED, REVIEW_REQUIRED, UNKNOWN
- **link_validator.py** (utils) - Classifie les décisions de réparation: NO_ACTION, DEAD_NO_REPLACEMENT, REPLACEMENT_CONFIRMED, REPAIR_REJECTED

### D. Archives / Wayback
- **archive_provider.py** (utils) - Coordination multi-providers (Wayback, Archive.org, Arquivo.pt)
- **archive_content_checker.py** (utils) - Détecte les soft-404 dans les archives
- **arquivo_provider.py** (utils) - Provider Arquivo.pt
- **commoncrawl_provider.py** (utils) - Provider CommonCrawl

### E. Correction / remplacement
- **dead_links.py** (analyzers) - Logique principale de réparation (contient beaucoup de logique de correction)
- **corrector.py** (utils) - Applique les corrections au wikicode
- **safe_url_replacer.py** (utils) - Remplacement sécurisé par position exacte
- **reference_template_helper.py** (utils) - Génère les templates de référence avec archives

### F. Vérification post-correction
- **template_replacement_validator.py** (utils) - Valide les remplacements de templates
- **content_verifier.py** (utils) - Vérifie contenu après correction

### G. Enregistrement / tracking
- **analyzed_tracker.py** (utils) - Suit les articles analysés
- **published_tracker.py** (utils) - Suit les articles publiés
- **publisher.py** (utils) - Publie sur Wikipedia (réécrit corrector.py)

### H. Orchestration
- **orchestrator.py** (orchestrator) - Coordination DeadLinkAnalyzer + HttpLinksAnalyzer + Corrector
- **automation_orchestrator.py** (orchestrator) - Orchestration automatisée

### I. Helper / utilitaire
- **url_metadata.py** (utils) - Extraction métadonnées URL (titre, site)
- **bare_url_helper.py** (utils) - Conversion URLs nues vers templates
- **lien_web_helper.py** (utils) - Manipulation templates {{Lien web}}
- **reference_utils.py** (utils) - Utilitaires références (ISBN, validation)
- **internal_links_writer.py** (utils) - Ajout liens internes dans "Voir aussi"

### J. Configuration
- **dead_link_analyzer_config.py** (utils) - Configuration DeadLinkAnalyzer
- **config.py** (utils) - Configuration générale

### K. Test
- **test_dead_link_analyzer_config.py** - Tests configuration
- **test_dead_link_analyzer_toggle.py** - Tests activation/désactivation
- **test_dead_link_fixes.py** - Tests corrections
- **test_dead_link_scenarios.py** - Tests scénarios

### L. Code obsolète / inutilisé
- **candidate_finder.py** (utils) - Importé mais jamais utilisé (commenté dans dead_links.py ligne 45)
- **corrector.py** (utils) - Version duplication avec publisher.py/corrector.py

### M. Responsabilité ambiguë
- **dead_links.py** (analyzers) - Mélange détection, validation, correction, tracking
- **lien_web_helper.py** (utils) - Duplique logique de reference_template_helper.py
- **reference_utils.py** (utils) - Fonctions génériques peu utilisées

## 2. TRACE D'EXÉCUTION RÉELLE

### Flux principal DeadLink:

```
Article (wikicode)
    ↓
DeadLinkOrchestrator.analyze()
    ↓
DeadLinkAnalyzer.analyze(content)
    ↓
UrlExtractor.URL_PATTERN.finditer(content) [url_extraction.py]
    ↓
DeadLinkAnalyzer._is_url_syntactically_valid() [dead_links.py]
    ↓
DeadLinkAnalyzer._is_url_in_reference_scope() [dead_links.py]
    ↓
LinkChecker.check_link(url) [link_checker.py]
    ↓
LinkChecker._attempt_check() → HTTP HEAD/GET
    ↓
LinkChecker._classify_http_status() → LinkStatus (HEALTHY/DEAD/TEMPORARY_ERROR/etc)
    ↓
[SI DEAD]
    ↓
RedirectFinder.find_redirect(url) [redirect_finder.py]
    ↓
[SI REDIRECT VALID]
    ↓
ContentVerifier.verify_same_resource() [content_verifier.py]
    ↓
ArchiveProvider.verify_content_match() [archive_provider.py]
    ↓
LinkValidator.validate_repair() [link_validator.py]
    ↓
[SI REPLACEMENT_CONFIRMED]
    ↓
DeadLinkAnalyzer._attempt_archive_fallback() [dead_links.py]
    ↓
ArchiveProvider.check_archive() [archive_provider.py]
    ↓
DeadLinkAnalyzer._build_lien_web_template() [dead_links.py]
    ↓
ReferenceTemplateHelper.generate_archive_repair_template() [reference_template_helper.py]
    ↓
DeadLinkAnalyzer._add_repair_issue() → Issue avec suggested_text
    ↓
DeadLinkAnalyzer.analyze() retourne List[Issue]
    ↓
DeadLinkOrchestrator.analyze()
    ↓
Corrector(original_content)
    ↓
Corrector.apply_corrections(issues)
    ↓
Corrector._apply_correction_at_position()
    ↓
Corrector.get_corrected_content()
    ↓
DeadLinkOrchestrator retourne DeadLinkResult
    ↓
[SI PUBLICATION]
    ↓
Publisher.publish()
    ↓
PublishedTracker.mark_as_published()
```

## 3. RESPONSABILITÉS QUI SE CHEVAUCHENT

### Validation HTTP - Duplication MAJEURE

**Fichier A: link_checker.py**
- Fait: Requêtes HTTP, retry, classification des codes HTTP
- Responsabilité: Détection de l'état des liens

**Fichier B: dead_links.py**
- Fait: Appelle link_checker.check_link() mais contient aussi logique de validation DNS transient
- Duplication: `_consecutive_dns_failures` tracking, `_check_url_truncation()`
- Différence: dead_links.py ajoute validation DNS transient non présente dans link_checker.py
- **Source correcte**: link_checker.py
- **Risque de divergence**: dead_links.py peut ignorer des erreurs DNS que link_checker.py considère comme DEAD

### Retry / Timeout - Duplication PARTIELLE

**Fichier A: link_checker.py**
- Fait: Retry avec backoff exponentiel, timeout configurable
- Constantes: DEFAULT_TIMEOUT=10, max_retries

**Fichier B: dead_links.py**
- Fait: Retry via link_checker mais ajoute sa propre logique retry pour archives
- Duplication: RetryHandler utilisé dans _attempt_archive_fallback() avec RetryConfig
- Différence: dead_links.py utilise RetryHandler alors que link_checker.py implémente son propre retry
- **Source correcte**: link_checker.py (devrait déléguer à RetryHandler)
- **Risque de divergence**: Différentes stratégies de retry selon le chemin

### Classification HTTP - Duplication

**Fichier A: link_checker.py**
- Fait: Classification: PERMANENTLY_DEAD_CODES (404, 410), REVIEW_REQUIRED_CODES (400, 401, 403, 498), TEMPORARY_ERROR_CODES

**Fichier B: link_validator.py**
- Fait: Reclassifie pour décision de réparation
- Duplication: Logique de décision basée sur LinkStatus mais avec critères supplémentaires
- Différence: link_validator.py ajoute preuves multiples (ORIGINAL_PAGE_EXISTS, CANDIDATE_PAGE_EXISTS, SAME_RESOURCE_CONFIRMED)
- **Source correcte**: link_checker.py pour classification HTTP, link_validator.py pour décision métier
- **Risque de divergence**: Faible - séparation des responsabilités correcte

### Détection 403 académique - Duplication LOGIQUE

**Fichier A: link_checker.py**
- Fait: `_is_academic_publisher()` détecte 403 académique → TEMPORARY_ERROR
- Charge: academic_domains.yaml

**Fichier B: url_extraction.py**
- Fait: `is_syntactically_valid()` exclut les domaines académiques
- Charge: academic_domains.yaml (via link_checker._load_academic_publisher_domains)
- Duplication: Deux modules chargent le même fichier pour des raisons différentes
- Différence: link_checker exclut après 403, url_extraction exclut avant vérification
- **Source correcte**: url_extraction.py (prévention) + link_checker.py (mitigation)
- **Risque de divergence**: Faible - complémentaire

### Wayback / Archives - Duplication COORDINATION

**Fichier A: archive_provider.py**
- Fait: Coordination multi-providers, check_archive()
- Providers: WaybackProvider, ArchiveOrgProvider, ArquivoProvider, CommonCrawlProvider

**Fichier B: dead_links.py**
- Fait: Appelle archive_provider mais contient logique de fallback multi-providers
- Duplication: dead_links.py réimplémente logique de fallback alternative dans _attempt_archive_fallback()
- Différence: archive_provider a check_all_providers() mais dead_links.py fait sa propre boucle
- **Source correcte**: archive_provider.py
- **Risque de divergence**: Élevé - logique dupliquée de vérification multi-providers

### Remplacement d'URL - Duplication

**Fichier A: safe_url_replacer.py**
- Fait: `replace_exact_occurrence()` avec validation de position et diff minimal

**Fichier B: corrector.py**
- Fait: `_apply_correction_at_position()` avec logique similaire
- Duplication: Logique de remplacement position-based dans les deux fichiers
- Différence: corrector.py gère conflits et offset tracking, safe_url_replacer.py est plus simple
- **Source correcte**: corrector.py (plus complet)
- **Risque de divergence**: Moyen - deux implémentations de la même fonctionnalité

### Template Generation - Duplication

**Fichier A: reference_template_helper.py**
- Fait: `generate_archive_repair_template()` pour tous les templates supportés

**Fichier B: lien_web_helper.py**
- Fait: `generate_archive_repair_template()` spécifique pour {{Lien web}}
- Duplication: Deux implémentations de génération de template avec archive
- Différence: lien_web_helper.py est spécifique Lien web, reference_template_helper.py est générique
- **Source correcte**: reference_template_helper.py
- **Risque de divergence**: Moyen - lien_web_helper.py pourrait être déprécié

### Wikicode Modification - Duplication

**Fichier A: dead_links.py**
- Fait: Modifie content directement dans certaines branches (commenté mais présent)
- Contient: `_apply_simple_url_replacement()` qui modifie content

**Fichier B: corrector.py**
- Fait: `apply_corrections()` modifie content via Issue.suggested_text
- Duplication: Deux approches de modification du wikicode
- Différence: dead_links.py modifie pendant analyse, corrector.py modifie après analyse
- **Source correcte**: corrector.py (séparation analyse/correction)
- **Risque de divergence**: Élevé - dead_links.py ne devrait pas modifier content

## 4. UTILISATION DES HELPERS ET SERVICES SPÉCIALISÉS

### link_checker.py - PARTIELLEMENT UTILISÉ
- **Utilisé par**: dead_links.py, link_validator.py
- **Contexte**: Validation HTTP des liens
- **Utilisation correcte**: OUI
- **Logique contournée**: dead_links.py ajoute sa propre logique DNS transient
- **Réimplémentation**: dead_links.py réimplémente retry pour archives

### link_validator.py - PARTIELLEMENT UTILISÉ
- **Utilisé par**: dead_links.py
- **Contexte**: Décision de réparation avec preuves multiples
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### redirect_finder.py - PARTIELLEMENT UTILISÉ
- **Utilisé par**: dead_links.py
- **Contexte**: Recherche de redirects valides
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### content_verifier.py - PARTIELLEMENT UTILISÉ
- **Utilisé par**: dead_links.py, link_validator.py
- **Contexte**: Vérification contenu entre URLs
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### archive_provider.py - PARTIELLEMENT UTILISÉ
- **Utilisé par**: dead_links.py, content_verifier.py
- **Contexte**: Recherche et vérification d'archives
- **Utilisation correcte**: PARTIELLE
- **Logique contournée**: dead_links.py réimplémente fallback multi-providers
- **Réimplémentation**: OUI - dead_links.py fait sa propre boucle de vérification alternative

**Ce module devrait être responsable de**: Coordination multi-providers, fallback automatique
**Mais actuellement**: dead_links.py fait lui-même la logique de fallback alternative

### archive_content_checker.py - PARTIELLEMENT UTILISÉ
- **Utilisé par**: dead_links.py
- **Contexte**: Détection soft-404 dans les archives
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### safe_url_replacer.py - PARTIELLEMENT UTILISÉ
- **Utilisé par**: dead_links.py
- **Contexte**: Remplacement sécurisé par position
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### reference_template_helper.py - PARTIELLEMENT UTILISÉ
- **Utilisé par**: dead_links.py, bare_url_helper.py
- **Contexte**: Manipulation templates de référence
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### bare_url_helper.py - PARTIELLEMENT UTILISÉ
- **Utilisé par**: dead_links.py
- **Contexte**: Conversion URLs nues vers templates
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### lien_web_helper.py - PEU UTILISÉ
- **Utilisé par**: Aucun import direct dans dead_links.py
- **Contexte**: Manipulation spécifique {{Lien web}}
- **Utilisation correcte**: NON
- **Logique contournée**: dead_links.py utilise reference_template_helper.py à la place
- **Réimplémentation**: Duplique logique de reference_template_helper.py

**Ce module devrait être responsable de**: Manipulation {{Lien web}} spécifique
**Mais actuellement**: Non utilisé, logique dupliquée dans reference_template_helper.py

### url_extraction.py - BIEN UTILISÉ
- **Utilisé par**: dead_links.py, bare_url_helper.py
- **Contexte**: Extraction et validation d'URLs
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### url_metadata.py - BIEN UTILISÉ
- **Utilisé par**: dead_links.py, bare_url_helper.py
- **Contexte**: Extraction métadonnées URL
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### template_replacement_validator.py - BIEN UTILISÉ
- **Utilisé par**: dead_links.py
- **Contexte**: Validation remplacements de templates
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### internal_links_writer.py - BIEN UTILISÉ
- **Utilisé par**: dead_links.py
- **Contexte**: Ajout liens internes "Voir aussi"
- **Utilisation correcte**: OUI
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune

### candidate_finder.py - NON UTILISÉ
- **Utilisé par**: Aucun
- **Contexte**: Recherche multi-stratégie de candidats
- **Utilisation correcte**: NON
- **Logique contournée**: Aucune
- **Réimplémentation**: Aucune
- **Statut**: Importé mais commenté dans dead_links.py ligne 45-46

## 5. ANALYSE DES DÉPENDANCES

### Matrice des dépendances

| Module | Appelé par | Appelle | Responsabilité | Utilisé réellement? | Duplication? | Problème |
|--------|-----------|---------|---------------|-------------------|-------------|----------|
| dead_links.py | orchestrator.py | link_checker, link_validator, redirect_finder, content_verifier, archive_provider, reference_template_helper, bare_url_helper, safe_url_replacer, template_replacement_validator, internal_links_writer, lien_web_helper | Détection + validation + correction | OUI | OUI (retry archives, fallback multi-providers) | Fait trop de choses |
| link_checker.py | dead_links.py, link_validator.py | api_throttler | Validation HTTP | OUI | OUI (retry dead_links) | Retry dupliqué |
| link_validator.py | dead_links.py | link_checker, content_verifier | Décision réparation | OUI | NON | Aucun |
| redirect_finder.py | dead_links.py | api_throttler, retry_handler | Recherche redirects | OUI | NON | Aucun |
| content_verifier.py | dead_links.py, link_validator.py | api_throttler, archive_provider | Vérification contenu | OUI | NON | Aucun |
| archive_provider.py | dead_links.py, content_verifier.py | api_throttler, retry_handler | Archives multi-providers | OUI | OUI (fallback dead_links) | Fallback dupliqué |
| reference_template_helper.py | dead_links.py, bare_url_helper.py | url_metadata | Templates référence | OUI | NON | Aucun |
| bare_url_helper.py | dead_links.py | reference_template_helper, url_metadata | Conversion URLs nues | OUI | NON | Aucun |
| lien_web_helper.py | Aucun | Aucun | Templates {{Lien web}} | NON | OUI (reference_template_helper) | Inutilisé |
| safe_url_replacer.py | dead_links.py | Aucun | Remplacement sécurisé | OUI | OUI (corrector) | Duplication corrector |
| template_replacement_validator.py | dead_links.py | Aucun | Validation templates | OUI | NON | Aucun |
| internal_links_writer.py | dead_links.py | Aucun | Liens internes | OUI | NON | Aucun |
| url_extraction.py | dead_links.py, bare_url_helper.py | Aucun | Extraction URLs | OUI | NON | Aucun |
| url_metadata.py | dead_links.py, bare_url_helper.py | url_extraction | Métadonnées URL | OUI | NON | Aucun |
| candidate_finder.py | Aucun | Aucun | Recherche candidats | NON | NON | Inutilisé |
| corrector.py | orchestrator.py, publisher.py | Aucun | Application corrections | OUI | OUI (safe_url_replacer) | Duplication |

### Imports inutilisés

**dead_links.py:**
- `candidate_finder` (commenté ligne 45-46)

**lien_web_helper.py:**
- Module entier non utilisé

### Classes inutilisées

**dead_links.py:**
- `CandidateFinder` (jamais instancié)

### Fonctions mortes

**reference_utils.py:**
- `validate_isbn()` - jamais appelée
- `check_link_status()` - jamais appelée (version requests)
- `get_archive_url()` - jamais appelée (version requests)
- `fetch_url_metadata()` - jamais appelée (version requests)
- `find_duplicate_refs()` - jamais appelée
- `normalize_isbn()` - jamais appelée
- `extract_urls_from_refs()` - jamais appelée
- `is_social_media_url()` - jamais appelée
- `is_wikipedia_url()` - jamais appelée
- `extract_language_from_wikipedia_url()` - jamais appelée

### Dépendances circulaires

Aucune dépendance circulaire détectée.

### Logique legacy

**corrector.py dans utils/ ET publisher.py:**
- Deux implémentations de Corrector
- utils/corrector.py: version avec OllamaSupervisor
- publisher.py: version simplifiée pour publication
- Utilisation: orchestrator.py utilise utils/corrector.py, publisher.py utilise sa propre version

## 6. FRONTIÈRE ENTRE DEADLINK ET ENREGISTREMENT

### Qui décide qu'un lien est mort
- **Décideur**: `link_checker.py` via `_classify_http_status()`
- **Critères**: Codes HTTP 404/410 = DEAD, autres classifiés selon règles
- **Enregistrement**: dead_links.py reçoit LinkCheckResult.status

### Qui décide qu'une correction est possible
- **Décideur**: `link_validator.py` via `validate_repair()`
- **Critères**: Preuves multiples (ORIGINAL_PAGE_EXISTS, CANDIDATE_PAGE_EXISTS, SAME_RESOURCE_CONFIRMED)
- **Enregistrement**: dead_links.py reçoit RepairResult.decision

### Qui effectue la correction
- **Exécuteur**: `corrector.py` via `apply_corrections()`
- **Critères**: Issue.suggested_text + position
- **Enregistrement**: corrector.crée Correction objects

### Qui décide qu'une correction a réussi
- **Décideur**: `corrector.py` via `_apply_correction_at_position()`
- **Critères**: Validation position + diff minimal
- **Enregistrement**: Correction.applied = True/False

### Qui enregistre la détection
- **Enregistreur**: `dead_links.py` via `self.issues.append(Issue(...))`
- **Format**: Issue avec issue_type="dead_link", extra avec repair_status
- **Problème**: dead_links.py écrit directement dans self.issues (pas de séparation)

### Qui enregistre la correction
- **Enregistreur**: `corrector.py` via `self.corrections.append(Correction(...))`
- **Format**: Correction avec applied=True/False
- **Problème**: corrector maintient sa propre liste séparée de Issue

### Qui enregistre l'échec
- **Enregistreur**: `dead_links.py` via Issue avec repair_status="REPAIR_FAILED", "REPAIR_REJECTED", etc.
- **Format**: Issue avec suggested_text=None
- **Problème**: Mixé avec les détections dans self.issues

### Qui enregistre l'archive
- **Enregistreur**: `dead_links.py` via Issue.extra['archive_url']
- **Format**: archive_url, archive_date, provider dans extra
- **Problème**: No tracking séparé des archives

### Qui enregistre l'URL originale
- **Enregistreur**: `dead_links.py` via Issue.extra['old_url']
- **Format**: old_url dans extra
- **Problème**: Dupliqué avec Issue.original_text

### Qui enregistre l'URL corrigée
- **Enregistreur**: `dead_links.py` via Issue.extra['new_url']
- **Format**: new_url dans extra
- **Problème**: Dupliqué avec Issue.suggested_text

### Qui enregistre le statut final
- **Enregistreur**: `dead_links.py` via Issue.extra['repair_status']
- **Format**: REPAIR_APPLIED, REPAIR_FAILED, etc.
- **Problème**: Pas de tracking consolidé

### Problèmes identifiés

1. **dead_links.py écrit directement dans les Issues** - devrait retourner des résultats neutres
2. **corrector.py maintient sa propre liste de Corrections** - duplication des données
3. **Pas de tracker consolidé** - informations dispersées entre Issue et Correction
4. **Pas de séparation analyse/enregistrement** - dead_links.py fait les deux

## 7. PROBLÈME CRITIQUE : TYPES DE RÉFÉRENCES WIKIPÉDIA

### Types de références distingués

**ReferenceTemplateHelper.KNOWN_TEMPLATE_NAMES:**
1. `Lien web` - Lien web externe
2. `article` - Article scientifique/presse
3. `ouvrage` - Ouvrage/livre
4. `chapitre` - Chapitre d'ouvrage
5. `podcast` - Podcast
6. `vidéo` - Vidéo
7. `Lien brisé` - Lien marqué comme brisé
8. `Lien archive` - Lien archivé
9. `interview` - Interview
10. `cite web` - Citation web (anglais)
11. `cite news` - Citation news (anglais)
12. `cite report` - Citation report (anglais)
13. `cite journal` - Citation journal (anglais)
14. `cite book` - Citation book (anglais)

### Exclusions de modification

**TEMPLATES_WITHOUT_SITE_PARAM:**
- `ouvrage` - Livres n'ont pas de "site"
- `chapitre` - Chapitres n'ont pas de "site"

**TEMPLATES_WITHOUT_ARCHIVE_PARAMS:**
- `ouvrage` - Livres ne sont pas des ressources web archivables
- `chapitre` - Chapitres ne sont pas des ressources web archivables

**TEMPLATES_WITHOUT_CONSULTE_LE_PARAM:**
- `ouvrage` - Livres ne sont pas consultés en ligne
- `chapitre` - Chapitres ne sont pas consultés en ligne

### Vérification du traitement des types

**dead_links.py - _is_url_in_reference_scope():**
```python
def _is_url_in_reference_scope(self, content: str, url: str, url_position: int) -> bool:
    # Vérifie si URL est dans <ref>...</ref> OU dans un template de citation
    # Retourne True seulement dans ces cas
```

**Protection correcte:**
- dead_links.py utilise `_is_url_in_reference_scope()` pour limiter aux <ref> et templates
- Cela exclut les URLs dans "Liens externes", "Voir aussi", texte libre

**dead_links.py - _apply_simple_url_replacement():**
```python
# Vérifie si URL est déjà dans un template
template = self._get_cached_reference_template(content, old_url, url_position)
if template:
    logger.info(f"URL already in reference template {template.template_name}, skipping bare URL conversion")
    return content
```

**Protection correcte:**
- Si URL est déjà dans un template, ne convertit pas en bare URL template

**dead_links.py - Vérification patterns académiques:**
```python
academic_patterns = [
    r'\{\{(en|es|de|fr|it|pt|gl|ca|ru|zh|ja)\}\}',  # Language templates
    r'\{\{vol\.\|',  # Volume template
    r'\{\{n[°o]\|',  # Number template
    r'\{\{p\.\|',  # Page template
    r'\{\{ISBN\|',  # ISBN
    r'\{\{OCLC\|',  # OCLC
    r'\{\{ISSN\|',  # ISSN
    r'\{\{DOI\|',  # DOI
    r'\[\[.*?\]\]',  # Wikilinks
]
```

**Protection correcte:**
- Si patterns académiques détectés autour de l'URL, ne convertit pas en {{Lien web}}

### Erreurs potentielles détectées

**1. Modification d'URL dans ouvrage:**
- **Risque**: dead_links.py modifie URLs dans {{ouvrage}}
- **Protection**: `TEMPLATES_WITHOUT_ARCHIVE_PARAMS` exclut ouvrage/chapitre des ajouts d'archive
- **Statut**: PROTÉGÉ

**2. Ajout de site= sur ouvrage:**
- **Risque**: dead_links.py pourrait ajouter |site= sur ouvrage
- **Protection**: `_get_site_parameter_if_missing()` vérifie `TEMPLATES_WITHOUT_SITE_PARAM`
- **Statut**: PROTÉGÉ

**3. Modification de métadonnées:**
- **Risque**: dead_links.py pourrait modifier auteur, titre, éditeur
- **Protection**: reference_template_helper.generate_archive_repair_template() préserve les paramètres existants
- **Statut**: PROTÉGÉ

**4. Remplacement global d'URL:**
- **Risque**: safe_url_replacer pourrait remplacer toutes les occurrences
- **Protection**: `replace_exact_occurrence()` remplace SEULEMENT à la position spécifiée
- **Statut**: PROTÉGÉ

**5. Confusion source bibliographique / cible web:**
- **Risque**: URL dans ouvrage pourrait être traitée comme lien web
- **Protection**: _is_url_in_reference_scope() + _apply_simple_url_replacement() vérifient template existant
- **Statut**: PROTÉGÉ

### Conclusion sur les types de références

Le système distingue CORRECTEMENT les types de références:
- Templates supportés: Lien web, article, interview, podcast, vidéo
- Templates exclus des modifications d'archive: ouvrage, chapitre
- Vérification de template existant avant conversion bare URL
- Vérification de patterns académiques avant conversion

**AUCUNE ERREUR MAJEURE DÉTECTÉE** dans la distinction des types de références.

## 8. ANALYSE DES RÈGLES DE MODIFICATION DU WIKICODE

### A. URL vivante
- **Condition**: result.status == LinkStatus.HEALTHY
- **Décision**: NO_ACTION, pas de modification
- **Fichier**: link_validator.py validate_repair()
- **Validation**: Aucune
- **Enregistrement**: Issue avec link_status=HEALTHY, suggested_text=None

### B. URL HTTP → HTTPS
- **Condition**: HttpLinksAnalyzer détecte http:// + HTTPS vérifié disponible
- **Décision**: Conversion http:// → https://
- **Fichier**: http_links.py _process_bare_http_url()
- **Validation**: HttpsVerificationService
- **Enregistrement**: Issue avec issue_type="http_link", suggested_text=https_url

### C. URL 404
- **Condition**: result.status == LinkStatus.DEAD (404)
- **Décision**: Tente redirect → sinon archive fallback
- **Fichier**: dead_links.py ligne 801+
- **Validation**: LinkValidator + ContentVerifier + ArchiveProvider
- **Enregistrement**: Issue avec repair_status selon résultat

### D. URL 410
- **Condition**: result.status == LinkStatus.DEAD (410)
- **Décision**: Tente redirect → sinon archive fallback
- **Fichier**: dead_links.py ligne 801+
- **Validation**: LinkValidator + ContentVerifier + ArchiveProvider
- **Enregistrement**: Issue avec repair_status selon résultat

### E. URL avec archive disponible
- **Condition**: ArchiveProvider.check_archive() retourne archive_url
- **Décision**: Utilise archive comme remplacement si redirect non disponible
- **Fichier**: dead_links.py _attempt_archive_fallback()
- **Validation**: Vérification HTTP archive + ArchiveContentChecker
- **Enregistrement**: Issue avec archive_url, archive_date, provider

### F. URL morte sans archive
- **Condition**: LinkStatus.DEAD + pas d'archive disponible
- **Décision**: Pas de modification, détection seulement
- **Fichier**: dead_links.py ligne 1291+
- **Validation**: Aucune
- **Enregistrement**: Issue avec repair_status="ARCHIVE_NOT_FOUND"

### G. URL avec redirect
- **Condition**: RedirectFinder.find_redirect() retourne valid_redirect
- **Décision**: Utilise redirect comme candidate pour validation
- **Fichier**: dead_links.py ligne 805+
- **Validation**: ContentVerifier.verify_same_resource()
- **Enregistrement**: Issue avec redirect_decision

### H. URL inaccessible temporairement
- **Condition**: result.status == LinkStatus.TEMPORARY_ERROR
- **Décision**: NO_ACTION, pas de modification
- **Fichier**: link_validator.py validate_repair()
- **Validation**: Aucune
- **Enregistrement**: Issue avec link_status=TEMPORARY_ERROR

### I. URL 403
- **Condition**: result.status == LinkStatus.REVIEW_REQUIRED (403)
- **Décision**: REPAIR_REJECTED, révision manuelle requise
- **Fichier**: link_validator.py validate_repair()
- **Validation**: Aucune
- **Enregistrement**: Issue avec repair_status="REVIEW_REQUIRED"

**Exception**: 403 académique → TEMPORARY_ERROR (link_checker.py)

### J. URL 429
- **Condition**: result.status == LinkStatus.RATE_LIMITED
- **Décision**: NO_ACTION, réessayer plus tard
- **Fichier**: link_validator.py validate_repair()
- **Validation**: Aucune
- **Enregistrement**: Issue avec link_status=RATE_LIMITED

### K. URL 5xx
- **Condition**: result.status == LinkStatus.TEMPORARY_ERROR (5xx)
- **Décision**: NO_ACTION, réessayer plus tard
- **Fichier**: link_validator.py validate_repair()
- **Validation**: Aucune
- **Enregistrement**: Issue avec link_status=TEMPORARY_ERROR

### L. URL déjà archivée
- **Condition**: Template avec archive-url paramètre existant
- **Décision**: Vérifie si archive est valide → si oui skip, si non répare archive seulement
- **Fichier**: dead_links.py ligne 676+
- **Validation**: LinkChecker.check_link(archive_url)
- **Enregistrement**: Issue avec repair_status="ARCHIVE_VALID_SKIP" ou "ARCHIVE_ONLY_REPAIR"

### M. URL contenant déjà archive-url
- **Condition**: Même que L
- **Décision**: Même que L
- **Fichier**: dead_links.py ligne 676+
- **Validation**: Même que L
- **Enregistrement**: Même que L

### N. URL avec archive-url + dead-url/brisé le
- **Condition**: Template avec archive-url + brisé le
- **Décision**: Vérifie archive → si valide skip, si non répare archive
- **Fichier**: dead_links.py ligne 676+
- **Validation**: Même que L
- **Enregistrement**: Même que L

### O. Référence bibliographique contenant une URL
- **Condition**: URL dans {{ouvrage}} ou {{chapitre}}
- **Décision**: Pas d'ajout d'archive (TEMPLATES_WITHOUT_ARCHIVE_PARAMS)
- **Fichier**: dead_links.py + reference_template_helper.py
- **Validation**: Vérification template_name dans TEMPLATES_WITHOUT_ARCHIVE_PARAMS
- **Enregistrement**: Issue avec repair_status selon template

## 9. INVARIANTS À PRÉSERVER

### Invariants identifiés dans le code

1. **Ne jamais modifier une URL vivante inutilement**
   - Implémenté: link_validator.py retourne NO_ACTION pour HEALTHY
   - Vérifié: OUI

2. **Ne jamais modifier une source bibliographique uniquement parce qu'elle contient une URL**
   - Implémenté: TEMPLATES_WITHOUT_ARCHIVE_PARAMS pour ouvrage/chapitre
   - Vérifié: OUI

3. **Ne jamais remplacer une URL sans validation**
   - Implémenté: LinkValidator exige 3 preuves pour REPLACEMENT_CONFIRMED
   - Vérifié: OUI

4. **Ne jamais perdre l'URL originale**
   - Implémenté: Issue.original_text + Issue.extra['old_url']
   - Vérifié: OUI

5. **Ne jamais ajouter une archive sans preuve qu'elle correspond à la ressource**
   - Implémenté: ArchiveContentChecker + vérification HTTP archive
   - Vérifié: OUI

6. **Ne jamais déclarer un lien mort sur une erreur temporaire**
   - Implémenté: TEMPORARY_ERROR → NO_ACTION
   - Vérifié: OUI

7. **Ne jamais modifier une référence entière pour corriger un seul champ**
   - Implémenté: reference_template_helper préserve les paramètres existants
   - Vérifié: OUI

8. **Ne jamais mélanger analyse et enregistrement**
   - Implémenté: PARTIELLEMENT - dead_links.py écrit dans self.issues
   - Vérifié: NON - violation partielle

9. **Ne jamais remplacer toutes les occurrences d'une URL**
   - Implémenté: safe_url_replacer.replace_exact_occurrence()
   - Vérifié: OUI

10. **Ne jamais ajouter |site= sur ouvrage/chapitre**
    - Implémenté: _get_site_parameter_if_missing() vérifie TEMPLATES_WITHOUT_SITE_PARAM
    - Vérifié: OUI

11. **Ne jamais ajouter |consulté le= sur ouvrage/chapitre**
    - Implémenté: reference_template_helper TEMPLATES_WITHOUT_CONSULTE_LE_PARAM
    - Vérifié: OUI

12. **Ne jamais modifier une URL dans un template non supporté sans validation**
    - Implémenté: dead_links.py vérifie template.is_supported
    - Vérifié: OUI

### Invariants NON implémentés ou violés

1. **Séparation analyse/enregistrement**
   - Statut: VIOLÉ
   - Problème: dead_links.py écrit directement dans self.issues

2. **Centralisation de la logique de retry**
   - Statut: VIOLÉ
   - Problème: link_checker.py et dead_links.py ont des logiques de retry différentes

3. **Centralisation de la logique multi-providers**
   - Statut: VIOLÉ
   - Problème: archive_provider.py et dead_links.py ont des logiques de fallback différentes

## 10. TABLEAU FINAL DES PROBLÈMES

| ID | Fichier | Fonction | Problème | Cause | Gravité | Risque | Responsabilité correcte |
|----|---------|----------|----------|-------|---------|-------|-------------------------|
| 1 | dead_links.py | analyze() | Mélange analyse/correction/enregistrement | Architecture monolithique | CRITIQUE | ÉLEVÉ | Séparer en 3 modules distincts |
| 2 | dead_links.py | _attempt_archive_fallback() | Duplication logique fallback multi-providers | Non délégation à archive_provider | ÉLEVÉE | MOYENNE | archive_provider.check_all_providers() |
| 3 | dead_links.py | _consecutive_dns_failures | Logique DNS transient non centralisée | Non déléguée à link_checker | MOYENNE | MOYENNE | link_checker.py |
| 4 | dead_links.py | _apply_simple_url_replacement() | Modification directe du content | Violation séparation analyse/correction | CRITIQUE | ÉLEVÉ | corrector.py |
| 5 | link_checker.py | check_link() | Retry implémenté manuellement | Non utilisation de RetryHandler | MOYENNE | FAIBLE | RetryHandler |
| 6 | corrector.py (utils) | apply_corrections() | Duplication avec publisher.py | Deux implémentations de Corrector | MOYENNE | MOYENNE | Garder une seule version |
| 7 | lien_web_helper.py | generate_archive_repair_template() | Duplication logique template | Non utilisé, logique dans reference_template_helper | FAIBLE | FAIBLE | Déprécier |
| 8 | reference_utils.py | check_link_status() | Fonctions mortes requests | Non utilisées, dépendance requests inutile | FAIBLE | FAIBLE | Supprimer |
| 9 | dead_links.py | _repair_cache | Cache de réparation local | Pas de persistance, contamination entre articles | MOYENNE | MOYENNE | Cache centralisé |
| 10 | dead_links.py | _check_cache | Cache de vérification local | Pas de persistance entre articles | FAIBLE | FAIBLE | Cache centralisé |
| 11 | dead_links.py | _template_cache | Cache de template local | Pas de persistance entre articles | FAIBLE | FAIBLE | Cache centralisé |
| 12 | reference_template_helper.py | generate_archive_repair_template() | Logique complexe de template | Difficile à tester, trop de responsabilités | MOYENNE | MOYENNE | Simplifier |
| 13 | dead_links.py | _build_lien_web_template() | Construction template inline | Logique dupliquée de reference_template_helper | MOYENNE | MOYENNE | reference_template_helper |
| 14 | candidate_finder.py | - | Module non utilisé | Importé mais jamais instancié | FAIBLE | FAIBLE | Supprimer ou utiliser |
| 15 | publisher.py | Corrector class | Duplication corrector | Deux classes Corrector différentes | MOYENNE | MOYENNE | Unifier |

## 11. ARCHITECTURE ACTUELLE VS ARCHITECTURE CIBLE

### Architecture actuelle (monolithique)

```
Article
    ↓
DeadLinkOrchestrator
    ↓
DeadLinkAnalyzer (MONOLITHIQUE)
    ├─ Extraction URLs (url_extraction)
    ├─ Validation syntaxe (url_extraction)
    ├─ Filtrage scope (dead_links)
    ├─ Validation HTTP (link_checker)
    ├─ Classification HTTP (link_checker)
    ├─ Recherche redirect (redirect_finder)
    ├─ Vérification contenu (content_verifier)
    ├─ Recherche archive (archive_provider)
    ├─ Validation archive (archive_content_checker)
    ├─ Décision réparation (link_validator)
    ├─ Construction template (reference_template_helper)
    ├─ Validation template (template_replacement_validator)
    ├─ Modification wikicode (dead_links - PROBLÈME)
    ├─ Enregistrement Issue (dead_links - PROBLÈME)
    └─ Tracking local (dead_links - PROBLÈME)
    ↓
Corrector
    ├─ Application corrections
    └─ Génération diff
    ↓
Publisher
    ├─ Publication Wikipedia
    └─ Tracking published
```

### Architecture cible (modulaire)

```
Article
    ↓
DeadLinkOrchestrator
    ↓
DeadLinkAnalyzer (DÉTECTION SEULE)
    ├─ Extraction URLs (url_extraction)
    ├─ Validation syntaxe (url_extraction)
    ├─ Filtrage scope (url_extraction)
    └─ Retour: List[LinkCandidate]
    ↓
LinkValidator (VALIDATION SEULE)
    ├─ Validation HTTP (link_checker)
    ├─ Classification HTTP (link_checker)
    ├─ Recherche redirect (redirect_finder)
    ├─ Vérification contenu (content_verifier)
    ├─ Recherche archive (archive_provider)
    ├─ Validation archive (archive_content_checker)
    └─ Retour: List[ValidationResult]
    ↓
RepairEngine (RÉPARATION SEULE)
    ├─ Décision réparation (link_validator)
    ├─ Construction template (reference_template_helper)
    ├─ Validation template (template_replacement_validator)
    └─ Retour: List[RepairProposal]
    ↓
Corrector (APPLICATION SEULE)
    ├─ Application corrections
    ├─ Validation diff minimal
    └─ Retour: CorrectedContent
    ↓
TrackingRecorder (ENREGISTREMENT SEULE)
    ├─ Enregistrement détections
    ├─ Enregistrement corrections
    ├─ Enregistrement échecs
    └─ Retour: TrackingSummary
    ↓
Publisher
    ├─ Publication Wikipedia
    └─ Tracking published
```

### Modules à réutiliser correctement

**Existants et bien conçus:**
- `url_extraction.py` - Extraction URLs (OK)
- `url_metadata.py` - Métadonnées URL (OK)
- `link_checker.py` - Validation HTTP (OK, mais utiliser RetryHandler)
- `link_validator.py` - Décision réparation (OK)
- `redirect_finder.py` - Recherche redirect (OK)
- `content_verifier.py` - Vérification contenu (OK)
- `archive_provider.py` - Archives (OK, mais centraliser fallback)
- `archive_content_checker.py` - Validation archive (OK)
- `reference_template_helper.py` - Templates (OK, mais simplifier)
- `safe_url_replacer.py` - Remplacement sécurisé (OK)
- `template_replacement_validator.py` - Validation template (OK)
- `bare_url_helper.py` - Conversion URLs nues (OK)
- `internal_links_writer.py` - Liens internes (OK)

**À supprimer ou déprécier:**
- `lien_web_helper.py` - Duplication de reference_template_helper
- `candidate_finder.py` - Non utilisé
- `reference_utils.py` - Fonctions mortes

**À refactoriser:**
- `dead_links.py` - Scinder en 3 modules (détection, validation, réparation)
- `corrector.py` - Unifier les deux versions

## 12. CE QUI FONCTIONNE CORRECTEMENT

1. **Extraction et validation des URLs** - url_extraction.py fait bien son travail
2. **Validation HTTP avec retry** - link_checker.py robuste
3. **Classification des codes HTTP** - link_checker.py classifie correctement
4. **Recherche de redirects** - redirect_finder.py valide les redirects correctement
5. **Vérification du contenu** - content_verifier.py vérifie correspondance
6. **Recherche multi-providers archives** - archive_provider.py coordonne bien
7. **Validation des archives** - archive_content_checker.py détecte soft-404
8. **Construction de templates** - reference_template_helper.py génère correctement
9. **Validation de templates** - template_replacement_validator.py valide bien
10. **Remplacement sécurisé** - safe_url_replacer.py remplace par position
11. **Distinction des types de références** - Protection ouvrage/chapitre correcte
12. **Protection URLs académiques** - Exclusion domaines académiques correcte
13. **Conversion URLs nues** - bare_url_helper.py convertit correctement
14. **Ajout liens internes** - internal_links_writer.py ajoute correctement

## CE QUI EST CASSÉ

1. **Séparation des responsabilités** - dead_links.py fait tout (détection, validation, correction, enregistrement)
2. **Centralisation du retry** - logique dupliquée entre link_checker et dead_links
3. **Centralisation du fallback multi-providers** - logique dupliquée entre archive_provider et dead_links
4. **Séparation analyse/correction** - dead_links modifie content pendant analyse
5. **Unification corrector** - deux versions différentes de Corrector
6. **Utilisation des helpers spécialisés** - lien_web_helper non utilisé, candidate_finder non utilisé

## CE QUI EST MÉLANGÉ

1. **dead_links.py** - Mélange détection, validation HTTP, recherche redirect, vérification contenu, recherche archive, décision réparation, construction template, validation template, modification wikicode, enregistrement
2. **corrector.py (utils)** - Mélange application corrections + supervision Ollama
3. **publisher.py** - Mélange publication + version simplifiée de corrector

## CE QUI EST DUPLIQUÉ

1. **Retry logic** - link_checker.py vs dead_links.py
2. **Fallback multi-providers** - archive_provider.py vs dead_links.py
3. **Corrector** - utils/corrector.py vs publisher.py
4. **Template generation** - reference_template_helper.py vs lien_web_helper.py
5. **Remplacement sécurisé** - safe_url_replacer.py vs corrector.py

## CE QUI N'EST JAMAIS UTILISÉ

1. **candidate_finder.py** - Importé mais jamais instancié
2. **lien_web_helper.py** - Aucun import direct
3. **reference_utils.py** - Toutes les fonctions sont mortes

## CE QUI DEVRAIT ÊTRE DÉPLACÉ

1. **Logique de correction de dead_links.py** - Vers RepairEngine dédié
2. **Logique d'enregistrement de dead_links.py** - Vers TrackingRecorder dédié
3. **Fallback multi-providers de dead_links.py** - Vers archive_provider.py
4. **Retry de dead_links.py** - Vers RetryHandler centralisé
5. **_build_lien_web_template de dead_links.py** - Vers reference_template_helper.py

## LES RISQUES DE RÉGRESSION

1. **ÉLEVÉ** - dead_links.py modifie content pendant analyse → risque de corruption
2. **ÉLEVÉ** - Logique fallback dupliquée → risque d'incohérence
3. **MOYEN** - Cache local dans dead_links.py → risque de contamination entre articles
4. **MOYEN** - Deux versions de Corrector → risque d'incohérence
5. **FAIBLE** - Fonctions mortes dans reference_utils.py → impact limité

## LES CORRECTIONS PRIORITAIRES

### P0 (CRITIQUE)
1. **Scinder dead_links.py** en 3 modules: DeadLinkDetector, LinkValidator, RepairEngine
2. **Séparer analyse et correction** - dead_links ne doit pas modifier content
3. **Centraliser fallback multi-providers** dans archive_provider.py

### P1 (ÉLEVÉE)
4. **Unifier Corrector** - supprimer une des deux versions
5. **Centraliser retry** - utiliser RetryHandler partout
6. **Créer TrackingRecorder** - séparer enregistrement de l'analyse

### P2 (MOYENNE)
7. **Supprimer lien_web_helper.py** - déprécier
8. **Supprimer candidate_finder.py** - non utilisé
9. **Nettoyer reference_utils.py** - supprimer fonctions mortes
10. **Centraliser cache** - cache partagé entre modules

### P3 (FAIBLE)
11. **Simplifier reference_template_helper.py** - réduire complexité
12. **Améliorer tests** - couverture complète des modules scindés

---

**CONCLUSION DE L'AUDIT**

Le système DeadLink fonctionne correctement dans ses aspects techniques (validation HTTP, recherche archives, construction templates, protection des types de références). Cependant, il souffre d'un problème architectural majeur: **dead_links.py est un monolithe qui fait tout**, violant le principe de séparation des responsabilités.

Les corrections prioritaires sont:
1. Scinder dead_links.py en modules spécialisés
2. Séparer analyse et correction
3. Centraliser la logique dupliquée (retry, fallback multi-providers)
4. Unifier les versions de Corrector

Les risques de régression sont principalement liés à la modification directe du content pendant l'analyse et à la logique dupliquée entre modules.


//////////Je vais réaliser l'Audit 2 sur l'architecture Tracking/Enregistrement, puis l'Audit 3 sur la classification des références et la sécurité des modifications.

Je vais analyser en profondeur le système de tracking/enregistrement. Commençons par lire les fichiers manquants.

Je poursuis l'Audit 2 sur l'architecture Tracking/Enregistrement. Laissez-moi lire quelques fichiers supplémentaires pour comprendre le flux complet.

Je vais maintenant réaliser l'Audit 3 sur la classification des références et la sécurité des modifications.

# AUDIT 2 : ARCHITECTURE TRACKING/ENREGISTREMENT

## 1. CARTOGRAPHIE COMPLÈTE DES SYSTÈMES DE TRACKING

### A. Systèmes de tracking identifiés

| Module | Type de stockage | Responsabilité | Tables/Fichiers | Statut |
|--------|-----------------|----------------|----------------|--------|
| **analyzed_tracker.py** | JSON (`analyzed_articles.json`) | Suivi des articles analysés | AnalysisRecord, AnalysisStatus | ACTIF |
| **published_tracker.py** | JSON (`published_articles.json`) | Suivi des articles publiés | published_articles dict | ACTIF |
| **automation_state.py** | JSON (`automation_state.json`) | État des sessions d'automatisation | AutomationSessionState, ArticleState | PARTIELLEMENT REMPLACÉ |
| **automation_state_sqlite.py** | SQLite | État des sessions d'automatisation (SQLite) | automation_sessions, automation_article_states, automation_interruptions | ACTIF |
| **pending_publish_queue.py** | JSON (`pending_publish_queue.json`) | File d'attente de publication | PendingArticle | ACTIF |
| **database.py** | SQLite (`wikipedia_maintenance.db`) | Base de données principale | 20+ tables | ACTIF |
| **event_manager.py** | Mémoire (queue) | Événements temps réel (SSE) | Event queue | ACTIF |
| **lia_logger.py** | Fichier (`lia_operations.log`, `published_articles.log`) | Logging des opérations | Fichiers texte | ACTIF |

### B. Tables principales dans DatabaseManager (SQLite)

| Table | Responsabilité | Colonnes clés | Relations |
|-------|----------------|---------------|-----------|
| **articles** | Articles analysés | title, page_id, last_revision_id, status | → issues, actions |
| **issues** | Problèmes détectés | article_id, issue_type, position, original_text, suggested_text | ← articles |
| **actions** | Actions utilisateur | article_id, action_type, edit_summary, revision_id | ← articles |
| **sessions** | Sessions d'analyse | source_type, articles_analyzed, articles_approved | - |
| **analysis_jobs** | Jobs d'analyse | article_title, mode, status, progress | → analysis_results |
| **analysis_results** | Résultats d'analyse | article_title, status, changes_count, original_content, corrected_content | ← analysis_jobs |
| **articles_to_analyze** | File d'attente d'analyse | title, page_id, revision_id, status, priority | → analysis_jobs |
| **manual_review_decisions** | Décisions de révision manuelle | article_title, url, status, decision_date | ← articles |
| **https_verification_cache** | Cache HTTPS | domain, status, https_url, expires_at | - |
| **scheduler_queue** | File d'attente du scheduler | article_title, corrected_content, status, priority | - |
| **scheduler_state** | État du scheduler | is_active, is_paused, daily_published_count | - |
| **automation_sessions** | Sessions d'automatisation | session_id, status, articles_processed | → automation_article_states |
| **automation_article_states** | États des articles en automation | session_id, article_title, status, progress | ← automation_sessions |
| **automation_interruptions** | Interruptions d'automatisation | session_id, timestamp, reason | ← automation_sessions |
| **kill_switch_state** | État du kill switch | enabled, reason, trigger_source | - |
| **automation_lock** | Verrou d'automatisation | locked, locked_by, session_id | - |

### C. Flux de données actuel

```
DeadLinkAnalyzer.analyze()
    ↓
self.issues.append(Issue(...))  # Liste en mémoire
    ↓
Orchestrator.analyze()
    ↓
Corrector.apply_corrections(issues)
    ↓
self.corrections.append(Correction(...))  # Liste en mémoire
    ↓
Corrector.get_corrected_content()
    ↓
Publication
    ↓
[PARALLÈLE 1] PublishedTracker.mark_as_published() → JSON
    ↓
[PARALLÈLE 2] DatabaseManager.update_article_status() → SQLite
    ↓
[PARALLÈLE 3] AnalyzedTracker.record_analysis() → JSON
    ↓
[PARALLÈLE 4] AutomationStateManager.update_status() → JSON
    ↓
[PARALLÈLE 5] SQLiteAutomationStateManager.update_status() → SQLite
    ↓
[PARALLÈLE 6] lia_logger.log_published_article() → Fichier log
    ↓
[PARALLÈLE 7] EventManager.emit() → Queue mémoire
```

## 2. PROBLÈMES IDENTIFIÉS

### A. Absence de source unique de vérité

**Problème critique:** Les informations de tracking sont dispersées entre 7+ systèmes différents sans coordination.

| Information | Système 1 | Système 2 | Système 3 | Système 4 | Système 5 | Système 6 | Système 7 |
|-------------|-----------|-----------|-----------|-----------|-----------|-----------|-----------|
| Article analysé | AnalyzedTracker | Database.articles | automation_article_states | - | - | - | - |
| URL originale | Issue.extra | - | - | - | - | - | - |
| URL corrigée | Issue.extra | - | - | - | - | - | - |
| Archive URL | Issue.extra | - | - | - | - | - | - |
| Statut réparation | Issue.extra.repair_status | - | - | - | - | - | - |
| Correction appliquée | Correction.applied | - | - | - | - | - | - |
| Article publié | PublishedTracker | Database.actions | automation_article_states | - | - | - | - |
| Revision ID | PublishedTracker | Database.actions | automation_article_states | - | - | - | - |
| Résumé de modification | Database.actions | PublishedTracker | - | - | - | - | - |

**Conséquence:** Impossible de reconstituer l'historique complet d'une correction en consultant une seule source.

### B. Duplication des systèmes de tracking

**Problème majeur:** Deux systèmes parallèles pour la même fonctionnalité.

| Fonctionnalité | Système A | Système B | Risque |
|---------------|-----------|-----------|--------|
| Tracking articles analysés | AnalyzedTracker (JSON) | Database.articles + automation_article_states (SQLite) | Incohérence |
| Tracking articles publiés | PublishedTracker (JSON) | Database.actions + scheduler_queue (SQLite) | Incohérence |
| Tracking sessions d'automatisation | AutomationStateManager (JSON) | SQLiteAutomationStateManager (SQLite) | Incohérence |
| Cache de réparation | dead_links._repair_cache (mémoire) | Aucun | Perte sur crash |
| Cache de vérification | dead_links._check_cache (mémoire) | Aucun | Perte sur crash |

### C. Écriture directe depuis l'analyseur

**Problème critique:** `dead_links.py` écrit directement dans `self.issues` sans passer par un système de tracking centralisé.

```python
# dead_links.py ligne 568-585
self.issues.append(Issue(
    issue_type="dead_link",
    description=f"Lien mort remplacé : {old_url} → {new_url}",
    position=url_position,
    original_text=old_url,
    suggested_text=new_url,
    severity="high",
    confidence=1.0,
    extra={
        'url': url,
        'old_url': old_url,
        'new_url': new_url,
        'http_status_code': result.http_status,
        'repair_decision': cached_decision.get('decision'),
        'cached': True,
        'repair_status': 'REPAIR_APPLIED'
    }
))
```

**Conséquence:** L'analyseur mélange détection et enregistrement, violant la séparation des responsabilités.

### D. Information dispersée dans Issue.extra

**Problème majeur:** Les informations de tracking sont stockées dans `Issue.extra` de manière non structurée.

```python
extra={
    'url': url,                           # Dupliqué avec original_text
    'old_url': old_url,                    # Dupliqué avec original_text
    'new_url': new_url,                    # Dupliqué avec suggested_text
    'http_status_code': result.http_status,
    'repair_decision': cached_decision.get('decision'),
    'cached': True,
    'repair_status': 'REPAIR_APPLIED',
    'archive_url': archive_url,            # Si applicable
    'archive_date': archive_date,          # Si applicable
    'provider': provider,                  # Si applicable
    'template_name': template_name,        # Si applicable
    'repair_type': 'template'              # Si applicable
}
```

**Conséquence:** Impossible de faire des requêtes structurées sur ces données.

### E. Pas de corrélation entre Issue et Correction

**Problème majeur:** `Issue` (détection) et `Correction` (application) ne sont pas corrélées.

| Structure | Fichier | Champs | Corrélation |
|-----------|---------|--------|-------------|
| Issue | dead_links.py | issue_type, position, original_text, suggested_text, extra | Aucune |
| Correction | corrector.py | issue, applied, original_snippet, corrected_snippet | Issue object |

**Conséquence:** Impossible de tracer quelles détections ont été appliquées et lesquelles ont été rejetées.

### F. Pas de tracking granulaire par URL

**Problème majeur:** Le tracking se fait au niveau de l'article, pas au niveau de l'URL.

| Niveau de tracking | Actuel | Idéal |
|-------------------|--------|-------|
| Article | ✅ OUI | ✅ OUI |
| Référence/template | ❌ NON | ✅ OUI |
| URL individuelle | ❌ NON | ✅ OUI |
| Paramètre spécifique | ❌ NON | ✅ OUI |

**Conséquence:** Impossible de répondre à "Quelle URL dans quel template a été modifiée quand ?"

### G. Caches locaux non persistants

**Problème moyen:** Les caches dans `dead_links.py` sont en mémoire et perdus sur crash.

```python
# dead_links.py
self._check_cache = {}           # Cache de vérification (non persistant)
self._repair_cache = {}          # Cache de réparation (non persistant)
self._template_cache = {}        # Cache de templates (non persistant)
```

**Conséquence:** Sur crash, l'automatisation peut retraiter les mêmes URLs ou perdre l'état.

## 3. QUI ENREGISTRE QUOI

### A. DeadLinkAnalyzer (dead_links.py)

**Enregistre:** `self.issues.append(Issue(...))`

**Quand:** Immédiatement après détection/correction

**Informations enregistrées:**
- type d'issue: "dead_link"
- position: position dans le wikicode
- original_text: URL originale
- suggested_text: URL corrigée ou template
- extra: 
  - url: URL
  - old_url: URL originale (dupliqué)
  - new_url: URL corrigée (dupliqué)
  - http_status_code: code HTTP
  - repair_decision: décision de réparation
  - repair_status: statut de réparation
  - archive_url: URL d'archive (si applicable)
  - archive_date: date d'archive (si applicable)
  - provider: fournisseur d'archive (si applicable)
  - template_name: nom du template (si applicable)

**Problème:** Écriture directe, pas de persistance, information dispersée dans extra

### B. Corrector (corrector.py - utils)

**Enregistre:** `self.corrections.append(Correction(...))`

**Quand:** Après application de la correction

**Informations enregistrées:**
- issue: Issue object complet
- applied: True/False
- original_snippet: texte original (si disponible)
- corrected_snippet: texte corrigé (si disponible)
- start: position de début
- end: position de fin

**Problème:** Liste séparée de Issue, pas de corrélation

### C. PublishedTracker (published_tracker.py)

**Enregistre:** `self.published_articles[article_title] = entry`

**Quand:** Après publication réussie

**Informations enregistrées:**
- published_at: timestamp
- category: catégorie de l'article
- mode: mode de traitement
- summary: résumé de modification
- revision_id: ID de révision (si disponible)

**Problème:** Stockage JSON simple, pas de tracking par URL

### D. AnalyzedTracker (analyzed_tracker.py)

**Enregistre:** `self._records[title] = AnalysisRecord(...)`

**Quand:** Après analyse de l'article

**Informations enregistrées:**
- title: titre de l'article
- page_id: ID de page
- revision_id: ID de révision
- analysis_date: date d'analyse
- status: statut (pending, published, rejected, etc.)
- score: score d'analyse
- decision: décision finale
- mode: mode d'analyse
- changes_count: nombre de changements
- summary: résumé
- original_content: contenu original
- corrected_content: contenu corrigé
- character_count: nombre de caractères
- total_links: nombre total de liens
- dead_links_count: nombre de liens morts
- corrected_links_count: nombre de liens corrigés
- human_verified: vérification humaine
- manual_review_urls: URLs nécessitant révision

**Problème:** Stockage JSON lourd (contenu complet), pas de tracking granulaire

### E. DatabaseManager (database.py)

**Enregistre:** Multiple tables SQLite

**Quand:** À différentes étapes du pipeline

**Informations enregistrées:**
- articles: articles analysés
- issues: problèmes détectés
- actions: actions utilisateur
- analysis_results: résultats d'analyse complets
- manual_review_decisions: décisions de révision
- scheduler_queue: file d'attente de publication
- automation_sessions: sessions d'automatisation
- automation_article_states: états des articles

**Problème:** Pas de table dédiée aux DeadLink corrections

### F. LiaLogger (lia_logger.py)

**Enregistre:** Fichiers texte JSON

**Quand:** Opérations LIA et publications

**Informations enregistrées:**
- lia_operations.log: opérations LIA (article, operation, timestamp, details)
- published_articles.log: articles publiés (article, mode, timestamp, summary, changes)

**Problème:** Logging non structuré, difficile à interroger

## 4. AUDIT 3 : CLASSIFICATION DES RÉFÉRENCES ET SÉCURITÉ DES MODIFICATIONS

## A. Qui détermine le type de template ?

**Responsable:** `ReferenceTemplateHelper.find_reference_template()`

**Comment:** Analyse le wikicode pour trouver le template parent de l'URL

**Processus:**
1. Recherche en arrière depuis la position de l'URL
2. Cherche `{{` pour trouver le début du template
3. Analyse le nom du template (entre `{{` et `|` ou `|`)
4. Parse les paramètres
5. Retourne `ReferenceTemplate` avec `template_name` et `is_supported`

**Résultat:** Le type de template est déterminé avant toute décision de modification.

## B. Qui autorise la modification d'une URL ?

**Responsable:** `DeadLinkAnalyzer._is_url_in_reference_scope()`

**Comment:** Vérifie que l'URL est dans un périmètre autorisé

**Critères d'autorisation:**
```python
def _is_url_in_reference_scope(self, content: str, url: str, url_position: int) -> bool:
    # Vérifie si URL est dans <ref>...</ref>
    for ref_match in re.finditer(r'<ref[^>]*>(.*?)</ref>', content, re.DOTALL):
        if ref_match.start() <= url_position < ref_match.end():
            return True
    
    # Vérifie si URL est dans un template de citation reconnu
    template = self._get_cached_reference_template(content, url, url_position)
    return template is not None
```

**Autorisation:** URL modifiable seulement si:
- Dans un `<ref>...</ref>` OU
- Dans un template de citation reconnu (Lien web, article, ouvrage, etc.)

**Protection:** URLs hors périmètre (Liens externes, Voir aussi, texte libre) sont exclues.

## C. Qui applique les restrictions par type de template ?

**Responsable:** `ReferenceTemplateHelper` via 3 listes noires

### 1. TEMPLATES_WITHOUT_SITE_PARAM

```python
TEMPLATES_WITHOUT_SITE_PARAM = {'ouvrage', 'chapitre'}
```

**Protection:** Ne jamais ajouter `|site=` à ouvrage/chapitre

**Où utilisé:**
- `_get_site_parameter_if_missing()` (dead_links.py)
- `generate_archive_repair_template()` (reference_template_helper.py)
- `add_enrichment()` (reference_template_helper.py)

### 2. TEMPLATES_WITHOUT_ARCHIVE_PARAMS

```python
TEMPLATES_WITHOUT_ARCHIVE_PARAMS = {'ouvrage', 'chapitre'}
```

**Protection:** Ne jamais ajouter `archive-url`, `archive-date`, `brisé le` à ouvrage/chapitre

**Où utilisé:**
- `generate_archive_repair_template()` (reference_template_helper.py)

### 3. TEMPLATES_WITHOUT_CONSULTE_LE_PARAM

```python
TEMPLATES_WITHOUT_CONSULTE_LE_PARAM = {'ouvrage', 'chapitre'}
```

**Protection:** Ne jamais ajouter `|consulté le=` à ouvrage/chapitre

**Où utilisé:**
- `generate_archive_repair_template()` (reference_template_helper.py)

## D. Qui vérifie le template avant modification ?

**Responsable:** `DeadLinkAnalyzer._get_cached_reference_template()`

**Comment:** Récupère le template parent et vérifie `is_supported`

**Processus:**
1. Cherche le template via `ReferenceTemplateHelper.find_reference_template()`
2. Vérifie `template.is_supported`
3. Si non supporté, marque pour révision manuelle

**Code:**
```python
# dead_links.py ligne 926-927
if not template.is_supported:
    # Attempt partial safe repair
```

## E. Qui empêche la modification d'URL dans ouvrage ?

**Protection en couches:**

### Couche 1: `_is_url_in_reference_scope()`
- Autorise les URLs dans ouvrage (car c'est un template de citation)
- **PROBLÈME:** Cette couche N'EXCLUT PAS ouvrage

### Couche 2: `TEMPLATES_WITHOUT_ARCHIVE_PARAMS`
- Exclut l'ajout d'archive params à ouvrage
- **Où:** `generate_archive_repair_template()`

### Couche 3: `TEMPLATES_WITHOUT_SITE_PARAM`
- Exclut l'ajout de `|site=` à ouvrage
- **Où:** `_get_site_parameter_if_missing()`

### Couche 4: `is_supported`
- Marque les templates non supportés pour révision manuelle
- **Où:** Dans la boucle de traitement

**ANALYSE CRITIQUE:** La couche 1 autorise les URLs dans ouvrage, mais les couches 2-4 limitent CE QUI PEUT ÊTRE AJOUTÉ. Cela signifie qu'une URL dans ouvrage peut être détectée comme DeadLink, mais les protections empêchent l'ajout d'archive params.

**Cependant, il y a un problème potentiel:** Si le code ne vérifie pas correctement le type de template AVANT de tenter la modification, une URL dans ouvrage pourrait être modifiée par un chemin de code qui contourne les protections.

## F. Qui construit la correction ?

**Responsable:** `DeadLinkAnalyzer._apply_simple_url_replacement()`

**Comment:** Construit la correction en fonction du contexte

**Processus:**
1. Vérifie si URL est dans un template existant
2. Si oui, utilise `generate_archive_repair_template()`
3. Si non, vérifie si c'est une URL nue et construit un template
4. Applique les protections selon le type de template

**Code de protection:**
```python
# dead_links.py ligne 1743-1746
template = self._get_cached_reference_template(content, old_url, url_position)
if template:
    logger.info(f"URL already in reference template {template.template_name}, skipping bare URL conversion")
    return content
```

## G. Qui applique réellement la modification ?

**Responsable:** `Corrector.apply_corrections()` (utils/corrector.py ou publisher.py)

**Comment:** Applique les corrections basées sur `Issue.suggested_text` et `Issue.position`

**Processus:**
1. Trie les issues par position (ordre descendant)
2. Pour chaque issue:
   - Vérifie que le texte original match à la position
   - Remplace par suggested_text
   - Enregistre Correction object

**Code de sécurité:**
```python
# corrector.py ligne 186-192
if self.strict_position_check:
    actual_text = self.current_content[start:end]
    if actual_text != original_text:
        logger.warning(f"Text mismatch at position {start}")
        return False
```

## H. QUI DÉTECTE VS QUI AUTORISE - ANALYSE DU FLUX

```
URL détectée (url_extraction.py)
    ↓
Dans périmètre autorisé ? (_is_url_in_reference_scope)
    ↓
[SI NON] → SKIP
    ↓
[SI OUI] → Template parent ? (find_reference_template)
    ↓
[SI OUI] → Type de template (ouvrage/article/Lien web/etc)
    ↓
Type supporté ? (is_supported)
    ↓
[SI NON] → REVIEW_REQUIRED
    ↓
[SI OUI] → Validation HTTP (link_checker)
    ↓
Statut DEAD ? (LinkStatus.DEAD)
    ↓
[SI NON] → SKIP (HEALTHY/TEMPORARY/etc)
    ↓
[SI OUI] → Recherche redirect (redirect_finder)
    ↓
Redirect valide ? → Validation contenu (content_verifier)
    ↓
Redirect non valide ? → Archive fallback (archive_provider)
    ↓
Decision de réparation (link_validator)
    ↓
REPLACEMENT_CONFIRMED ?
    ↓
[SI OUI] → Type de template (ouvrage/article/etc)
    ↓
TEMPLATE_WITHOUT_ARCHIVE_PARAMS ?
    ↓
[SI OUI - ouvrage/chapitre] → PAS d'archive params
    ↓
[SI NON] → Construction correction (generate_archive_repair_template)
    ↓
Application correction (corrector)
    ↓
Enregistrement (multiple systèmes)
```

## I. PROBLÈME CRITIQUE IDENTIFIÉ

**Le flux ci-dessus montre une faille potentielle:**

L'autorisation de modification (`_is_url_in_reference_scope()`) se fait TRÈS TÔT dans le pipeline, avant de connaître:
- Le type de template
- Le statut HTTP
- La décision de réparation

**Conséquence:** Une URL dans ouvrage EST AUTORISÉE à entrer dans le pipeline DeadLink. Les protections `TEMPLATES_WITHOUT_*` s'appliquent SEULEMENT lors de la construction de la correction, PAS lors de la détection.

**Scénario à risque:**
1. URL dans `{{ouvrage|url=https://example.com}}` est détectée
2. `_is_url_in_reference_scope()` retourne True (car dans un template)
3. `find_reference_template()` identifie ouvrage
4. Validation HTTP: 404 → DEAD
5. Archive fallback: archive trouvée
6. LinkValidator: REPLACEMENT_CONFIRMED
7. `_apply_simple_url_replacement()` appelé
8. **Si ce code ne vérifie pas le type de template avant de construire la correction**, il pourrait tenter d'ajouter des archive params

**Vérification du code:**
```python
# dead_links.py ligne 914-920
is_reference_template_repair = False
template_name = None
if repair_result and repair_result.details and repair_result.details.get('is_reference_template'):
    is_reference_template_repair = True
    template_name = repair_result.details.get('template_name')
```

**Le code DÉPEND de `repair_result.details.get('is_reference_template')` pour savoir si c'est un template. Mais `is_reference_template` est défini dans `_attempt_archive_fallback()`:**

```python
# dead_links.py ligne 1544
repair_details = {
    'archive_url': archive_url,
    'archive_date': archive_date,
    'provider': provider_name,
    'is_reference_template': is_reference_template,  # ← Défini ici
    'template_name': template_name,
    ...
}
```

Et `is_reference_template` est déterminé par:
```python
# dead_links.py ligne 1541
is_reference_template = template is not None
```

**CONCLUSION:** Le code vérifie correctement le type de template avant de construire la correction. Les protections `TEMPLATES_WITHOUT_*` sont appliquées dans `generate_archive_repair_template()`.

**Cependant, il y a un problème:** Le pipeline autorise des URLs dans ouvrage à entrer dans le système DeadLink, même si elles ne peuvent pas être corrigées. Cela consomme des ressources inutilement et peut créer des faux positifs dans les logs.

## J. SYNTHÈSE DES PROBLÈMES DE SÉCURITÉ

| ID | Problème | Localisation | Gravité | Risque |
|----|----------|--------------|---------|-------|
| S1 | URLs dans ouvrage entrent dans pipeline DeadLink | `_is_url_in_reference_scope()` | MOYENNE | Faux positifs, consommation ressources |
| S2 | Pas de vérification du type de template lors de la détection | dead_links.py | MOYENNE | État actuel acceptable mais sous-optimal |
| S3 | Protections `TEMPLATES_WITHOUT_*` appliquées tardivement | reference_template_helper.py | FAIBLE | Fonctionnel mais tardif |
| S4 | Cache de réparation local non persistant | dead_links.py | MOYENNE | Perte d'état sur crash |
| S5 | Information de tracking dispersée | Multiple fichiers | CRITIQUE | Impossible de tracer les corrections |
| S6 | Pas de corrélation Issue ↔ Correction | dead_links.py + corrector.py | ÉLEVÉE | Impossible d'auditer les modifications |
| S7 | Pas de tracking granulaire par URL | Tous systèmes | MOYENNE | Impossible de répondre "quelle URL modifiée quand ?" |

## K. RECOMMANDATIONS PRIORITAIRES

### P0 (CRITIQUE)
1. **Créer un système de tracking centralisé** - Un seul système pour enregistrer toutes les opérations DeadLink
2. **Corréler Issue et Correction** - Lier chaque détection à son application
3. **Ajouter tracking granulaire par URL** - Table dédiée aux corrections DeadLink

### P1 (ÉLEVÉE)
4. **Pré-filtrer par type de template** - Exclure ouvrage/chapitre de l'entrée dans le pipeline DeadLink
5. **Persister les caches** - _check_cache, _repair_cache, _template_cache
6. **Consolider les systèmes de tracking** - Choisir SQLite comme source unique de vérité

### P2 (MOYENNE)
7. **Améliorer les logs** - Structurer les informations de tracking
8. **Ajouter audit trail** - Historique complet des modifications par URL

---

# CONCLUSION DES DEUX AUDITS

## Audit 2 - Tracking/Enregistrement

**État actuel:** Chaos organisationnel avec 7+ systèmes de tracking parallèles, aucune source unique de vérité, information dispersée entre Issue.extra, Correction, et multiples fichiers/tables.

**Problème critique:** L'analyseur écrit directement dans self.issues sans passer par un système de tracking centralisé, mélangeant détection et enregistrement.

**Risque élevé:** Impossible de tracer l'historique complet d'une correction, de répondre "quelle URL modifiée quand ?", ou de reconstituer l'état après crash.

## Audit 3 - Classification des références

**État actuel:** Protections existent (`TEMPLATES_WITHOUT_SITE_PARAM`, `TEMPLATES_WITHOUT_ARCHIVE_PARAMS`, `TEMPLATES_WITHOUT_CONSULTE_LE_PARAM`) mais sont appliquées tardivement dans le pipeline.

**Problème moyen:** Les URLs dans ouvrage/chapitre sont autorisées à entrer dans le pipeline DeadLink même si elles ne peuvent pas être corrigées, créant des faux positifs et consommant des ressources.

**Risque moyen:** Les protections fonctionnent correctement lors de la construction de la correction, mais le système pourrait être optimisé en pré-filtrant par type de template.

---

# RECOMMANDATION FINALE

**NE PAS REFACTORISER MAINTENANT.**

Les deux audits révèlent des problèmes structurels importants, mais les protections fondamentales sont en place. Les risques identifiés sont réels mais gérables.

**Plan recommandé:**
1. Créer un système de tracking centralisé (P0)
2. Corréler Issue et Correction (P0)
3. Ajouter tracking granulaire par URL (P0)
4. Pré-filtrer par type de template (P1)
5. Consolider les systèmes de tracking (P1)
6. **Ensuite seulement:** scinder dead_links.py en modules spécialisés


/////////


Je vais réaliser l'Audit 4 sur la chaîne de modification en traçant les 4 scénarios réels de bout en bout.

Je vais tracer les 4 scénarios de modification en détail pour identifier les chemins exacts.

Je vais maintenant tracer les 4 scénarios de modification exacts et identifier les chemins potentiels de contournement.

# AUDIT 4 : AUDIT DE LA CHAÎNE DE MODIFICATION

## SCÉNARIO 1 : {{Lien web|url=https://site.com|titre=...}} avec 404

### Flux de modification

```
Wikicode: {{Lien web|url=https://site.com|titre=...}}
    ↓
UrlExtractor détecte l'URL (regex URL_PATTERN)
    ↓
_is_url_in_reference_scope() → True (dans <ref> OU template)
    ↓
_get_cached_reference_template() → template = ReferenceTemplate(template_name='Lien web', is_supported=True)
    ↓
LinkChecker.check_link() → 404 → LinkStatus.DEAD
    ↓
RedirectFinder.find_redirect() → redirect_result
    ↓
ContentVerifier.verify_same_resource() → content_result
    ↓
ArchiveProvider.verify_content_match() → archive_evidence
    ↓
LinkValidator.validate_repair() → RepairResult.decision = REPLACEMENT_CONFIRMED
    ↓
[Branche ligne 916] is_reference_template_repair = True (car repair_result.details.get('is_reference_template') = True)
    ↓
[Branche ligne 921] if is_reference_template_repair:
    ↓
_get_cached_reference_template() → template avec template_name='Lien web'
    ↓
[Branche ligne 926] if not template.is_supported → NON (Lien web est supporté)
    ↓
_get_site_parameter_if_missing() → ajoute |site= si absent
    ↓
reference_template_helper.generate_archive_repair_template()
    ↓
[Vérification ligne 634] normalized_template_name in TEMPLATES_WITHOUT_ARCHIVE_PARAMS
    ↓
'lien web' NOT IN {'ouvrage', 'chapitre'} → archive params AUTORISÉS
    ↓
params['url'] = archive_url (ou original_url selon assume_patch_deployed)
    ↓
params['archive-url'] = archive_url
    ↓
params['archive-date'] = archive_date
    ↓
params['brisé le'] = current_date
    ↓
Validate template → OK
    ↓
Issue créée avec suggested_text = nouveau template complet
    ↓
Corrector.apply_corrections() → remplace template entier à la position
```

### Point de modification
- **Qui modifie:** `reference_template_helper.generate_archive_repair_template()` construit le nouveau template
- **Qui applique:** `Corrector.apply_corrections()` remplace le template à la position
- **Portée:** Template entier remplacement
- **Sécurité:** TEMPLATES_WITHOUT_ARCHIVE_PARAMS vérifié, Lien web autorisé à recevoir archive params

### Chemins de contournement potentiels
- **Aucun détecté** - Le flux est sécurisé par les vérifications de template

---

## SCÉNARIO 2 : {{ouvrage|url=https://site.com|titre=...}} avec 404

### Flux de modification

```
Wikicode: {{ouvrage|url=https://site.com|titre=...}}
    ↓
UrlExtractor détecte l'URL (regex URL_PATTERN)
    ↓
_is_url_in_reference_scope() → True (dans template)
    ↓
_get_cached_reference_template() → template = ReferenceTemplate(template_name='ouvrage', is_supported=True)
    ↓
LinkChecker.check_link() → 404 → LinkStatus.DEAD
    ↓
RedirectFinder.find_redirect() → redirect_result
    ↓
ContentVerifier.verify_same_resource() → content_result
    ↓
ArchiveProvider.verify_content_match() → archive_evidence
    ↓
LinkValidator.validate_repair() → RepairResult.decision = REPLACEMENT_CONFIRMED
    ↓
[Branche ligne 916] is_reference_template_repair = True (car repair_result.details.get('is_reference_template') = True)
    ↓
[Branche ligne 921] if is_reference_template_repair:
    ↓
_get_cached_reference_template() → template avec template_name='ouvrage'
    ↓
[Branche ligne 926] if not template.is_supported → NON (ouvrage est supporté)
    ↓
_get_site_parameter_if_missing() → vérifie template_name in TEMPLATES_WITHOUT_SITE_PARAM
    ↓
'ouvrage' IN {'ouvrage', 'chapitre'} → retourne None (ligne 239-240)
    ↓
reference_template_helper.generate_archive_repair_template()
    ↓
[Vérification ligne 634] normalized_template_name in TEMPLATES_WITHOUT_ARCHIVE_PARAMS
    ↓
'ouvrage' IN {'ouvrage', 'chapitre'} → RETOURNE original_template.full_match (ligne 635-638)
    ↓
AUCUNE MODIFICATION APPLIQUÉE
    ↓
Issue créée avec suggested_text = None (pas de modification)
```

### Point de modification
- **Qui modifie:** Aucun
- **Qui applique:** Aucun
- **Portée:** Aucune modification
- **Sécurité:** TEMPLATES_WITHOUT_ARCHIVE_PARAMS BLOQUE la modification

### Chemins de contournement potentiels
- **Aucun détecté** - La protection est en place et fonctionne correctement

---

## SCÉNARIO 3 : <ref>https://site.com</ref> avec 404

### Flux de modification

```
Wikicode: <ref>https://site.com</ref>
    ↓
UrlExtractor détecte l'URL (regex URL_PATTERN)
    ↓
_is_url_in_reference_scope() → True (dans <ref>)
    ↓
_get_cached_reference_template() → template = None (pas de template)
    ↓
LinkChecker.check_link() → 404 → LinkStatus.DEAD
    ↓
RedirectFinder.find_redirect() → redirect_result
    ↓
ContentVerifier.verify_same_resource() → content_result
    ↓
ArchiveProvider.verify_content_match() → archive_evidence
    ↓
LinkValidator.validate_repair() → RepairResult.decision = REPLACEMENT_CONFIRMED
    ↓
[Branche ligne 916] is_reference_template_repair = False (car template = None)
    ↓
[Branche ligne 1091] else: → _apply_simple_url_replacement()
    ↓
[Branche ligne 1743] template = _get_cached_reference_template() → None
    ↓
[Branche ligne 1748-1771] Vérification patterns académiques → NON (pas de patterns)
    ↓
[Branche ligne 1774] bare_refs = bare_url_helper.find_bare_urls(content)
    ↓
[Branche ligne 1777-1781] matching_ref trouvé (URL nue détectée comme bare URL)
    ↓
[Branche ligne 1824] template_str = bare_url_helper.build_repaired_reference_template()
    ↓
BareUrlHelper.build_repaired_reference_template()
    ↓
[Vérification dans BareUrlHelper] final_archive_url validation → archive URL valide
    ↓
[Vérification dans BareUrlHelper] resolved_template_name = 'Lien web' (par défaut)
    ↓
[Vérification dans BareUrlHelper] template_helper.generate_archive_repair_template()
    ↓
[Vérification ligne 634] normalized_template_name in TEMPLATES_WITHOUT_ARCHIVE_PARAMS
    ↓
'lien web' NOT IN {'ouvrage', 'chapitre'} → archive params AUTORISÉS
    ↓
params['url'] = original_url (conserve URL originale)
    ↓
params['archive-url'] = archive_url
    ↓
params['archive-date'] = archive_date
    ↓
params['brisé le'] = current_date
    ↓
Issue créée avec suggested_text = {{Lien web|url=original|archive-url=archive|...}}
    ↓
Corrector.apply_corrections() → remplace URL nue par template complet
```

### Point de modification
- **Qui modifie:** `BareUrlHelper.build_repaired_reference_template()` construit le template
- **Qui applique:** `Corrector.apply_corrections()` remplace l'URL nue par le template
- **Portée:** URL nue remplacée par template {{Lien web}}
- **Sécurité:** Conversion automatique en template avec archive params

### Chemins de contournement potentiels
- **Aucun détecté** - Le flux est sécurisé par la vérification de template existant (ligne 1743)

---

## SCÉNARIO 4 : URL nue hors <ref> : https://site.com avec 404

### Flux de modification

```
Wikicode: https://site.com (dans texte libre ou Liens externes)
    ↓
UrlExtractor détecte l'URL (regex URL_PATTERN)
    ↓
_is_url_in_reference_scope() → FALSE (pas dans <ref> ni template)
    ↓
[Branche ligne 448] scoped_matches FILTRÉ → URL EXCLUE du pipeline
    ↓
AUCUNE TRAITEMENT
    ↓
AUCUNE MODIFICATION
```

### Point de modification
- **Qui modifie:** Aucun
- **Qui applique:** Aucun
- **Portée:** Aucune
- **Sécurité:** _is_url_in_reference_scope() EXCLUT les URLs hors périmètre

### Chemins de contournement potentiels
- **Aucun détecté** - La protection du périmètre fonctionne correctement

---

## ANALYSE CRITIQUE DES CHEMINS DE CONTOURNEMENT

### A. Contournement potentiel via "_apply_simple_url_replacement"

**Analyse du code (ligne 1718-1867):**

```python
def _apply_simple_url_replacement(self, content: str, old_url: str, new_url: str, ...):
    # Vérification 1: Détection template existant (ligne 1743)
    template = self._get_cached_reference_template(content, old_url, url_position)
    if template:
        logger.info(f"URL already in reference template {template.template_name}, skipping bare URL conversion")
        return content  # ← PROTECTION: ne modifie pas si template existe
```

**VERDICT:** Si une URL est déjà dans un template, `_apply_simple_url_replacement()` ne la modifie pas.

### B. Contournement potentiel via absence de vérification de type de template

**Analyse:** Dans `_attempt_archive_fallback()` (ligne 1541):

```python
template = self._get_cached_reference_template(content, url, url_position)
is_reference_template = template is not None
template_name = template.template_name if template else None

repair_details = {
    'is_reference_template': is_reference_template,
    'template_name': template_name,
    ...
}
```

Ce flag `is_reference_template` est utilisé ligne 916 pour décider du chemin de réparation. Mais **ce n'est pas utilisé pour bloquer l'entrée dans le pipeline**.

**VERDICT:** Les URLs dans ouvrage entrent dans le pipeline mais sont protégées lors de la construction de la correction (ligne 634-638).

### C. Problème identifié: DOUBLE VÉRIFICATION

Il y a DEUX endroits où le type de template est vérifié:

1. **Dans `_attempt_archive_fallback()` (ligne 1541)** - Définit `is_reference_template` et `template_name`
2. **Dans `_apply_simple_url_replacement()` (ligne 1743)** - Vérifie si template existe et retourne content inchangé

**Problème:** Si une URL dans ouvrage échoupe à la vérification ligne 634 (TEMPLATES_WITHOUT_ARCHIVE_PARAMS), le code pourrait encore tenter un chemin de fallback dans `_apply_simple_url_replacement()`.

**Vérification du code:**

```python
# dead_links.py ligne 1091-1093
else:
    # Simple URL replacement (not a {{Lien web}} template)
    self._apply_simple_url_replacement(content, old_url, new_url, url_position, result, repair_result, archive_repairs)
```

Ce chemin est atteint SEULEMENT si `is_reference_template_repair = False` (ligne 916). Pour une URL dans ouvrage:
- `template` = ReferenceTemplate(template_name='ouvrage')
- `is_reference_template` = True (ligne 1541)
- `is_reference_template_repair` = True (ligne 917)
- Le chemin ligne 1091 N'EST PAS atteint

**VERDICT:** Pas de contournement détecté.

### D. Problème identifié: PARTIAL REPAIR POUR TEMPLATES NON SUPPORTÉS

**Analyse du code (ligne 926-966):**

```python
if not template.is_supported:
    # Attempt partial safe repair: only modify URL and add archive parameters
    if repair_result and repair_result.decision == RepairDecision.REPLACEMENT_CONFIRMED:
        archive_url = repair_result.details.get('archive_url')
        archive_date = repair_result.details.get('archive_date')
        
        if archive_url and archive_date:
            new_template = self.reference_template_helper.generate_archive_repair_template(
                template,
                archive_url,
                archive_date,
                old_url,
                assume_patch_deployed=False,
                provider=provider
            )
```

**Risque:** Si un template est marqué `is_supported=False`, le code tente quand même une réparation partielle en ajoutant des archive params.

**Vérification:** `generate_archive_repair_template()` vérifie TEMPLATES_WITHOUT_ARCHIVE_PARAMS (ligne 634) et retourne le template inchangé pour ouvrage/chapitre.

**VERDICT:** Double protection en place, pas de risque détecté.

---

## TABLEAU DES 4 SCÉNARIOS

| Scénario | Type de référence | Modification possible ? | Qui modifie | Qui applique | Protection principale | Chemin de contournement |
|----------|-----------------|----------------------|-------------|--------------|---------------------|----------------------|
| 1. {{Lien web|url=...}} | Template supporté | OUI | ReferenceTemplateHelper | Corrector | TEMPLATES_WITHOUT_ARCHIVE_PARAMS (Lien web non exclu) | Aucun |
| 2. {{ouvrage|url=...}} | Template supporté | NON | Aucun | Aucun | TEMPLATES_WITHOUT_ARCHIVE_PARAMS (ouvrage exclu) | Aucun |
| 3. <ref>URL nue</ref> | Pas de template | OUI (conversion en {{Lien web}}) | BareUrlHelper | Corrector | Vérification template existant (ligne 1743) | Aucun |
| 4. URL nue hors <ref> | Hors périmètre | NON | Aucun | Aucun | _is_url_in_reference_scope() | Aucun |

---

## INVARIANTS ACTUELLEMENT RESPECTÉS

### Invariant 1: Ne jamais modifier une URL hors périmètre
- **Implémenté:** `_is_url_in_reference_scope()` ligne 1243-1258
- **Vérifié:** ✅ - Scénario 4 confirme l'exclusion

### Invariant 2: Ne jamais ajouter d'archive params à ouvrage/chapitre
- **Implémenté:** `TEMPLATES_WITHOUT_ARCHIVE_PARAMS` ligne 113 de reference_template_helper.py
- **Vérifié:** ✅ - Scénario 2 confirme le blocage (ligne 634-638)

### Invariant 3: Ne jamais ajouter |site= à ouvrage/chapitre
- **Implémenté:** `TEMPLATES_WITHOUT_SITE_PARAM` ligne 96 de reference_template_helper.py
- **Vérifié:** ✅ - Vérifié dans `_get_site_parameter_if_missing()` (ligne 239) et `generate_archive_repair_template()` (ligne 684-686)

### Invariant 4: Ne jamais modifier une URL déjà dans un template
- **Implémenté:** Vérification template existant dans `_apply_simple_url_replacement()` (ligne 1743-1746)
- **Vérifié:** ✅ - Scénario 3 confirme la protection

### Invariant 5: Ne jamais modifier une référence académique
- **Implémenté:** Vérification patterns académiques (ligne 1756-1771)
- **Vérifié:** ✅ - Patterns vérifiés et conversion bloquée

---

## PROBLÈME CRITIQUE IDENTIFIÉ

### PROBLÈME: ENTRÉE TARDIVE DANS LE PIPELINE

**Les URLs dans ouvrage/chapitre sont autorisées à entrer dans le pipeline DeadLink (validation HTTP, recherche archive, etc.) mais sont bloquées SEULEMENT lors de la construction de la correction.**

**Conséquences:**
1. **Consommation de ressources inutile** - Validation HTTP, recherche d'archive pour des URLs qui ne seront pas modifiées
2. **Faux positifs dans les logs** - Logs indiquent "lien mort détecté" pour des URLs qui ne seront pas corrigées
3. **Complexité du code** - Pipeline plus complexe que nécessaire

**Solution idéale:** Pré-filtrer par type de template AVANT validation HTTP:
```python
# Idéalement:
if template_name in {'ouvrage', 'chapitre'}:
    continue  # Sauter toute validation HTTP
```

**État actuel:** Fonctionnel mais sous-optimal.

---

## CONCLUSION DE L'AUDIT 4

### Ce qui fonctionne correctement

1. **Protection du périmètre** - `_is_url_in_reference_scope()` exclut correctement les URLs hors <ref>/template
2. **Protection des types de templates** - `TEMPLATES_WITHOUT_*` bloquent correctement les modifications d'ouvrage/chapitre
3. **Protection des templates existants** - `_apply_simple_url_replacement()` ne modifie pas les URLs déjà dans un template
4. **Protection des références académiques** - Patterns académiques bloquent la conversion en {{Lien web}}
5. **Double protection** - Vérifications à la fois dans dead_links.py et reference_template_helper.py

### Ce qui est sous-optimal

1. **Entrée tardive dans le pipeline** - Les URLs dans ouvrage sont validées HTTP et cherchées en archive avant d'être exclues
2. **Double vérification** - Le type de template est vérifié à plusieurs endroits sans coordination centralisée
3. **Complexité inutile** - Le pipeline traite des cas qui ne seront pas modifiés

### Ce qui N'EST PAS un problème

1. **Aucun chemin de contournement détecté** - Les protections fonctionnent correctement
2. **Aucun risque de modification non autorisée d'ouvrage** - Les protections TEMPLATES_WITHOUT_* sont efficaces
3. **Aucun risque de modification hors périmètre** - _is_url_in_reference_scope() fonctionne correctement

### Recommandation

**NE PAS MODIFIER LE CODE POUR L'INSTANT.**

Les protections fondamentales sont en place et fonctionnent correctement. Le problème est uniquement d'optimisation (entrée tardive dans le pipeline), pas de sécurité.

**Si optimisation souhaitée:**
1. Ajouter un pré-filtrage par type de template AVANT validation HTTP
2. Centraliser la logique de vérification du type de template
3. Réduire la complexité du pipeline DeadLink

---

# SYNTHÈSE FINALE DES 4 AUDITS

## Audit 1 - Architecture DeadLink ✅
**Conclusion:** DeadLinkAnalyzer est un monolithe qui fait tout (détection, validation, correction, tracking). Besoin de scinder en modules spécialisés.

## Audit 2 - Tracking/Enregistrement ✅
**Conclusion:** 7+ systèmes de tracking parallèles, aucune source unique de vérité, information dispersée entre Issue.extra, Correction, JSON, SQLite et logs. Besoin de système centralisé.

## Audit 3 - Classification des références ✅
**Conclusion:** Protections existent (`TEMPLATES_WITHOUT_*`) mais sont appliquées tardivement. Les URLs dans ouvrage entrent dans le pipeline avant d'être exclues. Fonctionnel mais sous-optimal.

## Audit 4 - Chaîne de modification ✅
**Conclusion:** Les 4 scénarios sont correctement protégés. Aucun chemin de contournement détecté. Les invariants de sécurité sont respectés. Le problème est uniquement d'optimisation (entrée tardive), pas de sécurité.

---

# RECOMMANDATION FINALE

**STATUT ACTUEL: SÛR ET FONCTIONNEL, MAIS SOUS-OPTIMAL.**

Le système DeadLink:
- ✅ Protège correctement les ouvrages/chapitre de la modification
- ✅ Exclut les URLs hors périmètre
- ✅ Respecte les invariants de sécurité
- ⚠️ Consomme des ressources inutilement (validation HTTP pour ouvrage)
- ⚠️ Tracking dispersé entre 7+ systèmes
- ⚠️ Architecture monolithique (dead_links.py fait tout)

**PLAN RECOMMANDÉ:**
1. **Créer système de tracking centralisé** (P0)
2. **Corréler Issue et Correction** (P0)
3. **Ajouter tracking granulaire par URL** (P0)
4. **Pré-filtrer par type de template** (P1 - optimisation)
5. **Scinder dead_links.py** (P2 - refactoring)

**NE PAS REFACTORISER SANS APPROBATION PRÉALABLE.**

////

# PLAN D'ARCHITECTURE ET DE REFACTORING DEADLINK / TRACKING

---

# 1. RÉSUMÉ EXÉCUTIF

Le système DeadLink actuel est **fonctionnel mais fragmenté** :

- ✅ **Sécurité :** Les protections fondamentales (TEMPLATES_WITHOUT_*, _is_url_in_reference_scope) fonctionnent correctement. Aucun risque immédiat de modification non autorisée.
- ⚠️ **Architecture :** `dead_links.py` est un monolithe de 2000+ lignes qui mélange détection, validation, archive, construction de template, tracking et cache.
- ⚠️ **Tracking :** 7+ systèmes parallèles (AnalyzedTracker, PublishedTracker, AutomationStateManager, SQLite, JSON, logs, EventManager) sans source unique de vérité.
- ⚠️ **Corrélation :** Issue et Correction ne sont pas corrélées, impossible de tracer "quelle détection → quelle correction".
- ⚠️ **Granularité :** Tracking au niveau article, pas au niveau URL. Impossible de répondre "quelle URL modifiée quand ?".

**Conclusion actuelle :** Le système est stable mais difficile à maintenir et à auditer. Les invariants de sécurité sont respectés, mais l'architecture ne permet pas une traçabilité complète.

**Objectif du refactoring :** Séparer clairement les responsabilités (DeadLink décide, Corrector applique, Tracking enregistre), établir une source unique de vérité (SQLite), et permettre une traçabilité granulaire par URL.

---

# 2. ARCHITECTURE ACTUELLE

## Flux de données actuel

```
Orchestrator.analyze(content)
    ↓
DeadLinkAnalyzer.analyze(content)
    ↓
[1] Extraction URLs (regex)
    ↓
[2] Filtrage périmètre (_is_url_in_reference_scope)
    ↓
[3] Validation HTTP (LinkChecker)
    ↓
[4] Redirects (RedirectFinder)
    ↓
[5] Content verification (ContentVerifier)
    ↓
[6] Archive fallback (ArchiveProvider)
    ↓
[7] Repair decision (LinkValidator)
    ↓
[8] Construction correction (generate_archive_repair_template / _apply_simple_url_replacement)
    ↓
[9] Création Issue (self.issues.append)
    ↓
[10] Orchestrator.combine_issues()
    ↓
[11] Corrector.apply_corrections(issues)
    ↓
[12] Création Correction (self.corrections.append)
    ↓
[13] Application wikitext
    ↓
[14] Publication (Publisher.publish)
    ↓
[PARALLÈLE A] AnalyzedTracker.record_analysis() → JSON
[PARALLÈLE B] PublishedTracker.mark_as_published() → JSON
[PARALLÈLE C] DatabaseManager.update_*() → SQLite
[PARALLÈLE D] AutomationStateManager.update_*() → JSON
[PARALLÈLE E] SQLiteAutomationStateManager.update_*() → SQLite
[PARALLÈLE F] LiaLogger.log_*() → Fichiers log
[PARALLÈLE G] EventManager.emit() → Queue mémoire
```

## Sources de données actuelles

| Source | Type | Données | Producteur | Consommateur | Nécessaire ? | Cible |
|--------|------|---------|------------|--------------|--------------|-------|
| **AnalyzedTracker** | JSON | AnalysisRecord (article, revision, status, changes, content) | DeadLinkAnalyzer, Orchestrator | Orchestrator, Backend API | ❌ Dupliqué | SQLite |
| **PublishedTracker** | JSON | Article publié (article, revision, summary, timestamp) | Publisher, publication.py | Backend API | ❌ Dupliqué | SQLite |
| **AutomationStateManager** | JSON | Session d'automatisation (session_id, article_states, interruptions) | Automation scripts | Automation scripts | ❌ Partiellement remplacé | SQLiteAutomationStateManager |
| **SQLiteAutomationStateManager** | SQLite | Session d'automatisation (même structure) | Automation scripts | Automation scripts | ✅ Conserver | SQLite |
| **PendingPublishQueue** | JSON | File d'attente publication (article, corrected_content, summary) | Orchestrator | Scheduler | ❌ Doublon avec scheduler_queue | SQLite |
| **Database.articles** | SQLite | Articles analysés (title, page_id, status) | DatabaseManager | UI, API | ✅ Conserver | SQLite |
| **Database.analysis_results** | SQLite | Résultats analyse (article, status, content, changes) | Backend API | UI, API | ✅ Conserver | SQLite |
| **Database.scheduler_queue** | SQLite | File d'attente scheduler (article, corrected_content, status) | Scheduler | Scheduler | ✅ Conserver | SQLite |
| **Database.manual_review_decisions** | SQLite | Décisions révision manuelle (article, url, status) | UI, API | UI, API | ✅ Conserver | SQLite |
| **Issue** | Mémoire | Détection (issue_type, position, original_text, suggested_text, extra) | DeadLinkAnalyzer | Corrector | ✅ Conserver (objet volatil) | - |
| **Correction** | Mémoire | Application (issue, applied, original_snippet, corrected_snippet) | Corrector | Publisher | ✅ Conserver (objet volatil) | - |
| **Issue.extra** | Mémoire | Méta-détails (url, archive_url, repair_status, template, etc.) | DeadLinkAnalyzer | Tracking | ❌ Fourre-tout non structuré | Table dédiée |
| **LiaLogger** | Fichier | Opérations LIA (lia_operations.log, published_articles.log) | Multiple | Aucun | ❌ Logging non structuré | SQLite |
| **EventManager** | Mémoire | Événements temps réel (SSE) | Multiple | UI React | ✅ Conserver (observabilité) | Mémoire |

---

# 3. ARCHITECTURE CIBLE

## Schéma cible

```
                    ORCHESTRATOR
                         │
                         ▼
                DEADLINK ANALYZER
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     CONTEXT         VALIDATION     CLASSIFICATION
     ANALYZER        HTTP/LINK      REFERENCE TYPE
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                 ARCHIVE RESOLVER
                         │
                         ▼
                  REPAIR DECISION
                         │
                         ▼
                CORRECTION BUILDER
                         │
                         ▼
                     CORRECTOR
                         │
                         ▼
                  CONTENT VERIFY
                         │
                         ▼
                  TRACKING SERVICE
                         │
                         ▼
                    REPOSITORY
                         │
                         ▼
                      SQLITE
```

## Modules existants à réutiliser

| Module existant | Responsabilité actuelle | Responsabilité cible | Action |
|----------------|----------------------|---------------------|--------|
| **LinkChecker** | Validation HTTP | Validation HTTP | ✅ Réutiliser tel quel |
| **LinkValidator** | Décision de réparation | Décision de réparation | ✅ Réutiliser tel quel |
| **RedirectFinder** | Recherche redirects | Recherche redirects | ✅ Réutiliser tel quel |
| **ContentVerifier** | Vérification contenu | Vérification contenu | ✅ Réutiliser tel quel |
| **ArchiveProvider** | Recherche archive | Recherche archive | ✅ Réutiliser tel quel |
| **ReferenceTemplateHelper** | Parsing templates, génération correction | Parsing templates, génération correction | ✅ Réutiliser tel quel |
| **BareUrlHelper** | Détection/conversion URLs nues | Détection/conversion URLs nues | ✅ Réutiliser tel quel |
| **Corrector (publisher.py)** | Application correction | Application correction | ✅ Réutiliser, supprimer duplicate |
| **Corrector (corrector.py)** | Application correction (duplicate) | À supprimer | ❌ Supprimer |
| **DatabaseManager** | SQLite operations | Source unique de vérité | ✅ Étendre avec table DeadLink |
| **SQLiteAutomationStateManager** | État automation | État automation | ✅ Réutiliser tel quel |
| **EventManager** | Observabilité temps réel | Observabilité temps réel | ✅ Réutiliser tel quel |

---

# 4. RESPONSABILITÉS PAR MODULE

## dead_links.py (actuel)

| Responsabilité | Fonction actuelle | Doit rester ? | Doit être délégué ? | Module cible |
|----------------|-------------------|---------------|-------------------|--------------|
| Extraction URLs | `_extract_urls_from_content()` | ✅ Oui | ❌ Non | DeadLink |
| Filtrage périmètre | `_is_url_in_reference_scope()` | ✅ Oui | ❌ Non | DeadLink |
| Détection template | `_get_cached_reference_template()` | ✅ Oui | ❌ Non | DeadLink |
| Validation HTTP | Appel LinkChecker | ✅ Oui | ❌ Non | DeadLink |
| Recherche redirects | Appel RedirectFinder | ✅ Oui | ❌ Non | DeadLink |
| Vérification contenu | Appel ContentVerifier | ✅ Oui | ❌ Non | DeadLink |
| Recherche archive | `_attempt_archive_fallback()` | ✅ Oui | ❌ Non | DeadLink |
| Décision réparation | Appel LinkValidator | ✅ Oui | ❌ Non | DeadLink |
| Construction correction template | `generate_archive_repair_template()` | ❌ Non | ✅ Oui | ReferenceTemplateHelper |
| Construction correction URL nue | `_apply_simple_url_replacement()` | ❌ Non | ✅ Oui | BareUrlHelper |
| Construction correction minimal | `_build_lien_web_template()` | ❌ Non | ✅ Oui | BareUrlHelper |
| Validation correction | `_validate_template_replacement()` | ✅ Oui | ❌ Non | DeadLink |
| Création Issue | `self.issues.append()` | ✅ Oui | ❌ Non | DeadLink |
| Cache vérification | `_check_cache` | ❌ Non | ✅ Oui | Database (table cache) |
| Cache réparation | `_repair_cache` | ❌ Non | ✅ Oui | Database (table cache) |
| Cache template | `_template_cache` | ❌ Non | ✅ Oui | Database (table cache) |
| Tracking (dans Issue.extra) | Issue dict | ❌ Non | ✅ Oui | TrackingService |

## publisher.py / Corrector

| Responsabilité | Fonction actuelle | Doit rester ? | Doit être délégué ? | Module cible |
|----------------|-------------------|---------------|-------------------|--------------|
| Application correction | `apply_corrections()` | ✅ Oui | ❌ Non | Corrector |
| Vérification position | `strict_position_check` | ✅ Oui | ❌ Non | Corrector |
| Validation diff | `validate_replacement()` | ✅ Oui | ❌ Non | Corrector |
| Publication API | `publish()` | ✅ Oui | ❌ Non | Publisher |
| Tracking publication | `mark_as_published()` | ❌ Non | ✅ Oui | TrackingService |

---

# 5. DEADLINK → CORRECTOR → TRACKING

## Contrat actuel

```
DeadLinkAnalyzer
    ↓
Issue(issue_type, position, original_text, suggested_text, extra={...})
    ↓
Corrector
    ↓
Correction(issue, applied, original_snippet, corrected_snippet)
    ↓
Publisher
    ↓
[PARALLÈLE] Trackers multiples
```

## Problème : Pas de corrélation explicite

- Issue et Correction ne partagent pas d'ID
- Issue.extra contient des données de tracking non structurées
- Impossible de tracer "quelle Issue → quelle Correction → quelle publication"

## Contrat cible

```
DeadLinkAnalyzer
    ↓
DeadLinkOperation {
    operation_id: UUID,
    article_title: str,
    revision_id: int,
    url_original: str,
    url_target: str,
    context: ContextInfo,
    reference_type: ReferenceType,
    template_name: str,
    field_name: str,
    http_status: int,
    link_status: LinkStatus,
    redirect_info: dict,
    archive_url: str,
    archive_date: str,
    archive_provider: str,
    archive_evidence: dict,
    repair_decision: RepairDecision,
    repair_type: RepairType,
    old_text: str,
    new_text: str,
    validation_result: ValidationResult,
    repair_status: RepairStatus,
    publication_status: PublicationStatus,
    error: str,
    timestamp: datetime
}
    ↓
TrackingService.record_operation(operation)
    ↓
Issue(issue_id=operation_id, position, original_text, suggested_text)
    ↓
Corrector
    ↓
Correction(issue_id=operation_id, applied, ...)
    ↓
TrackingService.update_correction(operation_id, correction_result)
    ↓
Publisher
    ↓
TrackingService.update_publication(operation_id, publication_result)
```

---

# 6. CLASSIFICATION DES RÉFÉRENCES

## Pipeline actuel (problématique)

```
URL détectée
    ↓
Validation HTTP
    ↓
Recherche archive
    ↓
Construction correction
    ↓
Vérification type template (TEMPLATES_WITHOUT_*)
```

## Pipeline cible (sécurisé)

```
URL détectée
    ↓
Analyse contexte (_is_url_in_reference_scope)
    ↓
Identification template (find_reference_template)
    ↓
Type de référence (Lien web / ouvrage / chapitre / article / ...)
    ↓
Éligibilité DeadLink ?
    ↓
SI NON ÉLIGIBLE (ouvrage, chapitre) → SKIP (pas de validation HTTP)
    ↓
SI ÉLIGIBLE (Lien web, article, URL nue dans <ref>)
    ↓
Validation HTTP
    ↓
Recherche archive
    ↓
Vérification
    ↓
Décision réparation
    ↓
Construction correction
```

## Types de référence à distinguer

| Type | Éligible DeadLink ? | Protection actuelle | Protection cible |
|------|-------------------|-------------------|-----------------|
| **Lien web** | ✅ Oui | - | - |
| **Ouvrage** | ❌ Non | TEMPLATES_WITHOUT_ARCHIVE_PARAMS | Pré-filtrage avant HTTP |
| **Chapitre** | ❌ Non | TEMPLATES_WITHOUT_ARCHIVE_PARAMS | Pré-filtrage avant HTTP |
| **Article scientifique** | ⚠️ À définir | is_supported | is_supported |
| **Article de presse** | ⚠️ À définir | is_supported | is_supported |
| **URL nue dans <ref>** | ✅ Oui (conversion) | Vérification patterns académiques | Vérification patterns académiques |
| **URL nue hors <ref>** | ❌ Non | _is_url_in_reference_scope | _is_url_in_reference_scope |
| **URL d'archive** | ⚠️ Déjà traitée | Skip si archive validée | Skip si archive validée |

## Protection ouvrage/chapitre en amont

```python
# Dans DeadLinkAnalyzer, après identification du template
template = self._get_cached_reference_template(content, url, url_position)
if template:
    normalized_name = template.template_name.lower().replace('_', ' ')
    if normalized_name in {'ouvrage', 'chapitre'}:
        logger.info(f"REFERENCE_TYPE_EXCLUDED | url={url} | type={template.template_name}")
        continue  # Skip toute validation HTTP et recherche archive
```

---

# 7. PROBLÈMES CRITIQUES

| ID | Problème | Localisation | Gravité | Impact |
|----|----------|--------------|---------|--------|
| C1 | 7+ systèmes de tracking parallèles sans source unique | Multiple fichiers | P1 | Impossible de tracer les corrections |
| C2 | Issue et Correction non corrélées | dead_links.py + corrector.py | P1 | Impossible d'auditer les modifications |
| C3 | Tracking granulaire manquant (pas par URL) | Tous systèmes | P1 | Impossible de répondre "quelle URL modifiée quand ?" |
| C4 | Issue.extra comme fourre-tout non structuré | dead_links.py | P1 | Impossible de requêter les données |
| C5 | DeadLink mélange détection, validation, construction, tracking | dead_links.py | P2 | Difficile à maintenir |
| C6 | Duplicate Corrector (corrector.py vs publisher.py) | Deux fichiers | P2 | Confusion, logique dupliquée |
| C7 | Entrée tardive dans pipeline (ouvrage validé HTTP avant exclusion) | dead_links.py | P3 | Consommation ressources inutile |
| C8 | Caches locaux non persistants | dead_links.py | P3 | Perte d'état sur crash |
| C9 | Tracking dispersé entre JSON, SQLite, logs, mémoire | Multiple | P1 | Pas de source unique de vérité |
| C10 | Pas de table dédiée aux DeadLink operations | database.py | P1 | Historique incomplet |

---

# 8. DUPLICATIONS

| Duplication | Implémentation A | Implémentation B | Différence | Risque | Source à conserver | Source à supprimer |
|-------------|------------------|-------------------|------------|--------|-------------------|-------------------|
| **Corrector** | `utils/corrector.py::Corrector` | `utils/publisher.py::Corrector` | - A : Ollama supervisor, fields différents<br>- B : Publication API, stricte position check | Confusion sur lequel utiliser | **publisher.py::Corrector** | corrector.py |
| **Tracking session automation** | `automation_state.py` (JSON) | `automation_state_sqlite.py` (SQLite) | - JSON : non transactionnel<br>- SQLite : transactionnel, robuste | Incohérence possible | **SQLite** | JSON (migration) |
| **Tracking article analysé** | `analyzed_tracker.py` (JSON) | `database.analysis_results` (SQLite) | - JSON : complet (contenu)<br>- SQLite : même structure + plus | Incohérence possible | **SQLite** | JSON (migration) |
| **Tracking article publié** | `published_tracker.py` (JSON) | `database.actions` + `scheduler_queue` (SQLite) | - JSON : simple<br>- SQLite : complet avec job tracking | Incohérence possible | **SQLite** | JSON (migration) |
| **File d'attente publication** | `pending_publish_queue.py` (JSON) | `database.scheduler_queue` (SQLite) | - JSON : simple FIFO<br>- SQLite : state machine complète | Incohérence possible | **SQLite** | JSON (migration) |
| **Génération template archive** | `reference_template_helper::generate_archive_repair_template` | `dead_links.py::_build_lien_web_template` | - Helper : générique, supporte tous templates<br>- DeadLink : spécialisé Lien web | Incohérence possible | **Helper** | dead_links (déléguer) |
| **Construction template URL nue** | `bare_url_helper::build_repaired_reference_template` | `dead_links.py::_apply_simple_url_replacement` | - Helper : validé, réutilisable<br>- DeadLink : inline, fallback minimal | Incohérence possible | **Helper** | dead_links (déléguer) |
| **Cache template** | `dead_links._template_cache` (mémoire) | Aucun équivalent persistant | - Mémoire : perdu sur crash<br>- Pas de persistant | Perte d'état | **Nouveau cache SQLite** | Mémoire |

---

# 9. SOURCE DE VÉRITÉ

## Source unique proposée : SQLite (DatabaseManager)

### Nouvelle table principale : `deadlink_operations`

```sql
CREATE TABLE deadlink_operations (
    id TEXT PRIMARY KEY,  -- UUID
    article_title TEXT NOT NULL,
    revision_id INTEGER,
    operation_id TEXT NOT NULL,  -- UUID de l'opération
    
    -- URL et contexte
    url_original TEXT NOT NULL,
    url_target TEXT,
    context_type TEXT,  -- 'ref', 'template', 'bare_url'
    reference_type TEXT,  -- 'lien_web', 'ouvrage', 'chapitre', 'article', etc.
    template_name TEXT,
    field_name TEXT,  -- 'url', 'archive-url', etc.
    
    -- Validation HTTP
    http_status_code INTEGER,
    link_status TEXT,  -- HEALTHY, DEAD, TEMPORARY_ERROR, etc.
    error_type TEXT,
    
    -- Redirect
    redirect_url TEXT,
    redirect_count INTEGER,
    
    -- Archive
    archive_url TEXT,
    archive_date TEXT,
    archive_provider TEXT,
    archive_evidence TEXT,  -- JSON
    
    -- Décision de réparation
    repair_decision TEXT,  -- NO_ACTION, REPLACEMENT_CONFIRMED, etc.
    repair_type TEXT,  -- 'template', 'url', 'archive_only', etc.
    repair_reason TEXT,
    
    -- Correction
    old_text TEXT,
    new_text TEXT,
    old_position INTEGER,
    new_position INTEGER,
    
    -- Validation
    validation_result TEXT,  -- 'valid', 'invalid', 'warning'
    validation_details TEXT,  -- JSON
    
    -- Statuts
    repair_status TEXT,  -- 'detected', 'validated', 'confirmed', 'applied', 'published', 'failed'
    publication_status TEXT,  -- 'pending', 'published', 'rejected'
    
    -- Erreurs
    error_message TEXT,
    error_stack TEXT,
    
    -- Métadonnées
    retry_count INTEGER DEFAULT 0,
    idempotency_key TEXT UNIQUE,  -- (article_title, revision_id, url_original, context_hash)
    
    -- Timestamps
    detected_at TIMESTAMP,
    validated_at TIMESTAMP,
    repaired_at TIMESTAMP,
    applied_at TIMESTAMP,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Corrélation
    issue_id TEXT,  -- Référence à Issue (si applicable)
    correction_id TEXT,  -- Référence à Correction (si applicable)
    publication_job_id TEXT,  -- Référence à job publication
    
    FOREIGN KEY (article_title) REFERENCES articles(title),
    FOREIGN KEY (revision_id) REFERENCES articles(last_revision_id)
);

CREATE INDEX idx_deadlink_operations_article ON deadlink_operations(article_title);
CREATE INDEX idx_deadlink_operations_url ON deadlink_operations(url_original);
CREATE INDEX idx_deadlink_operations_status ON deadlink_operations(repair_status);
CREATE INDEX idx_deadlink_operations_idempotency ON deadlink_operations(idempotency_key);
CREATE INDEX idx_deadlink_operations_timestamp ON deadlink_operations(detected_at);
```

## Migration des systèmes existants

| Système | Action | Pourquoi | Cible |
|---------|--------|----------|-------|
| **AnalyzedTracker (JSON)** | Migrer → déprécier | Duplique analysis_results | `database.analysis_results` |
| **PublishedTracker (JSON)** | Migrer → déprécier | Duplique actions + scheduler_queue | `database.actions` + `scheduler_queue` |
| **AutomationStateManager (JSON)** | Migrer → déprécier | Remplacé par SQLite | `SQLiteAutomationStateManager` |
| **PendingPublishQueue (JSON)** | Migrer → déprécier | Duplique scheduler_queue | `database.scheduler_queue` |
| **LiaLogger (fichiers)** | Transformer en historique | Logging non structuré | `database.operation_logs` (nouvelle table) |
| **Issue.extra** | Migrer → structurer | Fourre-tout non structuré | `deadlink_operations` |
| **Caches mémoire** | Persister → déprécier | Perte d'état sur crash | `database.caches` (nouvelle table) |
| **EventManager** | Conserver | Observabilité temps réel | Mémoire (inchangé) |

---

# 10. MACHINE À ÉTATS

## États actuels (dispersés)

| Système | États |
|---------|-------|
| **AnalysisStatus** | ANALYZING, PENDING, PUBLISHED, REJECTED, IGNORED, ERROR |
| **ArticleProcessingStatus** | PENDING, RETRIEVING, ANALYZING, CORRECTING, QUEUED, PUBLISHED, REJECTED, ERROR |
| **SessionStatus** | NOT_STARTED, RUNNING, PAUSED, COMPLETED, FAILED, INTERRUPTED |
| **RepairDecision** | NO_ACTION, DEAD_NO_REPLACEMENT, REPLACEMENT_CONFIRMED, REPAIR_REJECTED, REPAIR_DIFF_REJECTED |
| **LinkStatus** | HEALTHY, DEAD, TEMPORARY_ERROR, RATE_LIMITED, REVIEW_REQUIRED, UNKNOWN |

## Machine à états unifiée (DeadLink operation)

```
DETECTED
    ↓ (validation HTTP réussie)
VALIDATED
    ↓ (archive trouvée et validée)
REPAIR_CANDIDATE
    ↓ (LinkValidator = REPLACEMENT_CONFIRMED)
REPAIR_CONFIRMED
    ↓ (correction construite et validée)
CORRECTION_READY
    ↓ (Corrector applique)
APPLIED
    ↓ (diff validé)
VERIFIED
    ↓ (publication réussie)
PUBLISHED
```

### États d'échec

```
DETECTED
    ↓ (validation HTTP échoue)
HTTP_FAILED → SKIP

DETECTED
    ↓ (URL hors périmètre)
OUT_OF_SCOPE → SKIP

DETECTED
    ↓ (type de référence exclu)
REFERENCE_TYPE_EXCLUDED → SKIP

REPAIR_CANDIDATE
    ↓ (archive non trouvée)
NO_ARCHIVE → REVIEW_REQUIRED

REPAIR_CANDIDATE
    ↓ (archive non valide)
ARCHIVE_INVALID → REVIEW_REQUIRED

REPAIR_CONFIRMED
    ↓ (construction correction échoue)
CORRECTION_FAILED → REVIEW_REQUIRED

CORRECTION_READY
    ↓ (application échoue)
APPLICATION_FAILED → REVIEW_REQUIRED

APPLIED
    ↓ (diff invalide)
VALIDATION_FAILED → ROLLBACK

VERIFIED
    ↓ (publication échoue)
PUBLICATION_FAILED → RETRY
```

### Définitions

| État | Définition | Producteur | Consommateur | Transitions autorisées |
|------|------------|------------|--------------|----------------------|
| **DETECTED** | URL détectée et identifiée comme candidate | DeadLinkAnalyzer | Validation HTTP | → VALIDATED, → OUT_OF_SCOPE, → REFERENCE_TYPE_EXCLUDED |
| **VALIDATED** | Validation HTTP terminée | LinkChecker | Archive resolver | → REPAIR_CANDIDATE, → HTTP_FAILED |
| **REPAIR_CANDIDATE** | Archive candidate trouvée | ArchiveProvider | LinkValidator | → REPAIR_CONFIRMED, → NO_ARCHIVE, → ARCHIVE_INVALID |
| **REPAIR_CONFIRMED** | Décision de réparation positive | LinkValidator | Correction builder | → CORRECTION_READY, → CORRECTION_FAILED |
| **CORRECTION_READY** | Correction construite et validée | Correction builder | Corrector | → APPLIED, → APPLICATION_FAILED |
| **APPLIED** | Correction appliquée au wikitext | Corrector | Diff validator | → VERIFIED, → VALIDATION_FAILED |
| **VERIFIED** | Diff validé | Diff validator | Publisher | → PUBLISHED, → PUBLICATION_FAILED |
| **PUBLISHED** | Publication réussie | Publisher | TrackingService | (final) |
| **OUT_OF_SCOPE** | URL hors périmètre autorisé | DeadLinkAnalyzer | TrackingService | (final) |
| **REFERENCE_TYPE_EXCLUDED** | Type de référence exclu (ouvrage, chapitre) | DeadLinkAnalyzer | TrackingService | (final) |
| **HTTP_FAILED** | Validation HTTP échouée | LinkChecker | TrackingService | (final) |
| **NO_ARCHIVE** | Archive non trouvée | ArchiveProvider | TrackingService | (final) |
| **ARCHIVE_INVALID** | Archive non valide | ArchiveProvider | TrackingService | (final) |
| **CORRECTION_FAILED** | Construction correction échouée | Correction builder | TrackingService | (final) |
| **APPLICATION_FAILED** | Application correction échouée | Corrector | TrackingService | (final) |
| **VALIDATION_FAILED** | Diff invalide | Diff validator | TrackingService | (final) |
| **PUBLICATION_FAILED** | Publication échouée | Publisher | TrackingService | → RETRY |
| **REVIEW_REQUIRED** | Révision manuelle requise | Multiple | TrackingService | (final) |

---

# 11. IDEMPOTENCE

## Clé d'idempotence proposée

```python
idempotency_key = f"{article_title}:{revision_id}:{url_original}:{context_type}:{reference_type}"
```

### Pourquoi ces composants ?

- **article_title** : Distingue les articles
- **revision_id** : Distingue les révisions (même article, même URL, révision différente = nouvelle opération)
- **url_original** : Distingue les URLs
- **context_type** : Distingue même URL dans différents contextes (ref vs template vs bare_url)
- **reference_type** : Distingue même URL dans différents types de templates (Lien web vs ouvrage)

### Mécanisme

```python
# Avant de créer une nouvelle opération
existing = db.get_deadlink_operation_by_idempotency_key(idempotency_key)
if existing:
    if existing.repair_status == 'PUBLISHED':
        logger.info(f"Operation already published, skipping: {idempotency_key}")
        return existing
    elif existing.repair_status in ['FAILED', 'REVIEW_REQUIRED']:
        logger.info(f"Operation previously failed, retrying: {idempotency_key}")
        # Réutiliser l'opération existante (mise à jour)
        return existing
    else:
        logger.warning(f"Operation in progress state: {existing.repair_status}")
        return existing
```

### Retries

Les retries DOIVENT réutiliser la même opération (même idempotency_key) et incrémenter `retry_count`, pas créer une nouvelle opération.

---

# 12. GESTION DES CRASHES

| Étape du pipeline | État mémoire | État Tracking | État Wikipédia | Risque | Reprise possible ? |
|------------------|-------------|--------------|----------------|--------|-------------------|
| **Avant validation HTTP** | URL dans filtered_matches | Aucun | Inchangé | Aucun | ✅ Oui (retraitement depuis début) |
| **Après validation HTTP** | _check_cache peuplé | Aucun | Inchangé | Cache perdu sur crash | ⚠️ Partiel (revalidation HTTP) |
| **Après recherche archive** | _repair_cache peuplé | Aucun | Inchangé | Cache perdu sur crash | ⚠️ Partiel (recherche archive) |
| **Après création Issue** | Issue dans self.issues | Aucun | Inchangé | Issue perdu sur crash | ❌ Non (perdu) |
| **Après création Correction** | Correction dans self.corrections | Aucun | Inchangé | Correction perdu sur crash | ❌ Non (perdu) |
| **Après application wikitext** | corrected_content en mémoire | Aucun | MODIFIÉ | Wikipédia modifié, tracking perdu | ❌ **CRITIQUE** |
| **Après validation diff** | validation_result en mémoire | Aucun | MODIFIÉ | Wikipédia modifié, tracking perdu | ❌ **CRITIQUE** |
| **Après publication** | revision_id reçu | Parallèle (trackers) | MODIFIÉ | Tracking peut être incomplet | ⚠️ Partiel (tracking à reconstruire) |

### Problème critique

**L'état le plus à risque est après application wikitext mais avant publication tracking.** Si le bot crash à ce moment :
- Wikipédia est modifiée
- Tracking est incomplet (seulement dans mémoire, pas persisté)
- Impossible de savoir si la modification a été validée/published

### Solution

**Enregistrer l'opération dans SQLite IMMÉDIATEMENT après chaque transition d'état :**

```python
# 1. Après détection
operation = DeadLinkOperation(status='DETECTED', ...)
tracking_service.record_operation(operation)

# 2. Après validation HTTP
tracking_service.update_operation(operation.id, status='VALIDATED', http_status=...)

# 3. Après archive trouvée
tracking_service.update_operation(operation.id, status='REPAIR_CANDIDATE', archive_url=...)

# 4. Après décision
tracking_service.update_operation(operation.id, status='REPAIR_CONFIRMED', repair_decision=...)

# 5. Après construction correction
tracking_service.update_operation(operation.id, status='CORRECTION_READY', new_text=...)

# 6. IMMÉDIATEMENT AVANT application wikitext
tracking_service.update_operation(operation.id, status='APPLYING', ...)

# 7. IMMÉDIATEMENT APRÈS application wikitext
tracking_service.update_operation(operation.id, status='APPLIED', ...)

# 8. Après publication
tracking_service.update_operation(operation.id, status='PUBLISHED', revision_id=...)
```

### Reprise après crash

```python
# Au démarrage, trouver les opérations en état intermédiaire
stale_operations = db.get_deadlink_operations_by_status('APPLYING')
for op in stale_operations:
    # Vérifier si Wikipédia a été modifiée
    current_revision = wikipedia.get_revision(op.article_title)
    if current_revision.revision_id != op.revision_id:
        # Wikipédia a été modifiée par autre chose ou déjà publié
        op.status = 'UNKNOWN_STATE'
        db.update_deadlink_operation(op)
    else:
        # Wikipédia non modifiée, peut reprendre
        op.status = 'APPLIED'  # Ou rollback si nécessaire
        db.update_deadlink_operation(op)
```

---

# 13. PLAN DE MIGRATION

## Phase 0 — Tests et état de référence

**Objectif :** Créer des tests qui figent le comportement actuel.

**Actions :**
1. Créer `tests/test_deadlink_audit.py` avec les 12+ tests de non-régression (section 14)
2. Exécuter les tests sur l'état actuel → baseline
3. Créer des tests d'intégration pour chaque scénario d'Audit 4
4. Documenter le comportement actuel (logs, tracking, Issue.extra)

**Critère de succès :** Tous les tests passent sur l'état actuel.

---

## Phase 1 — Contrat Tracking (P1)

**Objectif :** Créer le nouveau modèle logique sans supprimer l'ancien.

**Actions :**
1. Créer `utils/tracking_service.py` avec la classe `TrackingService`
2. Créer la table `deadlink_operations` dans DatabaseManager
3. Créer le modèle `DeadLinkOperation` (dataclass)
4. Implémenter `record_operation()`, `update_operation()`, `get_operation()`
5. Ajouter l'ID d'opération dans Issue (`issue_id: str`)
6. **NE PAS** supprimer les anciens trackers
7. **PARALLÈLE** : écrire dans TrackingService ET les anciens trackers

**Critère de succès :** TrackingService enregistre les opérations, anciens trackers fonctionnent toujours.

---

## Phase 2 — Corrélation Issue/Correction (P1)

**Objectif :** Ajouter les identifiants nécessaires pour corréler Issue et Correction.

**Actions :**
1. Ajouter `operation_id: str` à Issue (via Issue.extra ou nouveau champ)
2. Ajouter `operation_id: str` à Correction
3. Modifier DeadLinkAnalyzer pour générer un UUID avant de créer l'Issue
4. Passer l'operation_id à Corrector
5. Enregistrer l'opération dans TrackingService avec l'operation_id
6. Corréler Correction avec l'opération via operation_id

**Critère de succès :** Une Issue et sa Correction partagent le même operation_id.

---

## Phase 3 — Classification en amont (P3)

**Objectif :** Déplacer la décision d'éligibilité avant HTTP/archive.

**Actions :**
1. Dans DeadLinkAnalyzer, après `_is_url_in_reference_scope()`, identifier le template
2. Si template trouvé, vérifier le type
3. Si type in {'ouvrage', 'chapitre'}, loguer et skip (pas de validation HTTP)
4. Ajouter des tests spécifiques pour ce scénario
5. Vérifier que les autres types ne sont pas affectés

**Critère de succès :** ouvrage/chapitre ne déclenchent plus de validation HTTP.

---

## Phase 4 — Délégation aux helpers (P2)

**Objectif :** Supprimer progressivement les duplications de logique de construction de template.

**Actions :**
1. Remplacer `_build_lien_web_template()` par appel à `BareUrlHelper.build_repaired_reference_template()`
2. Remplacer construction inline de template par appel à `ReferenceTemplateHelper.generate_archive_repair_template()`
3. Supprimer les fonctions dupliquées dans dead_links.py
4. Ajouter des tests pour vérifier que le comportement est identique

**Critère de succès :** Toute la logique de construction de template est déléguée aux helpers.

---

## Phase 5 — Simplification de DeadLink (P2)

**Objectif :** Réduire dead_links.py en supprimant les responsabilités déléguées.

**Actions :**
1. Supprimer les caches locaux (_check_cache, _repair_cache, _template_cache)
2. Remplacer par appels à DatabaseManager (nouvelle table caches) ou TrackingService
3. Supprimer les fonctions de construction de template (déléguées)
4. Simplifier le flux principal (moins de branches)
5. Réduire la taille de dead_links.py de 2000+ lignes à ~800-1000 lignes

**Critère de succès :** dead_links.py ne contient que la logique d'orchestration DeadLink.

---

## Phase 6 — Migration du Tracking (P1)

**Objectif :** Migrer progressivement les anciens systèmes vers TrackingService.

**Actions :**
1. Pour AnalyzedTracker : migrer les données vers `analysis_results`, déprécier
2. Pour PublishedTracker : migrer les données vers `actions` + `scheduler_queue`, déprécier
3. Pour AutomationStateManager : migrer vers SQLiteAutomationStateManager, déprécier
4. Pour PendingPublishQueue : migrer vers `scheduler_queue`, déprécier
5. Pour LiaLogger : créer `operation_logs` table, migrer logs, déprécier fichiers
6. **PARALLÈLE** : continuer à écrire dans les anciens systèmes pendant transition
7. Ajouter des tests de rétrocompatibilité

**Critère de succès :** TrackingService est la source unique de vérité, anciens systèmes dépréciés mais fonctionnels.

---

## Phase 7 — Suppression du legacy (P4)

**Objectif :** Supprimer les anciens systèmes lorsque les tests prouvent qu'ils ne sont plus nécessaires.

**Actions :**
1. Vérifier qu'aucun code n'utilise les anciens trackers
2. Supprimer AnalyzedTracker
3. Supprimer PublishedTracker
4. Supprimer AutomationStateManager (JSON)
5. Supprimer PendingPublishQueue
6. Supprimer LiaLogger (ou transformer en logging pur)
7. Supprimer Corrector (utils/corrector.py)
8. Nettoyer les imports et dépendances

**Critère de succès :** Seul TrackingService et SQLite subsistent pour le tracking.

---

# 14. TESTS DE NON-RÉGRESSION

## Test 1 : Lien web + 404 + archive valide

```python
def test_lien_web_dead_with_archive():
    content = "{{Lien web|url=https://dead-site.com|titre=Test}}"
    result = deadlink_analyzer.analyze(content)
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.issue_type == "dead_link"
    assert "archive-url" in issue.suggested_text
    assert "archive-date" in issue.suggested_text
```

## Test 2 : Ouvrage + 404 + archive

```python
def test_ouvrage_dead_no_modification():
    content = "{{ouvrage|url=https://dead-site.com|titre=Test}}"
    result = deadlink_analyzer.analyze(content)
    # Soit aucune issue, soit issue avec suggested_text=None
    if result.issues:
        issue = result.issues[0]
        assert issue.suggested_text is None or "archive-url" not in issue.suggested_text
```

## Test 3 : Chapitre + 404

```python
def test_chapitre_dead_no_modification():
    content = "{{chapitre|url=https://dead-site.com|titre=Test}}"
    result = deadlink_analyzer.analyze(content)
    if result.issues:
        issue = result.issues[0]
        assert issue.suggested_text is None or "archive-url" not in issue.suggested_text
```

## Test 4 : URL nue dans <ref> + 404

```python
def test_bare_url_in_ref_with_archive():
    content = "<ref>https://dead-site.com</ref>"
    result = deadlink_analyzer.analyze(content)
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert "{{Lien web" in issue.suggested_text
```

## Test 5 : URL nue hors <ref> + 404

```python
def test_bare_url_out_of_ref_no_modification():
    content = "Voir https://dead-site.com pour plus d'infos."
    result = deadlink_analyzer.analyze(content)
    assert len(result.issues) == 0
```

## Test 6 : Référence académique + URL morte

```python
def test_academic_reference_no_conversion():
    content = "<ref>{{en}}Article title. {{vol.|23}}. https://dead-site.com</ref>"
    result = deadlink_analyzer.analyze(content)
    assert len(result.issues) == 0
```

## Test 7 : URL déjà archivée

```python
def test_already_archived_no_duplicate():
    content = "{{Lien web|url=https://dead-site.com|archive-url=https://archive.org/...}}"
    result = deadlink_analyzer.analyze(content)
    # Ne doit pas ajouter un deuxième archive-url
    assert result.issues == [] or "archive-url" not in issue.suggested_text or count_archive_urls(issue.suggested_text) == 1
```

## Test 8 : URL avec archive-url + brisé le

```python
def test_existing_archive_preserved():
    content = "{{Lien web|url=https://dead-site.com|archive-url=https://archive.org/...|brisé le=2024-01-01}}"
    result = deadlink_analyzer.analyze(content)
    # Doit préserver ou mettre à jour intelligemment
    # Cas spécifique à définir selon règles actuelles
```

## Test 9 : 404 temporaire

```python
def test_temporary_error_no_dead_declaration():
    # Mock LinkChecker pour retourner TEMPORARY_ERROR
    content = "{{Lien web|url=https://temporarily-down.com|titre=Test}}"
    result = deadlink_analyzer.analyze(content)
    assert len(result.issues) == 0 or any(i.extra.get('repair_status') != 'REPAIR_APPLIED' for i in result.issues)
```

## Test 10 : Retry idempotence

```python
def test_retry_idempotence():
    content = "{{Lien web|url=https://dead-site.com|titre=Test}}"
    result1 = deadlink_analyzer.analyze(content)
    result2 = deadlink_analyzer.analyze(content)
    # Même opération ne doit pas créer plusieurs événements de tracking
    # À implémenter après TrackingService
```

## Test 11 : Crash après correction avant publication

```python
def test_crash_recovery():
    # Simuler crash après application wikitext
    # Vérifier que l'état peut être récupéré depuis SQLite
    pass  # À implémenter après Phase 1
```

## Test 12 : Idempotence même URL

```python
def test_idempotence_same_url():
    content = "{{Lien web|url=https://dead-site.com|titre=Test}}"
    result1 = deadlink_analyzer.analyze(content)
    result2 = deadlink_analyzer.analyze(content)
    # Même URL doit produire le même résultat
    assert len(result1.issues) == len(result2.issues)
```

## Tests supplémentaires nécessaires

### Test 13 : Corrélation Issue/Correction

```python
def test_issue_correction_correlation():
    content = "{{Lien web|url=https://dead-site.com|titre=Test}}"
    result = deadlink_analyzer.analyze(content)
    corrections = corrector.apply_corrections(result.issues)
    assert corrections[0].issue_id == result.issues[0].operation_id
```

### Test 14 : Tracking granulaire par URL

```python
def test_tracking_granular_by_url():
    content = "{{Lien web|url=https://dead-site.com|titre=Test}}"
    deadlink_analyzer.analyze(content)
    operation = tracking_service.get_operation_by_url("https://dead-site.com")
    assert operation is not None
    assert operation.url_original == "https://dead-site.com"
```

### Test 15 : Pré-filtrage ouvrage/chapitre

```python
def test_ouvrage_prefilter_no_http_check():
    content = "{{ouvrage|url=https://dead-site.com|titre=Test}}"
    # Mock pour vérifier que LinkChecker n'est PAS appelé
    with mock.patch('LinkChecker.check_link') as mock_check:
        result = deadlink_analyzer.analyze(content)
        mock_check.assert_not_called()  # Ne doit pas appeler HTTP check
```

---

# 15. FICHIERS À MODIFIER

## Fichier : `src/wikipedia_maintenance/analyzers/dead_links.py`

**Modification :**
1. Ajouter génération d'UUID pour chaque opération (avant création Issue)
2. Ajouter operation_id à Issue.extra (ou nouveau champ)
3. Ajouter pré-filtrage par type de template (avant validation HTTP)
4. Remplacer `_build_lien_web_template()` par appel à BareUrlHelper
5. Remplacer construction inline par appel à ReferenceTemplateHelper
6. Supprimer caches locaux (_check_cache, _repair_cache, _template_cache)
7. Ajouter appels à TrackingService pour chaque transition d'état
8. Simplifier le flux principal (supprimer branches dupliquées)

**Pourquoi :**
- Séparer clairement détection, décision, tracking
- Déléguer la construction de template aux helpers
- Établir la corrélation Issue/Correction
- Permettre la reprise après crash

**Risque :**
- Modification du flux principal peut introduire des régressions
- Pré-filtrage peut affecter d'autres types de templates

**Dépendances :**
- Création de TrackingService (Phase 1)
- Extension de DatabaseManager (table deadlink_operations)

**Tests nécessaires :**
- Tests 1-8 (non-régression)
- Test 13 (corrélation)
- Test 15 (pré-filtrage)

---

## Fichier : `src/wikipedia_maintenance/utils/database.py`

**Modification :**
1. Ajouter table `deadlink_operations`
2. Ajouter table `operation_logs` (pour LiaLogger)
3. Ajouter table `caches` (pour caches persistants)
4. Ajouter méthodes DatabaseManager pour ces tables
5. Ajouter indexes pour performance

**Pourquoi :**
- Établir SQLite comme source unique de vérité
- Permettre la persistance des opérations DeadLink
- Permettre la reprise après crash

**Risque :**
- Migration de schema peut échouer
- Performance impactée par indexes

**Dépendances :**
- Aucune (peut être fait indépendamment)

**Tests nécessaires :**
- Tests de migration de schema
- Tests de CRUD sur nouvelles tables

---

## Fichier : `src/wikipedia_maintenance/utils/tracking_service.py` (NOUVEAU)

**Modification :**
1. Créer le fichier
2. Implémenter TrackingService class
3. Implémenter record_operation(), update_operation(), get_operation()
4. Implémenter get_operation_by_url(), get_operation_by_idempotency_key()
5. Implémenter get_stale_operations() pour reprise après crash

**Pourquoi :**
- Centraliser le tracking des opérations DeadLink
- Permettre la corrélation Issue/Correction/Publication
- Permettre la traçabilité granulaire par URL

**Risque :**
- Nouveau module peut introduire des bugs
- Performance impactée par écritures fréquentes

**Dépendances :**
- Extension de DatabaseManager (table deadlink_operations)

**Tests nécessaires :**
- Tests unitaires TrackingService
- Tests d'intégration avec DatabaseManager

---

## Fichier : `src/wikipedia_maintenance/analyzers/base.py`

**Modification :**
1. Ajouter champ `operation_id: Optional[str]` à Issue dataclass
2. Ou modifier Issue.extra pour inclure operation_id

**Pourquoi :**
- Permettre la corrélation Issue/Correction

**Risque :**
- Modification de la structure de Issue peut affecter les consommateurs

**Dépendances :**
- Aucune (peut être fait indépendamment)

**Tests nécessaires :**
- Tests de création d'Issue avec operation_id

---

## Fichier : `src/wikipedia_maintenance/utils/corrector.py` (utils/corrector.py)

**Modification :**
1. Ajouter champ `operation_id: Optional[str]` à Correction dataclass
2. Passer operation_id depuis Issue lors de la création de Correction

**Pourquoi :**
- Permettre la corrélation Issue/Correction

**Risque :**
- Modification de la structure de Correction peut affecter les consommateurs

**Dépendances :**
- Modification de Issue (base.py)

**Tests nécessaires :**
- Tests de création de Correction avec operation_id

---

## Fichier : `src/wikipedia_maintenance/utils/publisher.py`

**Modification :**
1. Appeler TrackingService.update_operation() après publication
2. Passer operation_id à TrackingService

**Pourquoi :**
- Enregistrer le résultat de publication dans TrackingService

**Risque :**
- Si TrackingService échoue, publication peut réussir sans tracking

**Dépendances :**
- Création de TrackingService

**Tests nécessaires :**
- Tests de publication avec TrackingService

---

## Fichier : `backend/api/routes/publication.py`

**Modification :**
1. Appeler TrackingService.update_operation() après publication API
2. Passer operation_id depuis le job de publication

**Pourquoi :**
- Enregistrer le résultat de publication API dans TrackingService

**Risque :**
- Si TrackingService échoue, publication peut réussir sans tracking

**Dépendances :**
- Création de TrackingService

**Tests nécessaires :**
- Tests d'API publication avec TrackingService

---

# 16. FICHIERS À NE PAS MODIFIER

## Fichiers de sécurité (protections existantes)

- **`src/wikipedia_maintenance/utils/reference_template_helper.py`**
  - TEMPLATES_WITHOUT_ARCHIVE_PARAMS
  - TEMPLATES_WITHOUT_SITE_PARAM
  - TEMPLATES_WITHOUT_CONSULTE_LE_PARAM
  - generate_archive_repair_template()
  - **Pourquoi :** Protections critiques, fonctionnent correctement

- **`src/wikipedia_maintenance/utils/link_checker.py`**
  - LinkStatus enum
  - LinkCheckResult
  - **Pourquoi :** Validation HTTP, stable

- **`src/wikipedia_maintenance/utils/link_validator.py`**
  - RepairDecision enum
  - RepairResult
  - **Pourquoi :** Décision de réparation, stable

- **`src/wikipedia_maintenance/utils/bare_url_helper.py`**
  - Détection URLs nues
  - Construction template
  - **Pourquoi :** Fonctionnel, réutilisable

## Fichiers d'observabilité

- **`src/wikipedia_maintenance/utils/event_manager.py`**
  - **Pourquoi :** Observabilité temps réel, indépendant du tracking

## Fichiers de base de données (structure existante)

- **Tables existantes dans DatabaseManager**
  - articles, issues, actions, sessions, analysis_results, etc.
  - **Pourquoi :** Ne pas casser les systèmes existants

---

# 17. FICHIERS POTENTIELLEMENT OBSOLÈTES

## À déprécier (Phase 6)

- **`src/wikipedia_maintenance/utils/analyzed_tracker.py`**
  - Remplacé par : `database.analysis_results`
  - Migration nécessaire : Oui
  - Condition de suppression : Quand tous les consommateurs migrent vers analysis_results

- **`src/wikipedia_maintenance/utils/published_tracker.py`**
  - Remplacé par : `database.actions` + `scheduler_queue`
  - Migration nécessaire : Oui
  - Condition de suppression : Quand tous les consommateurs migrent vers SQLite

- **`src/wikipedia_maintenance/utils/automation_state.py`**
  - Remplacé par : `automation_state_sqlite.py`
  - Migration nécessaire : Oui
  - Condition de suppression : Quand tous les scripts d'automation utilisent SQLite

- **`src/wikipedia_maintenance/utils/pending_publish_queue.py`**
  - Remplacé par : `database.scheduler_queue`
  - Migration nécessaire : Oui
  - Condition de suppression : Quand le scheduler utilise scheduler_queue

- **`src/wikipedia_maintenance/utils/lia_logger.py`**
  - Remplacé par : `database.operation_logs`
  - Migration nécessaire : Oui (historique)
  - Condition de suppression : Garder comme logging pur, ou transformer

## À supprimer (Phase 7)

- **`src/wikipedia_maintenance/utils/corrector.py`**
  - Remplacé par : `publisher.py::Corrector`
  - Migration nécessaire : Non (duplication pure)
  - Condition de suppression : Quand publisher.py::Corrector est le seul utilisé

---

# 18. MATRICE FINALE DES RESPONSABILITÉS

| Fonction | DeadLink | Helper | Corrector | Tracking | Orchestrator |
|----------|---------|--------|-----------|----------|--------------|
| Détecter URL | ✅ PRINCIPAL | - | - | - | - |
| Classifier contexte | ✅ PRINCIPAL | ReferenceTemplateHelper (parsing) | - | - | - |
| Vérifier HTTP | ✅ PRINCIPAL | LinkChecker | - | - | - |
| Redirect | ✅ PRINCIPAL | RedirectFinder | - | - | - |
| Recherche archive | ✅ PRINCIPAL | ArchiveProvider | - | - | - |
| Vérification archive | ✅ PRINCIPAL | ContentVerifier | - | - | - |
| Décision réparation | ✅ PRINCIPAL | LinkValidator | - | - | - |
| Construire correction | - | ReferenceTemplateHelper, BareUrlHelper | - | - | - |
| Appliquer correction | - | - | ✅ PRINCIPAL | - | - |
| Vérifier diff | - | - | ✅ PRINCIPAL | - | - |
| Enregistrer événement | - | - | - | ✅ PRINCIPAL | - |
| Historique | - | - | - | ✅ PRINCIPAL | - |
| Publication | - | - | - | ✅ RECORD | ✅ ORCHESTRATE |

---

# 19. ORDRE EXACT D'IMPLÉMENTATION

## Ordre séquentiel

1. **Phase 0** : Tests et état de référence (2-3 jours)
   - Créer tests 1-12
   - Exécuter baseline
   - Documenter comportement actuel

2. **Phase 1** : Contrat Tracking (3-4 jours)
   - Créer table deadlink_operations
   - Créer TrackingService
   - Ajouter operation_id à Issue
   - Écriture parallèle (ancien + nouveau)

3. **Phase 2** : Corrélation Issue/Correction (2-3 jours)
   - Ajouter operation_id à Correction
   - Corréler via operation_id
   - Tests de corrélation

4. **Phase 3** : Classification en amont (2-3 jours)
   - Pré-filtrage ouvrage/chapitre
   - Tests spécifiques
   - Vérification autres types

5. **Phase 4** : Délégation aux helpers (3-4 jours)
   - Remplacer _build_lien_web_template
   - Remplacer construction inline
   - Supprimer duplications
   - Tests de non-régression

6. **Phase 5** : Simplification de DeadLink (4-5 jours)
   - Supprimer caches locaux
   - Remplacer par DatabaseManager
   - Réduire taille dead_links.py
   - Tests complets

7. **Phase 6** : Migration du Tracking (5-7 jours)
   - Migrer AnalyzedTracker
   - Migrer PublishedTracker
   - Migrer AutomationStateManager
   - Migrer PendingPublishQueue
   - Migrer LiaLogger
   - Tests de rétrocompatibilité

8. **Phase 7** : Suppression du legacy (2-3 jours)
   - Supprimer AnalyzedTracker
   - Supprimer PublishedTracker
   - Supprimer AutomationStateManager (JSON)
   - Supprimer PendingPublishQueue
   - Supprimer corrector.py
   - Tests finaux

**Total estimé :** 23-32 jours

---

# 20. GO / NO-GO

## GO/NO-GO

**Le système peut-il être modifié maintenant ?**

**NON**

## Pourquoi ?

1. **Tests de non-régression absents** : Les tests 1-12 n'existent pas encore. Sans baseline, impossible de garantir la non-régression.

2. **Phase 0 non complétée** : Le comportement actuel n'est pas documenté ni figé par des tests.

3. **Risque de régression élevé** : dead_links.py est un monolithe complexe; toute modification sans tests est risquée.

4. **TrackingService non créé** : La source unique de vérité n'existe pas encore; impossible de corréler les opérations.

5. **Pas de mécanisme de reprise après crash** : L'état actuel ne permet pas la reprise fiable après crash.

## Quels tests doivent être présents avant la première modification ?

**Obligatoires :**
- Test 1 : Lien web + 404 + archive valide
- Test 2 : Ouvrage + 404 + archive (aucune modification)
- Test 3 : Chapitre + 404 (aucune modification)
- Test 4 : URL nue dans <ref> + 404 (conversion autorisée)
- Test 5 : URL nue hors <ref> + 404 (aucune modification)
- Test 6 : Référence académique + URL morte (aucune conversion)
- Test 7 : URL déjà archivée (pas de duplication)
- Test 8 : URL avec archive-url + brisé le (comportement conforme)

**Fortement recommandés :**
- Test 9 : 404 temporaire (pas de fausse déclaration)
- Test 10 : Retry idempotence
- Test 11 : Crash recovery
- Test 12 : Idempotence même URL

## Quelle est la première modification recommandée ?

**Phase 0 : Créer les tests de non-régression.**

1. Créer `tests/test_deadlink_audit.py`
2. Implémenter les tests 1-8 (obligatoires)
3. Exécuter sur l'état actuel → baseline
4. Documenter le comportement actuel (logs, Issue.extra, tracking)
5. **SEULEMENT APRÈS** : passer à Phase 1

---

# INVARIANTS À GARANTIR

1. ✅ Une URL détectée n'est pas automatiquement une URL modifiable (protection par _is_url_in_reference_scope)
2. ✅ Le contexte de référence doit être connu avant toute correction (find_reference_template)
3. ✅ ouvrage et chapitre ne doivent pas être traités comme Lien web (TEMPLATES_WITHOUT_*)
4. ✅ Une URL hors périmètre ne doit jamais être modifiée (_is_url_in_reference_scope)
5. ✅ DeadLink décide de la réparation (LinkValidator)
6. ✅ Corrector applique la réparation (ne redécide pas)
7. ⚠️ Tracking enregistre ce qui s'est passé (à implémenter via TrackingService)
8. ⚠️ Tracking ne doit pas refaire le travail de DeadLink (à garantir par architecture)
9. ⚠️ Une correction doit être reliée à sa détection (à implémenter via operation_id)
10. ✅ Une URL originale ne doit jamais être perdue (conservée dans old_text)
11. ⚠️ Une correction non validée ne doit jamais être considérée comme réussie (à garantir par machine à états)
12. ⚠️ Un retry ne doit pas créer plusieurs événements logiques (à implémenter via idempotency_key)
13. ⚠️ Un crash ne doit pas laisser un état impossible (à implémenter via tracking persistant)
14. ⚠️ Le système doit être idempotent (à implémenter via idempotency_key)
15. ⚠️ Une seule source de vérité doit exister pour l'état opérationnel (à implémenter via SQLite)
16. ✅ Les modules spécialisés existants doivent être réutilisés (plan respecte cela)
17. ✅ Aucun refactoring ne doit supprimer une protection existante sans preuve équivalente (protections conservées)
18. ✅ Aucun changement ne doit être effectué avant validation du plan (en attente approbation)

---

**CONCLUSION :** Le plan est complet et prêt pour validation. Aucune modification ne doit être effectuée avant approbation humaine et complétion de la Phase 0 (tests de non-régression).


/////


Je vais mettre à jour le plan avec vos corrections et confirmer le statut GO/NO-GO.

---

# PLAN RÉVISÉ D'ARCHITECTURE ET DE REFACTORING DEADLINK / TRACKING

## CORRECTIONS APPORTÉES

### Correction A : Caches mémoire vs SQLite

**Original :** Remplacer tous les caches mémoire par une table SQLite `caches`.

**Révisé :** Distinguer les types de caches :

| Type de cache | Actuel | Cible | Justification |
|---------------|--------|-------|---------------|
| **Cache de performance (HTTP, calcul)** | Mémoire (_check_cache, _repair_cache, _template_cache) | Mémoire (ou cache dédié type Redis) | Optimisation de performance, pas de persistance requise |
| **État métier / opérationnel** | Dispersion (Issue.extra, JSON, mémoire) | SQLite (deadlink_operations) | Données métier, doit persister |
| **Historique / audit** | Fichiers log (lia_logger) | SQLite (operation_logs) | Audit trail, doit être structuré et persistant |
| **Événements temps réel** | EventManager (mémoire) | EventManager (mémoire) | Observabilité, pas de persistance requise |

**Action :** NE PAS créer de table `caches` SQLite. Conserver les caches mémoire pour la performance, uniquement documenter leur durée de vie et invalidation.

---

### Correction B : Structure de deadlink_operations

**Original :** Table unique avec tous les champs (détection, HTTP, redirect, archive, repair, correction, validation, publication, erreurs, timestamps).

**Révisé :** Séparer en table principale + table d'événements pour historique :

```sql
-- Table principale : registre de l'opération
CREATE TABLE deadlink_operations (
    id TEXT PRIMARY KEY,  -- UUID
    article_title TEXT NOT NULL,
    revision_id INTEGER,
    operation_id TEXT NOT NULL UNIQUE,  -- UUID de l'opération
    
    -- URL et contexte (immutable)
    url_original TEXT NOT NULL,
    url_normalized TEXT NOT NULL,  -- URL normalisée pour idempotence
    context_type TEXT,
    reference_type TEXT,
    template_name TEXT,
    field_name TEXT,
    
    -- Métadonnées
    idempotency_key TEXT UNIQUE,
    retry_count INTEGER DEFAULT 0,
    
    -- Statut final
    final_status TEXT,  -- Dernier état de la machine à états
    publication_status TEXT,
    
    -- Corrélation
    issue_id TEXT,
    correction_id TEXT,
    publication_job_id TEXT,
    
    -- Timestamps clés
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detected_at TIMESTAMP,
    published_at TIMESTAMP,
    
    FOREIGN KEY (article_title) REFERENCES articles(title)
);

-- Table d'événements : historique des transitions
CREATE TABLE deadlink_operation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- DETECTED, VALIDATED, REPAIR_CANDIDATE, etc.
    event_data TEXT,  -- JSON avec détails spécifiques à l'événement
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (operation_id) REFERENCES deadlink_operations(operation_id)
);

CREATE INDEX idx_deadlink_operations_article ON deadlink_operations(article_title);
CREATE INDEX idx_deadlink_operations_url ON deadlink_operations(url_original);
CREATE INDEX idx_deadlink_operations_normalized_url ON deadlink_operations(url_normalized);
CREATE INDEX idx_deadlink_operations_idempotency ON deadlink_operations(idempotency_key);
CREATE INDEX idx_deadlink_operation_events_operation ON deadlink_operation_events(operation_id);
CREATE INDEX idx_deadlink_operation_events_type ON deadlink_operation_events(event_type);
CREATE INDEX idx_deadlink_operation_events_timestamp ON deadlink_operation_events(timestamp);
```

**Avantages :**
- Historique complet : opération → état A à 10:31 → état B à 10:32 → ...
- Audit trail : chaque transition est un événement avec timestamp
- Flexibilité : peut ajouter de nouveaux types d'événements sans modifier le schéma principal
- Performance : requêtes sur la table principale restent légères

---

### Correction C : Idempotency key révisée

**Original :** `article_title:revision_id:url_original:context_type:reference_type`

**Révisé :** Normalisation + hash + définition précise du comportement

```python
import hashlib
from urllib.parse import urlparse

def normalize_url(url: str) -> str:
    """Normalise l'URL pour idempotence."""
    parsed = urlparse(url)
    # Normalisation : lowercasing scheme/netloc, trailing slash, etc.
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized

def compute_idempotency_key(
    article_title: str,
    revision_id: int,
    url_original: str,
    context_type: str,
    reference_type: str
) -> str:
    """Calcule la clé d'idempotence."""
    normalized_url = normalize_url(url_original)
    key_string = f"{article_title}:{revision_id}:{normalized_url}:{context_type}:{reference_type}"
    return hashlib.sha256(key_string.encode()).hexdigest()
```

**Comportement pour les cas edge :**

| Cas | Comportement |
|-----|--------------|
| **Même URL 2 fois dans même article** | Créer 2 opérations (context_type différent si positions différentes) |
| **Même URL dans 2 `<ref>` différents** | Créer 2 opérations (positions différentes = contextes différents) |
| **Même article, révision différente** | Créer nouvelle opération (revision_id différent) |
| **Correction déjà publiée** | Retourner l'opération existante (final_status = PUBLISHED) |
| **Autre contributeur a modifié la référence** | Créer nouvelle opération (revision_id a changé) |

---

### Correction D : Résolution de la duplication Corrector

**Original :** Le plan dit de supprimer utils/corrector.py mais aussi de lui ajouter operation_id (incohérent).

**Révisé :** Phase 0 doit déterminer lequel est réellement utilisé.

**Action dans Phase 0 (audit de dépendances) :**

```python
# Audit : qui importe quel Corrector ?
grep -r "from.*corrector import" src/
grep -r "import.*corrector" src/
grep -r "Corrector" src/wikipedia_maintenance/ --include="*.py"
```

**Définition de la stratégie :**

- Si `utils/corrector.py::Corrector` est utilisé → migrer vers `publisher.py::Corrector`, puis supprimer
- Si `publisher.py::Corrector` est le seul utilisé → supprimer `utils/corrector.py` immédiatement
- Si les deux sont utilisés → déterminer lequel est "principal", migrer les appels, puis supprimer l'autre

**Action reportée à après Phase 0.**

---

### Correction E : Renforcement de la Phase 0

**Original :** Tests 1-15 puis baseline.

**Révisé :** Audit de dépendances AVANT les tests.

**Nouveau Phase 0 :**

### Phase 0 — Audit de dépendances et état de référence

**Étape 0.1 : Audit structurel (1-2 jours)**

```python
# Cartographie complète des imports et consommateurs
audit_results = {
    'dead_links.py': {
        'imported_by': [...],
        'calls': {
            'analyze()': [...],
            '_is_url_in_reference_scope()': [...],
            ...
        },
        'consumes': ['LinkChecker', 'RedirectFinder', 'ArchiveProvider', ...],
        'produces': ['Issue', 'Issue.extra'],
    },
    'publisher.py::Corrector': {
        'imported_by': [...],
        'used_by': [...],
    },
    'utils/corrector.py::Corrector': {
        'imported_by': [...],
        'used_by': [...],
    },
    'AnalyzedTracker': {
        'written_by': [...],
        'read_by': [...],
    },
    'PublishedTracker': {
        'written_by': [...],
        'read_by': [...],
    },
    ...
}
```

**Étape 0.2 : Tests de caractérisation (2-3 jours)**

- Exécuter le système sur un jeu de données réel
- Capturer les logs, Issue.extra, tracking actuel
- Documenter le comportement réel (pas le supposé)

**Étape 0.3 : Baseline (2-3 jours)**

- Créer tests 1-8 (obligatoires)
- Exécuter sur l'état actuel
- Sauvegarder les résultats comme baseline

**Critère de succès Phase 0 :**
- Audit de dépendances complet
- Tests 1-8 passent sur baseline
- Comportement actuel documenté
- Duplication Corrector résolue (stratégie définie)

---

## ARCHITECTURE VALIDÉE

### Schéma final (inchangé, validé)

```
                    ORCHESTRATOR
                         │
                         ▼
                  DEADLINK ANALYZER
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          CONTEXT     VALIDATION   CLASSIFICATION
             │           │           │
             └───────────┼───────────┘
                         ▼
                  ARCHIVE RESOLVER
                         │
                         ▼
                   REPAIR DECISION
                         │
                         ▼
                 CORRECTION BUILDER
                         │
                         ▼
                     CORRECTOR
                         │
                         ▼
                  DIFF / VALIDATION
                         │
                         ▼
                     PUBLISHER
                         │
                         ▼
                  TRACKING SERVICE
                         │
                         ▼
                      SQLITE
```

### Règle fondamentale (confirmée)

> **DeadLink décide. Corrector applique. Publisher publie. Tracking observe et persiste.**

Le TrackingService ne doit **jamais décider si une URL est réparable**.

---

# VERDICT FINAL

## GO/NO-GO

### 🟢 GO pour Phase 0 uniquement

**Autorisé :**
- Audit de dépendances (étape 0.1)
- Tests de caractérisation (étape 0.2)
- Baseline (étape 0.3)

### 🔴 NO-GO pour toute modification fonctionnelle

**Interdit jusqu'à :**
- Baseline des tests 1-8 établie
- Cartographie réelle des imports et consommateurs complétée
- Duplication Corrector résolue (stratégie définie)
- Modèle SQLite validé (deadlink_operations + deadlink_operation_events)

---

## CONDITIONS PRÉALABLES À PHASE 1

Avant de débuter Phase 1 (Contrat Tracking), les 4 conditions suivantes doivent être remplies :

1. **Baseline des tests 1-8 minimum**
   - Tests créés et passent sur l'état actuel
   - Résultats sauvegardés comme référence

2. **Cartographie réelle des imports et consommateurs**
   - Qui importe DeadLinkAnalyzer ?
   - Qui appelle analyze() ?
   - Qui consomme Issue et Issue.extra ?
   - Qui consomme Correction ?
   - Qui importe publisher.Corrector vs utils.corrector.Corrector ?
   - Qui écrit dans AnalyzedTracker, PublishedTracker, SQLite ?

3. **Résolution de la duplication Corrector**
   - Déterminer lequel des deux est réellement utilisé
   - Définir la stratégie de migration/suppression
   - Confirmer qu'aucun code critique ne dépendra du fichier à supprimer

4. **Validation du modèle SQLite avant migration**
   - Schéma deadlink_operations + deadlink_operation_events validé
   - Scripts de migration testés
   - Performance des indexes évaluée

---

## ORDRE RÉVISÉ D'IMPLÉMENTATION

### Phase 0 — Audit et baseline (5-8 jours)
- Étape 0.1 : Audit de dépendances (1-2 jours)
- Étape 0.2 : Tests de caractérisation (2-3 jours)
- Étape 0.3 : Baseline (2-3 jours)

### Phase 1 — Contrat Tracking (3-4 jours)
- Créer table deadlink_operations + deadlink_operation_events
- Créer TrackingService
- Ajouter operation_id à Issue
- Écriture parallèle (ancien + nouveau)

### Phase 2 — Corrélation Issue/Correction (2-3 jours)
- Résolution duplication Corrector (suite de Phase 0)
- Ajouter operation_id à Correction
- Corréler via operation_id

### Phase 3 — Classification en amont (2-3 jours)
- Pré-filtrage ouvrage/chapitre
- Tests spécifiques

### Phase 4 — Délégation aux helpers (3-4 jours)
- Remplacer _build_lien_web_template
- Remplacer construction inline

### Phase 5 — Simplification de DeadLink (4-5 jours)
- Réduire taille dead_links.py
- Conserver caches mémoire (performance)

### Phase 6 — Migration du Tracking (5-7 jours)
- Migrer AnalyzedTracker, PublishedTracker, etc.
- Conserver EventManager (observabilité)

### Phase 7 — Suppression du legacy (2-3 jours)
- Supprimer trackers obsolètes
- Supprimer corrector.py (si confirmé)

**Total estimé :** 26-37 jours

---

# CONFIRMATION

## Je confirme :

1. ✅ **Aucun fichier ne sera modifié** avant approbation de ce plan révisé
2. ✅ **Aucun refactoring ne sera effectué** avant complétion de Phase 0
3. ✅ **Les caches mémoire seront conservés** pour la performance (pas de table caches SQLite)
4. ✅ **deadlink_operations sera séparé** en table principale + table d'événements
5. ✅ **L'idempotency key sera normalisée** avec hash et comportement edge cases défini
6. ✅ **La duplication Corrector sera résolue** dans Phase 0 (audit de dépendances)
7. ✅ **Phase 0 sera renforcée** avec audit de dépendances avant les tests
8. ✅ **L'architecture cible est validée** avec la règle "DeadLink décide, Corrector applique, Tracking observe"

## En attente de votre approbation pour :

- Démarrer Phase 0 (audit de dépendances + tests de caractérisation + baseline)
- Ou toute autre correction avant GO technique