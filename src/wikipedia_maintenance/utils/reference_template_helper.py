"""
Generic Reference Template Helper for Wikipedia reference templates.

This module provides utilities for:
- Detecting various reference templates ({{Lien web}}, {{article}}, {{ouvrage}}, etc.)
- Parsing template parameters (robust to nested templates/links)
- Generating reference templates with archive parameters

Hardened version: fixes nested-template parsing, brace-balanced template
extraction, safer parameter merging, input validation, and immutability
of parsed structures.
"""

from __future__ import annotations

import re
import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReferenceTemplate:
    """Parsed reference template (immutable snapshot)."""
    template_name: str
    parameters: Dict[str, str] = field(default_factory=dict)
    full_match: str = ""
    start_position: int = -1
    end_position: int = -1
    is_supported: bool = True  # True if template is in KNOWN_TEMPLATE_NAMES


class ReferenceTemplateHelper:
    """
    Generic helper for Wikipedia reference template manipulation.

    Handles multiple reference template types:
    - {{Lien web}}
    - {{article}}
    - {{ouvrage}}
    - {{Lien brisé}}

    When a dead link is repaired with an archive, the helper generates
    the appropriate template format with archive parameters.
    """

    # Template names recognized as reference templates (case-insensitive).
    # Matched against the template's own name (after {{ and before first | or }}).
    KNOWN_TEMPLATE_NAMES = {
        'lien web': 'Lien web',
        'lien_web': 'Lien web',
        'article': 'article',
        'ouvrage': 'ouvrage',
        'chapitre': 'chapitre',
        'podcast': 'podcast',
        'vidéo': 'vidéo',
        'video': 'vidéo',
        'lien brisé': 'Lien brisé',
        'lien_brisé': 'Lien brisé',
        'lien archive': 'Lien archive',
        'lien_archive': 'Lien archive',
        'interview': 'interview',
        # English citation templates (mapped to French equivalents)
        'cite web': 'Lien web',
        'cite_web': 'Lien web',
        'cite news': 'Lien web',
        'cite_news': 'Lien web',
        'cite report': 'Lien web',
        'cite_report': 'Lien web',
        'cite journal': 'article',
        'cite_journal': 'article',
        'cite book': 'ouvrage',
        'cite_book': 'ouvrage',
    }

    # Templates for which it is semantically valid to promote the archive
    # URL to the main `url` parameter. `Lien brisé` explicitly marks a
    # link as broken, so silently pointing `url` at the archive there
    # would misrepresent the template's own semantics.
    # NOTE: All names are lowercase for case-insensitive comparison (all usages normalize template names).
    TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK = {'lien web', 'lien archive', 'interview', 'podcast', 'vidéo'}

    # Templates for which a |site= parameter is not semantically valid
    # (e.g. a book has no "site"). generate_archive_repair_template must
    # never auto-fill |site= for these, whether or not one was already
    # present on a synthetic template built upstream.
    # CHANGED: added to close the gap where an existing {{ouvrage}} going
    # through archive repair could get a |site= injected, since this
    # exclusion previously existed only in BareUrlHelper, not here.
    # Books and chapters are physical/digital publications, not web sites.
    TEMPLATES_WITHOUT_SITE_PARAM = {'ouvrage', 'chapitre'}

    # Whitelist: Templates for which |consulté le= is semantically valid.
    # These are web resources that are consulted online. Physical/digital
    # publications (books, chapters) are NOT included.
    # NOTE: All names are lowercase for case-insensitive comparison (ReferenceEnricherAnalyzer
    # normalizes template names to lowercase before checking this set).
    TEMPLATES_SUPPORTING_CONSULTE_LE = {'lien web', 'lien archive', 'interview', 'podcast', 'vidéo'}

    # Templates for which archive parameters (archive-url, archive-date, brisé le)
    # are NOT semantically valid. These are physical/digital publications that
    # don't have web URLs that can be archived.
    TEMPLATES_WITHOUT_ARCHIVE_PARAMS = {'ouvrage', 'chapitre'}

    # Maps raw archive-provider identifiers to their display/article name
    # on the French Wikipedia. Used only for the human-readable prose
    # rendering (render_archive_repair_prose) — never written into the
    # generated wikitext, since no real reference template has an
    # equivalent parameter.
    PROVIDER_NAMES: Dict[str, str] = {
        'WaybackMachine': 'Internet Archive',
        'Archive.org': 'Internet Archive',
        'Arquivo.pt': 'Arquivo.pt',
        'Wikiwix': 'Wikiwix',
    }

    # Best-effort mapping from a bare domain (as returned by
    # _safe_extract_domain, i.e. urlparse().netloc with any "www."
    # already implied by the source URL) to a human-readable site name
    # for the |site= parameter. 
    # NOTE: This is now loaded from case_normalization_data.yaml for centralized maintenance.
    # The hardcoded fallback below is only used if the YAML file cannot be loaded.
    DOMAIN_TO_SITE_NAME: Dict[str, str] = {}
    
    @classmethod
    def _load_domain_to_site_name_mapping(cls) -> Dict[str, str]:
        """
        Load domain to site name mapping from case_normalization_data.yaml.
        
        Returns:
            Dictionary mapping domains to human-readable site names (preserving wiki link format [[...]]).
            Falls back to empty dict if file cannot be loaded.
        """
        try:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "case_normalization_data.yaml"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                    if config_data and 'domain_to_site_name' in config_data:
                        # Extract the site names from the YAML format
                        # YAML format: "domain.com: [[Site Name]]" -> we want "domain.com": "[[Site Name]]"
                        # We preserve the wiki link format [[...]] for use in |site= parameter
                        mapping = {}
                        for domain, wiki_links in config_data['domain_to_site_name'].items():
                            if wiki_links and isinstance(wiki_links, list) and len(wiki_links) > 0:
                                # Keep the wiki link format [[Site Name]] as-is
                                site_name = wiki_links[0]
                                mapping[domain] = site_name
                        logger.info(f"Loaded {len(mapping)} domain->site name mappings from YAML")
                        return mapping
        except Exception as e:
            logger.warning(f"Failed to load domain_to_site_name from YAML: {e}. Using empty mapping.")
        
        return {}

    # French month names for prose date rendering ("5 janvier 2015").
    _FRENCH_MONTHS = [
        '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
        'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
    ]

    # Common parameters across reference templates (fallback ordering).
    COMMON_PARAMETERS: List[str] = [
        'langue',
        'auteur', 'auteur1', 'auteur2', 'auteur3', 'auteur4', 'auteur5',
        'auteur prénom', 'auteur nom', 'auteur lien',
        'auteur1 prénom', 'auteur1 nom', 'auteur1 lien',
        'auteur2 prénom', 'auteur2 nom', 'auteur2 lien',
        'auteur3 prénom', 'auteur3 nom', 'auteur3 lien',
        'et al.', 'auteur institutionnel',
        'traducteur', 'photographe', 'directeur', 'éditeur', 'publisher',
        'titre', 'sous-titre', 'traduction titre', 'description',
        'url', 'lire en ligne', 'url texte', 'lien',
        'format électronique', 'accès url',
        'série', 'work', 'site', 'website', 'périodique', 'journal',
        'lieu', 'lieu édition', 'location',
        'date', 'année', 'year', 'en ligne le', 'en ligne',
        'date jour', 'date mois', 'date année',
        'volume', 'numéro', 'issue', 'pages', 'page',
        'archive-url', 'archiveurl', 'archive-date', 'archivedate',
        'brisé le', 'dead-url', 'deadurl', 'lien brisé',
        'isbn', 'issn', 'e-issn', 'oclc', 'pmid', 'pmcid',
        'doi', 'accès doi', 'jstor', 'bibcode', 'math reviews', 'zbmath', 'arxiv',
        'consulté le', 'extrait', 'citation', 'quote', 'passage',
        'id', 'libellé', 'plume', 'nature document', 'afficher plume', 'nocat',
    ]

    TEMPLATE_SPECIFIC_PARAMETERS: Dict[str, List[str]] = {
        'Lien web': [
            'langue',
            'auteur', 'auteur prénom', 'auteur nom', 'auteur lien', 'auteur responsabilité', 'auteur directeur',
            'auteur2', 'auteur2 prénom', 'auteur2 nom', 'auteur2 lien', 'auteur2 responsabilité', 'auteur2 directeur',
            'auteur3', 'auteur3 prénom', 'auteur3 nom',
            'auteur4', 'auteur4 prénom', 'auteur4 nom',
            'auteur5', 'auteur5 prénom', 'auteur5 nom',
            'auteur6', 'auteur6 prénom', 'auteur6 nom',
            'auteur7', 'auteur7 prénom', 'auteur7 nom',
            'auteur8', 'auteur8 prénom', 'auteur8 nom',
            'auteur9', 'auteur9 prénom', 'auteur9 nom',
            'auteur10', 'auteur10 prénom', 'auteur10 nom',
            'auteur11', 'auteur11 prénom', 'auteur11 nom',
            'auteur12', 'auteur12 prénom', 'auteur12 nom',
            'auteur13', 'auteur13 prénom', 'auteur13 nom',
            'auteur14', 'auteur14 prénom', 'auteur14 nom',
            'et al.', 'auteur institutionnel',
            'traducteur', 'photographe',
            'titre', 'sous-titre', 'traduction titre', 'description',
            'url', 'lire en ligne', 'url texte', 'lien',
            'format électronique', 'accès url',
            'série', 'work', 'site', 'website', 'périodique',
            'lieu', 'lieu édition', 'location',
            'éditeur', 'publisher', 'editeur',
            'date', 'année', 'year', 'en ligne le', 'en ligne',
            'date jour', 'date mois', 'date année',
            'archive-url', 'archiveurl', 'archive-date', 'archivedate',
            'brisé le', 'dead-url', 'deadurl', 'lien brisé',
            'isbn', 'issn', 'e-issn', 'oclc', 'pmid', 'pmcid',
            'doi', 'accès doi', 'jstor', 'bibcode', 'math reviews', 'zbmath', 'arxiv',
            'consulté le', 'extrait', 'citation', 'quote', 'page', 'pages', 'passage',
            'id', 'libellé', 'plume', 'nature document', 'afficher plume', 'nocat',
        ],
        'article': [
            'langue',
            'auteur', 'auteur prénom', 'auteur nom', 'auteur lien', 'auteur responsabilité', 'auteur directeur',
            'auteur2', 'auteur2 prénom', 'auteur2 nom', 'auteur2 lien', 'auteur2 responsabilité', 'auteur2 directeur',
            'auteur3', 'auteur3 prénom', 'auteur3 nom',
            'auteur4', 'auteur4 prénom', 'auteur4 nom',
            'auteur5', 'auteur5 prénom', 'auteur5 nom',
            'auteur6', 'auteur6 prénom', 'auteur6 nom',
            'auteur7', 'auteur7 prénom', 'auteur7 nom',
            'auteur8', 'auteur8 prénom', 'auteur8 nom',
            'auteur9', 'auteur9 prénom', 'auteur9 nom',
            'auteur10', 'auteur10 prénom', 'auteur10 nom',
            'auteur11', 'auteur11 prénom', 'auteur11 nom',
            'auteur12', 'auteur12 prénom', 'auteur12 nom',
            'auteur13', 'auteur13 prénom', 'auteur13 nom',
            'auteur14', 'auteur14 prénom', 'auteur14 nom',
            'et al.', 'auteur institutionnel',
            'traducteur', 'photographe',
            'titre', 'sous-titre', 'traduction titre', 'description',
            'url', 'lire en ligne', 'url texte', 'lien',
            'format électronique', 'accès url',
            'série', 'work', 'site', 'website', 'périodique',
            'lieu', 'lieu édition', 'location',
            'éditeur', 'publisher', 'editeur',
            'date', 'année', 'year', 'en ligne le', 'en ligne',
            'date jour', 'date mois', 'date année',
            'volume', 'numéro', 'issue', 'pages', 'page',
            'archive-url', 'archiveurl', 'archive-date', 'archivedate',
            'brisé le', 'dead-url', 'deadurl', 'lien brisé',
            'isbn', 'issn', 'e-issn', 'oclc', 'pmid', 'pmcid',
            'doi', 'accès doi', 'jstor', 'bibcode', 'math reviews', 'zbmath', 'arxiv',
            'consulté le', 'extrait', 'citation', 'quote', 'passage',
            'id', 'libellé', 'plume', 'nature document', 'afficher plume', 'nocat',
        ],
        'ouvrage': [
            'langue',
            'auteur', 'auteur prénom', 'auteur nom', 'auteur lien', 'auteur responsabilité', 'auteur directeur',
            'auteur2', 'auteur2 prénom', 'auteur2 nom', 'auteur2 lien', 'auteur2 responsabilité', 'auteur2 directeur',
            'auteur3', 'auteur3 prénom', 'auteur3 nom',
            'auteur4', 'auteur4 prénom', 'auteur4 nom',
            'auteur5', 'auteur5 prénom', 'auteur5 nom',
            'auteur6', 'auteur6 prénom', 'auteur6 nom',
            'auteur7', 'auteur7 prénom', 'auteur7 nom',
            'auteur8', 'auteur8 prénom', 'auteur8 nom',
            'auteur9', 'auteur9 prénom', 'auteur9 nom',
            'auteur10', 'auteur10 prénom', 'auteur10 nom',
            'et al.', 'auteur institutionnel',
            'traducteur', 'langue originale', 'préface', 'postface', 'illustrateur', 'photographe', 'champ libre',
            'titre', 'sous-titre', 'titre original', 'titre traduction',
            'volume', 'tome', 'volume titre',
            'lieu', 'éditeur', 'nature ouvrage', 'collection', 'série', 'numéro dans collection',
            'année', 'mois', 'jour', 'date', 'édition numéro', 'année première édition', 'réimpression',
            'format livre', 'pages totales', 'passage', 'page',
            'isbn', 'isbn2', 'isbn3', 'isbn 10', 'isbn erroné',
            'issn', 'e-issn', 'ismn', 'ean', 'oclc', 'notice bnf', 'sbn', 'lccn', 'dnb',
            'pmid', 'doi', 'accès doi', 'jstor', 'bibcode', 'math reviews', 'zbmath', 'arxiv', 'hal', 'hdl',
            'accès hdl', 's2cid', 'libris', 'citeseerx', 'jfm', 'sudoc', 'wikisource',
            'présentation en ligne', 'lire en ligne', 'accès url', 'format électronique', 'consulté le',
            'partie', 'chapitre numéro', 'chapitre titre',
            'identifiant', 'libellé', 'référence', 'référence simplifiée', 'extrait', 'commentaire', 'plume', 'nocat',
        ],
        'Lien brisé': [
            'titre', 'url', 'date', 'brisé le', 'archive-url', 'archive-date',
        ],
        'Lien archive': [
            'titre', 'url', 'horodatage archive', 'date', 'éditeur', 'format',
            'langue', 'auteur', 'auteur prénom', 'auteur nom', 'auteur lien',
            'site', 'consulté le', 'archive-url', 'archive-date', 'brisé le',
        ],
    }

    # Matches the template's opening tag and captures its bare name,
    # e.g. "{{ Lien web |" -> "Lien web". Used only to identify the
    # template type once brace-balanced extraction has found its bounds.
    _TEMPLATE_NAME_RE = re.compile(r'\{\{\s*([^|{}]+?)\s*(?:\||\}\})')

    # Parses `key=value` pairs from *top-level* pipe-separated segments
    # only (see _split_top_level). Kept simple: segments are pre-split
    # respecting nested {{ }} and [[ ]], so this just splits on the
    # first '=' within a segment.
    _PARAM_KV_RE = re.compile(r'^\s*([^=]+?)\s*=\s*(.*)$', re.DOTALL)

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ------------------------------------------------------------------
    # Template discovery
    # ------------------------------------------------------------------

    def find_reference_template(self, content: str, url: str, position: int) -> Optional[ReferenceTemplate]:
        """
        Find if a URL is part of a reference template.

        Uses brace-balanced scanning (not naive rfind/find) so templates
        containing nested templates (e.g. {{date|...}}) or double
        brackets ([[...]]) in parameter values are handled correctly.

        Args:
            content: Full wikitext content
            url: URL to search for (used only for logging)
            position: Position of the URL in content

        Returns:
            ReferenceTemplate if found, None otherwise
        """
        if not content or position < 0 or position > len(content):
            self._logger.info(f"TEMPLATE_NOT_FOUND | url={url} | reason=invalid_position")
            return None

        bounds = self._find_enclosing_template_bounds(content, position)
        if bounds is None:
            self._logger.info(f"TEMPLATE_NOT_FOUND | url={url} | reason=no_enclosing_template")
            return None

        template_start, template_end = bounds
        template_content = content[template_start:template_end]

        self._logger.info(
            f"TEMPLATE_CANDIDATE | url={url} | template_start={template_start} | "
            f"template_end={template_end} | content_length={len(template_content)}"
        )

        name_match = self._TEMPLATE_NAME_RE.match(template_content)
        if not name_match:
            self._logger.info(f"TEMPLATE_NOT_MATCHED | url={url} | reason=unparseable_name")
            return None

        raw_name = name_match.group(1).strip()
        normalized = raw_name.lower().replace('_', ' ')
        template_name = self.KNOWN_TEMPLATE_NAMES.get(normalized)

        if template_name is None:
            # Template exists but is not supported - return with is_supported=False
            # This allows callers to distinguish between "no template" and "unsupported template"
            parameters = self._parse_template_parameters(template_content)
            self._logger.info(
                f"TEMPLATE_UNSUPPORTED | url={url} | raw_name={raw_name!r} | "
                f"template_content={template_content[:200]!r}"
            )
            return ReferenceTemplate(
                template_name=raw_name,  # Use the actual name found
                parameters=parameters,
                full_match=template_content,
                start_position=template_start,
                end_position=template_end,
                is_supported=False  # Mark as unsupported
            )

        parameters = self._parse_template_parameters(template_content)

        self._logger.info(
            f"TEMPLATE_FOUND | url={url} | template_name={template_name} | "
            f"parameters_count={len(parameters)}"
        )

        return ReferenceTemplate(
            template_name=template_name,
            parameters=parameters,
            full_match=template_content,
            start_position=template_start,
            end_position=template_end,
            is_supported=True  # Mark as supported
        )

    def _find_enclosing_template_bounds(self, content: str, position: int) -> Optional[Tuple[int, int]]:
        """
        Find the start/end indices of the innermost {{...}} template
        that encloses `position`, using proper brace balancing.

        Returns (start, end) where end is exclusive (i.e. content[start:end]
        includes the trailing '}}'), or None if no enclosing template exists.
        """
        # Find all template start markers before `position`, walk forward
        # from each candidate (nearest first) balancing braces until we
        # either enclose `position` or overshoot it.
        search_from = 0
        best: Optional[Tuple[int, int]] = None

        while True:
            start = content.find('{{', search_from)
            if start == -1 or start > position:
                break

            end = self._match_balanced_braces(content, start)
            if end is not None and start <= position < end:
                # Keep the innermost (latest-starting) enclosing template.
                best = (start, end)

            search_from = start + 2

        return best

    @staticmethod
    def _match_balanced_braces(content: str, open_pos: int) -> Optional[int]:
        """
        Given the index of an opening '{{', return the index just past
        the matching closing '}}', accounting for nested {{ }}.
        Returns None if unbalanced.
        """
        depth = 0
        i = open_pos
        length = len(content)
        while i < length - 1:
            two = content[i:i + 2]
            if two == '{{':
                depth += 1
                i += 2
                continue
            if two == '}}':
                depth -= 1
                i += 2
                if depth == 0:
                    return i
                continue
            i += 1
        return None

    # ------------------------------------------------------------------
    # Parameter parsing
    # ------------------------------------------------------------------

    def _parse_template_parameters(self, template_content: str) -> Dict[str, str]:
        """
        Parse parameters from a reference template, respecting nested
        {{ }} and [[ ]] structures so a value like
        {{date|2020|01|01}} or [[Some|Link]] is not truncated at its
        internal '|'.

        Args:
            template_content: Full template string including {{...}}

        Returns:
            Dictionary of parameter names to values (first occurrence wins,
            except that a later archive.org duplicate is always ignored).
        """
        if not (template_content.startswith('{{') and template_content.endswith('}}')):
            self._logger.info("PARAM_PARSE_SKIPPED | reason=malformed_template_bounds")
            return {}

        inner = template_content[2:-2]

        first_pipe = self._find_top_level_pipe(inner, start=0)
        if first_pipe is None:
            # No parameters at all (e.g. "{{Lien web}}").
            return {}

        params_blob = inner[first_pipe + 1:]
        segments = self._split_top_level(params_blob)

        parameters: Dict[str, str] = {}
        for segment in segments:
            kv = self._PARAM_KV_RE.match(segment)
            if not kv:
                # Positional/unnamed parameter or malformed segment; skip
                # rather than corrupt the map with a bogus key.
                if segment.strip():
                    self._logger.info(f"PARAM_PARSE_SKIPPED_SEGMENT | segment={segment[:80]!r}")
                continue

            key = kv.group(1).strip()
            value = kv.group(2).strip()
            if not key:
                continue

            if key not in parameters:
                parameters[key] = value
            else:
                if 'web.archive.org' in value or 'archive.org' in value:
                    self._logger.info(f"SKIPPING_DUPLICATE_ARCHIVE_PARAM | key={key} | value={value[:120]}")
                    continue
                self._logger.info(
                    f"KEEPING_FIRST_OCCURRENCE | key={key} | "
                    f"first={parameters[key][:60]} | second={value[:60]}"
                )

        return parameters

    @staticmethod
    def _find_top_level_pipe(text: str, start: int = 0) -> Optional[int]:
        """Find the index of the first '|' not nested inside {{ }} or [[ ]]."""
        depth_curly = 0
        depth_bracket = 0
        i = start
        length = len(text)
        while i < length:
            two = text[i:i + 2]
            if two == '{{':
                depth_curly += 1
                i += 2
                continue
            if two == '}}':
                depth_curly = max(0, depth_curly - 1)
                i += 2
                continue
            if two == '[[':
                depth_bracket += 1
                i += 2
                continue
            if two == ']]':
                depth_bracket = max(0, depth_bracket - 1)
                i += 2
                continue
            if text[i] == '|' and depth_curly == 0 and depth_bracket == 0:
                return i
            i += 1
        return None

    @classmethod
    def _split_top_level(cls, text: str) -> List[str]:
        """Split text on '|' characters that aren't nested inside {{ }} or [[ ]]."""
        segments: List[str] = []
        depth_curly = 0
        depth_bracket = 0
        current: List[str] = []
        i = 0
        length = len(text)
        while i < length:
            two = text[i:i + 2]
            if two == '{{':
                depth_curly += 1
                current.append(two)
                i += 2
                continue
            if two == '}}':
                depth_curly = max(0, depth_curly - 1)
                current.append(two)
                i += 2
                continue
            if two == '[[':
                depth_bracket += 1
                current.append(two)
                i += 2
                continue
            if two == ']]':
                depth_bracket = max(0, depth_bracket - 1)
                current.append(two)
                i += 2
                continue
            if text[i] == '|' and depth_curly == 0 and depth_bracket == 0:
                segments.append(''.join(current))
                current = []
                i += 1
                continue
            current.append(text[i])
            i += 1
        segments.append(''.join(current))
        return segments

    # ------------------------------------------------------------------
    # Template generation
    # ------------------------------------------------------------------

    def generate_archive_repair_template(
        self,
        original_template: ReferenceTemplate,
        archive_url: str,
        archive_date: str,
        original_url: str,
        assume_patch_deployed: bool = False,
        provider: Optional[str] = None,
    ) -> str:
        """
        Generate a reference template string with archive parameters
        merged in, preserving all existing parameters.

        Args:
            original_template: Original parsed template
            archive_url: Archive URL to use
            archive_date: Archive date from provider (YYYYMMDDHHMMSS or YYYY-MM-DD)
            original_url: Original dead URL
            assume_patch_deployed: If True and the template type supports it,
                use the archive URL as the main `url` link.
            provider: Raw archive provider identifier (e.g. 'WaybackMachine',
                'Arquivo.pt'). NOTE: `archive-host` is not a recognized
                parameter of the real Wikipedia {{Lien web}}/{{article}}/
                {{ouvrage}} templates — MediaWiki does not render it, so it
                is never written into the generated wikitext. The provider
                is only resolved/logged here; use
                render_archive_repair_prose() if you need a human-readable
                "via Internet Archive" mention in prose output.

        Returns:
            New template string with archive parameters.

        Raises:
            ValueError: if required inputs are missing/invalid.
        """
        if original_template is None:
            raise ValueError("original_template is required")
        if not archive_url or not archive_url.strip():
            raise ValueError("archive_url must be a non-empty string")
        if not original_url or not original_url.strip():
            raise ValueError("original_url must be a non-empty string")

        archive_url = archive_url.strip()
        original_url = original_url.strip()

        params = dict(original_template.parameters)  # shallow copy; safe, immutable source

        # Check if this template type supports archive parameters at all
        # Normalize template name for comparison to handle case/spacing variations
        normalized_template_name = original_template.template_name.lower().replace('_', ' ')
        if normalized_template_name in self.TEMPLATES_WITHOUT_ARCHIVE_PARAMS:
            self._logger.info(f"ARCHIVE_PARAMS_SKIPPED | template={original_template.template_name} | reason=template_does_not_support_archives")
            # Skip all archive parameter handling for these templates
            # Just return the original template unchanged
            return original_template.full_match

        # Normalize template name for comparison to handle case/spacing variations
        normalized_template_name = original_template.template_name.lower().replace('_', ' ')
        can_promote_archive = (
            assume_patch_deployed
            and normalized_template_name in self.TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK
        )
        params['url'] = archive_url if can_promote_archive else original_url

        params['archive-url'] = archive_url

        formatted_archive_date = self._format_archive_date(archive_date)
        if formatted_archive_date:
            params['archive-date'] = formatted_archive_date

        # Get current date for brisé le and consulté le
        current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        # Only add brisé le if not already present (preserve existing value)
        if 'brisé le' not in params and 'dead-url' not in params and 'deadurl' not in params and 'lien brisé' not in params:
            params['brisé le'] = current_date

        # Add consultation date if not already present (date when the URL was verified)
        if 'consulté le' not in params:
            params['consulté le'] = current_date

        if provider:
            # Resolved/logged for traceability only. Deliberately NOT
            # written into `params`: no real Wikipedia reference template
            # has an `archive-host` (or equivalent) parameter, so writing
            # it would produce an unrecognized-parameter artifact that
            # MediaWiki silently ignores in the rendered page.
            resolved_provider = self.PROVIDER_NAMES.get(provider, provider)
            self._logger.info(f"PROVIDER_RESOLVED_NOT_WRITTEN | raw={provider} | resolved={resolved_provider}")

        # Clean up stale "dead" flags now that the link has been repaired,
        # to avoid contradictory metadata (e.g. deadurl=yes alongside a
        # freshly archived, working url).
        for stale_key in ('dead-url', 'deadurl'):
            params.pop(stale_key, None)

        # CHANGED: templates without a valid |site= (e.g. 'ouvrage') must
        # never have one auto-filled OR carried over from a pre-existing
        # synthetic value — a book has no "site". Previously this
        # exclusion existed only in BareUrlHelper; an existing {{ouvrage}}
        # going through archive repair here had no such guard.
        # Normalize template name for comparison to handle case/spacing variations
        site_not_applicable = normalized_template_name in self.TEMPLATES_WITHOUT_SITE_PARAM
        if site_not_applicable:
            params.pop('site', None)
        elif 'site' not in params and 'périodique' not in params and 'work' not in params:
            # Only auto-fill site parameter if not already present.
            # Never touch 'série' or 'collection' parameters - they are manually curated.
            # Policy: FEW ENRICHMENTS + ZERO UNRELATED CHANGES - conservative blocking
            # Check both lowercase and capitalized variants
            série = params.get('série') or params.get('Série')
            collection = params.get('collection') or params.get('Collection')
            editeur = params.get('éditeur') or params.get('Éditeur')
            if série or collection or editeur:
                self._logger.info(f"ARCHIVE_SITE_SKIPPED | template={original_template.template_name} | reason=manually_curated_params_present")
            else:
                original_domain = self._safe_extract_domain(original_url)
                if original_domain:
                    site_value = self._resolve_site_display_name(original_domain)
                    # Check if titre already contains the site name to avoid duplication
                    # Normalize for comparison (case-insensitive, remove brackets and www)
                    site_clean = site_value.strip().lower().replace('www.', '').replace('[[', '').replace(']]', '')
                    titre = params.get('titre')
                    if titre:
                        titre_clean = titre.strip().lower().replace('www.', '').replace('[[', '').replace(']]', '')
                        if site_clean == titre_clean or site_clean in titre_clean or titre_clean in site_clean:
                            self._logger.info(f"ARCHIVE_SITE_SKIPPED | template={original_template.template_name} | reason=titre_contains_site_name")
                        else:
                            params['site'] = site_value
                    else:
                        params['site'] = site_value
        elif 'site' in params:
            # CHANGED: resolve a raw domain already sitting in |site= to its
            # display name too, so a value written upstream (e.g. by
            # BareUrlHelper) is rendered consistently with the case where
            # this method fills |site= itself. _resolve_site_display_name
            # returns its input unchanged when it isn't a recognized bare
            # domain (e.g. an already human-readable name, or a wikilink),
            # so this can only normalize a raw domain, never corrupt a
            # deliberately curated value.
            existing_site = params['site']

            # Correct www. prefix in existing site value if present
            if existing_site and existing_site.strip().startswith('www.'):
                from urllib.parse import urlparse
                if '://' in existing_site:
                    # It's a full URL, extract domain
                    parsed = urlparse(existing_site)
                    domain = parsed.netloc.replace('www.', '')
                else:
                    # It's just a domain
                    domain = existing_site.strip().replace('www.', '')

                # Try to get the mapped site name for the corrected domain
                corrected_site = self._resolve_site_display_name(domain)

                # If mapping found and it's different, use it
                if corrected_site and corrected_site != existing_site.strip():
                    self._logger.info(f"ARCHIVE_SITE_CORRECTION | template={original_template.template_name} | existing_site={existing_site} | new_site={corrected_site} | reason=remove_www_prefix_with_mapping")
                    params['site'] = corrected_site
                # If no mapping found, still remove www. prefix (plain domain)
                elif domain != existing_site.strip():
                    self._logger.info(f"ARCHIVE_SITE_CORRECTION | template={original_template.template_name} | existing_site={existing_site} | new_site={domain} | reason=remove_www_prefix_no_mapping")
                    params['site'] = domain
            else:
                params['site'] = self._resolve_site_display_name(existing_site)

        # Preserve original parameter order instead of using predefined order
        # This prevents parameter reordering (e.g., format=pdf moving to the end)
        template_parts = [f'{{{{{original_template.template_name}']
        
        # Get original parameter order from the template's full_match
        # Parse the original template to extract parameter order
        original_param_order = []
        if original_template.full_match:
            template_content = original_template.full_match[2:-2]  # Remove {{ and }}
            segments = self._split_top_level(template_content)
            for segment in segments[1:]:  # Skip template name
                # Use the same regex as _parse_template_parameters for consistency
                kv = self._PARAM_KV_RE.match(segment)
                if kv:
                    param_name = kv.group(1).strip()
                    original_param_order.append(param_name)
        
        # Add parameters in original order
        emitted = set()
        for param in original_param_order:
            if param in params:
                template_parts.append(f'|{param}={params[param]}')
                emitted.add(param)
        
        # Add any new parameters (archive-url, archive-date, etc.) that weren't in original
        for param, value in params.items():
            if param not in emitted:
                template_parts.append(f'|{param}={value}')

        template_parts.append('}}')
        new_template = ''.join(template_parts)

        self._logger.info(
            f"GENERATED_ARCHIVE_TEMPLATE | template={original_template.template_name} | "
            f"original_url={original_url} | archive_url={archive_url} | "
            f"archive_date={formatted_archive_date} | assume_patch_deployed={assume_patch_deployed} | "
            f"archive_promoted={can_promote_archive}"
        )

        return new_template

    @staticmethod
    def _safe_extract_domain(url: str) -> str:
        try:
            return urlparse(url).netloc
        except (ValueError, AttributeError):
            return ""

    def _resolve_site_display_name(self, domain: str) -> str:
        """
        Best-effort lookup of a human-readable site name for |site=,
        given a bare domain (e.g. "music.apple.com").

        Looks up domain_to_site_name from YAML first with the domain exactly as
        given, then with a "www." prefix stripped (covers both
        "www.example.com" and "example.com" entries interchangeably).
        Falls back to returning the domain without www when nothing
        matches in the mapping.
        
        The YAML mapping contains wiki link format [[Site Name]] which is preserved.
        """
        if not domain:
            return domain

        # Load mapping from YAML (cached at class level for efficiency)
        if not ReferenceTemplateHelper.DOMAIN_TO_SITE_NAME:
            ReferenceTemplateHelper.DOMAIN_TO_SITE_NAME = self._load_domain_to_site_name_mapping()

        # Try exact match first
        mapped = ReferenceTemplateHelper.DOMAIN_TO_SITE_NAME.get(domain)
        if mapped:
            return mapped

        # Try without www prefix
        if domain.startswith('www.'):
            domain_without_www = domain[len('www.'):]
            mapped = ReferenceTemplateHelper.DOMAIN_TO_SITE_NAME.get(domain_without_www)
            if mapped:
                return mapped

        # Fallback: return domain without www (no wiki link brackets)
        if domain.startswith('www.'):
            return domain[len('www.'):]
        
        return domain

    def _format_archive_date(self, archive_date: Optional[str]) -> str:
        """
        Format archive date for the reference template.

        Archive providers typically return dates as YYYYMMDDHHMMSS.
        This converts to YYYY-MM-DD; already-formatted or unrecognized
        inputs are handled gracefully instead of raising.

        Args:
            archive_date: Archive date string, or None/empty.

        Returns:
            Formatted date (YYYY-MM-DD), or "" if unavailable.
        """
        if not archive_date:
            return ""

        archive_date = archive_date.strip()
        if not archive_date:
            return ""

        # Already YYYY-MM-DD.
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', archive_date):
            return archive_date

        # YYYYMMDD[HHMMSS] numeric form.
        digits = re.sub(r'\D', '', archive_date)
        if len(digits) >= 8:
            year, month, day = digits[0:4], digits[4:6], digits[6:8]
            if year.isdigit() and 1 <= int(month or 0) <= 12 and 1 <= int(day or 0) <= 31:
                return f"{year}-{month}-{day}"

        self._logger.info(f"ARCHIVE_DATE_FORMAT_UNRECOGNIZED | raw={archive_date!r}")
        return archive_date

    def generate_enriched_template(
        self,
        original_template: ReferenceTemplate,
        site_value: Optional[str] = None,
        consulte_le_value: Optional[str] = None,
    ) -> str:
        """
        Generate a reference template string with enrichment parameters
        (site and/or consulté le) added, preserving all existing parameters.

        This method is specifically for ReferenceEnricherAnalyzer to add
        missing site and consulté le parameters to healthy reference templates.

        Args:
            original_template: Original parsed template
            site_value: Site value to add if missing (None to skip)
            consulte_le_value: Consulté le value to add if missing (None to skip)

        Returns:
            New template string with enrichment parameters added.
            Returns original template unchanged if no parameters need to be added.

        Raises:
            ValueError: if original_template is None.
        """
        if original_template is None:
            raise ValueError("original_template is required")

        # Check if any enrichment is needed using parameter variants
        # Check both 'site' and 'Site' variants
        current_site = original_template.parameters.get('site') or original_template.parameters.get('Site') or original_template.parameters.get('website')

        # Check 'consulté le' variants including case variations
        current_consulte_le = original_template.parameters.get('consulté le') or original_template.parameters.get('Consulté le') or original_template.parameters.get('consulte le')

        # If both parameters are already present and non-empty, no enrichment needed
        # unless site needs www. prefix correction
        site_needs_correction = current_site and current_site.strip().startswith('www.')
        if current_site and current_consulte_le and not site_needs_correction:
            self._logger.info(f"ENRICHMENT_NOT_NEEDED | template={original_template.template_name} | reason=both_params_present")
            return original_template.full_match

        # If no values to add and no site correction needed, no enrichment needed
        if (not site_value or not site_value.strip()) and (not consulte_le_value or not consulte_le_value.strip()) and not site_needs_correction:
            self._logger.info(f"ENRICHMENT_NOT_NEEDED | template={original_template.template_name} | reason=no_values_to_add")
            return original_template.full_match

        params = dict(original_template.parameters)  # shallow copy; safe, immutable source

        # Correct www. prefix in existing site value if present
        if site_needs_correction:
            from urllib.parse import urlparse
            if '://' in current_site:
                # It's a full URL, extract domain
                parsed = urlparse(current_site)
                domain = parsed.netloc.replace('www.', '')
            else:
                # It's just a domain
                domain = current_site.strip().replace('www.', '')

            # Try to get the mapped site name for the corrected domain
            corrected_site = self._resolve_site_display_name(domain)

            # If mapping found and it's different, use it
            if corrected_site and corrected_site != current_site.strip():
                self._logger.info(f"ENRICHMENT_SITE_CORRECTION | template={original_template.template_name} | existing_site={current_site} | new_site={corrected_site} | reason=remove_www_prefix_with_mapping")
                params['site'] = corrected_site
            # If no mapping found, still remove www. prefix (plain domain)
            elif domain != current_site.strip():
                self._logger.info(f"ENRICHMENT_SITE_CORRECTION | template={original_template.template_name} | existing_site={current_site} | new_site={domain} | reason=remove_www_prefix_no_mapping")
                params['site'] = domain

        # Add site parameter if missing and value provided
        if site_value and site_value.strip() and not current_site:
            # Check if template supports site parameter
            # Normalize template name for comparison to handle case/spacing variations
            normalized_template_name = original_template.template_name.lower().replace('_', ' ')
            if normalized_template_name not in self.TEMPLATES_WITHOUT_SITE_PARAM:
                # Skip if manually curated parameters are present (série, collection, éditeur)
                # Policy: FEW ENRICHMENTS + ZERO UNRELATED CHANGES - conservative blocking
                # Check both lowercase and capitalized variants
                série = params.get('série') or params.get('Série')
                collection = params.get('collection') or params.get('Collection')
                editeur = params.get('éditeur') or params.get('Éditeur')
                if série or collection or editeur:
                    self._logger.info(f"ENRICHMENT_SITE_SKIPPED | template={original_template.template_name} | reason=manually_curated_params_present")
                else:
                    # Check if titre already contains the site name to avoid duplication
                    # Normalize for comparison (case-insensitive, remove brackets and www)
                    site_clean = site_value.strip().lower().replace('www.', '').replace('[[', '').replace(']]', '')
                    titre = params.get('titre')
                    if titre:
                        titre_clean = titre.strip().lower().replace('www.', '').replace('[[', '').replace(']]', '')
                        if site_clean == titre_clean or site_clean in titre_clean or titre_clean in site_clean:
                            self._logger.info(f"ENRICHMENT_SITE_SKIPPED | template={original_template.template_name} | reason=titre_contains_site_name")
                        else:
                            params['site'] = site_value.strip()
                            self._logger.info(f"ENRICHMENT_SITE_ADDED | template={original_template.template_name} | site={site_value}")
                    else:
                        params['site'] = site_value.strip()
                        self._logger.info(f"ENRICHMENT_SITE_ADDED | template={original_template.template_name} | site={site_value}")
            else:
                self._logger.info(f"ENRICHMENT_SITE_SKIPPED | template={original_template.template_name} | reason=template_without_site_param")

        # Add consulté le parameter if missing and value provided
        if consulte_le_value and consulte_le_value.strip() and not current_consulte_le:
            # Check if template supports consulté le parameter
            # Normalize template name for comparison to handle case/spacing variations
            normalized_template_name = original_template.template_name.lower().replace('_', ' ')
            if normalized_template_name in self.TEMPLATES_SUPPORTING_CONSULTE_LE:
                params['consulté le'] = consulte_le_value.strip()
                self._logger.info(f"ENRICHMENT_CONSULTE_LE_ADDED | template={original_template.template_name} | consulte_le={consulte_le_value}")
            elif normalized_template_name == 'article':
                # Special case for {{article}}: only add consulté le if lire en ligne or url is present
                if params.get('lire en ligne') or params.get('url'):
                    params['consulté le'] = consulte_le_value.strip()
                    self._logger.info(f"ENRICHMENT_CONSULTE_LE_ADDED | template={original_template.template_name} | reason=article_with_online_access | consulté_le={consulte_le_value}")
                else:
                    self._logger.info(f"ENRICHMENT_CONSULTE_LE_SKIPPED | template={original_template.template_name} | reason=article_without_online_access")
            else:
                self._logger.info(f"ENRICHMENT_CONSULTE_LE_SKIPPED | template={original_template.template_name} | reason=template_not_in_whitelist")

        # Preserve original parameter order
        template_parts = [f'{{{{{original_template.template_name}']

        # Get original parameter order from the template's full_match
        original_param_order = []
        if original_template.full_match:
            template_content = original_template.full_match[2:-2]  # Remove {{ and }}
            segments = self._split_top_level(template_content)
            for segment in segments[1:]:  # Skip template name
                kv = self._PARAM_KV_RE.match(segment)
                if kv:
                    param_name = kv.group(1).strip()
                    original_param_order.append(param_name)

        # Add parameters in original order
        emitted = set()
        for param in original_param_order:
            if param in params:
                template_parts.append(f'|{param}={params[param]}')
                emitted.add(param)

        # Add any new parameters that weren't in original
        for param, value in params.items():
            if param not in emitted:
                template_parts.append(f'|{param}={value}')

        template_parts.append('}}')
        new_template = ''.join(template_parts)

        self._logger.info(
            f"GENERATED_ENRICHED_TEMPLATE | template={original_template.template_name} | "
            f"site_added={site_value is not None and not current_site} | "
            f"consulte_le_added={consulte_le_value is not None and not current_consulte_le}"
        )

        return new_template

    def add_brise_le_parameter(
        self,
        original_template: ReferenceTemplate,
        brise_le_date: str,
    ) -> str:
        """
        Add a brisé le parameter to an existing template, preserving all other parameters.

        This method is specifically for DeadLinkAnalyzer to mark a dead link as broken
        when a valid archive already exists.

        Args:
            original_template: Original parsed template
            brise_le_date: Date string in YYYY-MM-DD format for the brisé le parameter

        Returns:
            New template string with brisé le parameter added.
            Returns original template unchanged if brisé le is already present.

        Raises:
            ValueError: if original_template is None.
        """
        if original_template is None:
            raise ValueError("original_template is required")

        # Check if brisé le is already present (check all variants)
        brise_le_variants = ('brisé le', 'brise le', 'dead-url', 'deadurl', 'lien brisé')
        has_brise_le = False
        for variant in brise_le_variants:
            if variant in original_template.parameters:
                has_brise_le = True
                self._logger.info(f"BRISE_LE_ALREADY_PRESENT | template={original_template.template_name} | variant={variant}")
                break

        if has_brise_le:
            return original_template.full_match

        # Check if template supports brisé le parameter
        # Normalize template name for comparison
        normalized_template_name = original_template.template_name.lower().replace('_', ' ')
        if normalized_template_name in self.TEMPLATES_WITHOUT_ARCHIVE_PARAMS:
            self._logger.info(f"BRISE_LE_SKIPPED | template={original_template.template_name} | reason=template_without_archive_params")
            return original_template.full_match

        params = dict(original_template.parameters)  # shallow copy; safe, immutable source

        # Add brisé le parameter
        params['brisé le'] = brise_le_date
        self._logger.info(f"BRISE_LE_ADDED | template={original_template.template_name} | brise_le={brise_le_date}")

        # Preserve original parameter order
        template_parts = [f'{{{{{original_template.template_name}']

        # Get original parameter order from the template's full_match
        original_param_order = []
        if original_template.full_match:
            template_content = original_template.full_match[2:-2]  # Remove {{ and }}
            segments = self._split_top_level(template_content)
            for segment in segments[1:]:  # Skip template name
                kv = self._PARAM_KV_RE.match(segment)
                if kv:
                    param_name = kv.group(1).strip()
                    original_param_order.append(param_name)

        # Add parameters in original order
        emitted = set()
        for param in original_param_order:
            if param in params:
                template_parts.append(f'|{param}={params[param]}')
                emitted.add(param)

        # Add brisé le parameter (new parameter)
        template_parts.append(f'|brisé le={brise_le_date}')

        template_parts.append('}}')
        new_template = ''.join(template_parts)

        self._logger.info(
            f"GENERATED_BRISE_LE_TEMPLATE | template={original_template.template_name} | "
            f"brise_le={brise_le_date}"
        )

        return new_template

    # ------------------------------------------------------------------
    # Human-readable rendering
    # ------------------------------------------------------------------

    def render_archive_repair_prose(
        self,
        original_template: ReferenceTemplate,
        archive_url: str,
        archive_date: str,
        original_url: str,
        provider: Optional[str] = None,
        consulted_date: Optional[str] = None,
        assume_patch_deployed: bool = False,
    ) -> str:
        """
        Render a human-readable French citation sentence for a repaired
        dead link, e.g.:

        Titre, « Texte du lien » [archive du 1er janvier 2020],
        sur original-site.com via Internet Archive, 5 janvier 2015
        (consulté le 25 juillet 2026)

        - The title (if present) is quoted with French guillemets « ».
        - The link text points at the archive URL when `assume_patch_deployed`
          is True and the template supports promoting the archive as the
          main link; otherwise the link text points at the original URL and
          the archive is only referenced via "[archive du ...]".
        - "archive du <date>" always uses the *archive* date, never the
          publication date.
        - "sur <site> via <provider>" uses the resolved provider name.
        - Publication date (`date`/`année`) and "consulté le" are appended
          when available.

        Args:
            original_template: Parsed template (for titre/date/site/etc.)
            archive_url: Archive URL
            archive_date: Archive date from provider (YYYYMMDDHHMMSS or YYYY-MM-DD)
            original_url: Original dead URL
            provider: Raw archive provider identifier (e.g. 'WaybackMachine')
            consulted_date: Consultation date (YYYY-MM-DD); defaults to today (UTC)
            assume_patch_deployed: If True and the template supports it, the
                link text points to the archive URL instead of the original.

        Returns:
            A single formatted prose sentence (str).

        Raises:
            ValueError: if required inputs are missing/invalid.
        """
        if original_template is None:
            raise ValueError("original_template is required")
        if not archive_url or not archive_url.strip():
            raise ValueError("archive_url must be a non-empty string")
        if not original_url or not original_url.strip():
            raise ValueError("original_url must be a non-empty string")

        archive_url = archive_url.strip()
        original_url = original_url.strip()
        params = original_template.parameters

        # Normalize template name for comparison to handle case/spacing variations
        normalized_template_name = original_template.template_name.lower().replace('_', ' ')
        can_promote_archive = (
            assume_patch_deployed
            and normalized_template_name in self.TEMPLATES_SUPPORTING_ARCHIVE_AS_MAIN_LINK
        )
        link_target = archive_url if can_promote_archive else original_url

        titre = params.get('titre', '').strip()
        link_label = titre if titre else link_target

        # First segment: "Titre, « [lien](cible) »" or just "« [lien](cible) »"
        if titre:
            head = f'{titre}, « [{link_label}]({link_target}) »'
        else:
            head = f'« [{link_label}]({link_target}) »'

        # Archive marker glues directly onto the head with a space, no comma
        # before it: '... » [archive du 1er janvier 2020], sur ...'
        formatted_archive_date = self._format_archive_date(archive_date)
        archive_date_prose = self._format_date_prose(formatted_archive_date)
        archive_marker = f'[archive du {archive_date_prose}]' if archive_date_prose else '[archive du date inconnue]'
        head = f'{head} {archive_marker}'

        trailing: List[str] = []

        # Extract site name, handling cases where site parameter contains a URL instead of a name
        raw_site = params.get('site') or params.get('website')
        
        # Check if site parameter already contains a wikilink format like [www.multiple.be]
        # If so, don't add "sur <site>" in trailing section to avoid duplication
        site_is_wikilink = False
        if raw_site and ('[' in raw_site and ']' in raw_site):
            site_is_wikilink = True
            self._logger.debug(f"Site parameter '{raw_site}' already contains wikilink format, skipping 'sur <site>'")
        
        if raw_site and ('://' in raw_site or raw_site.startswith('www.')):
            site = self._safe_extract_domain(raw_site)
        else:
            site = raw_site or self._safe_extract_domain(original_url)
        resolved_provider = self.PROVIDER_NAMES.get(provider, provider) if provider else None

        # Avoid duplication: if link_label already contains the site name (domain),
        # don't add "sur <site>" in trailing section
        # This prevents: "[www.multiple.be](...), sur multiple.be"
        site_in_link_label = False
        if not titre and site and not site_is_wikilink:  # Only check when titre is empty and site is not a wikilink
            # Check if the site name appears in the link label (case-insensitive)
            site_lower = site.lower().replace('www.', '')
            link_label_lower = link_label.lower().replace('www.', '').replace('https://', '').replace('http://', '')
            if site_lower in link_label_lower or link_label_lower in site_lower:
                site_in_link_label = True
                self._logger.debug(f"Site '{site}' already present in link label '{link_label}', skipping 'sur {site}'")

        if site and resolved_provider and not site_in_link_label and not site_is_wikilink:
            trailing.append(f'sur {site} via {resolved_provider}')
        elif site and not site_in_link_label and not site_is_wikilink:
            trailing.append(f'sur {site}')
        elif resolved_provider:
            trailing.append(f'via {resolved_provider}')

        pub_date_raw = params.get('date') or params.get('année') or params.get('year')
        pub_date_prose = self._format_date_prose(self._format_archive_date(pub_date_raw)) if pub_date_raw else None
        if pub_date_prose:
            trailing.append(pub_date_prose)

        if not consulted_date:
            consulted_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        consulted_prose = self._format_date_prose(consulted_date)
        if consulted_prose:
            trailing.append(f'(consulté le {consulted_prose})')

        if not trailing:
            return head
        return head + ', ' + ', '.join(trailing)

    def _format_date_prose(self, iso_date: Optional[str]) -> str:
        """
        Convert a YYYY-MM-DD date into French prose form, e.g.
        '2020-01-01' -> '1er janvier 2020', '2020-01-05' -> '5 janvier 2020'.

        Falls back to returning the input unchanged if it isn't a clean
        YYYY-MM-DD string (e.g. year-only dates like '2015').
        """
        if not iso_date:
            return ""

        match = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', iso_date.strip())
        if not match:
            # Year-only or unparseable: return as-is (still useful prose).
            return iso_date.strip()

        year, month, day = match.groups()
        month_idx = int(month)
        if not (1 <= month_idx <= 12):
            return iso_date.strip()

        day_int = int(day)
        day_str = '1er' if day_int == 1 else str(day_int)
        month_name = self._FRENCH_MONTHS[month_idx]

        return f'{day_str} {month_name} {year}'

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def should_use_archive_template(self, content: str, url: str, position: int) -> bool:
        """
        Determine if archive template format should be used, i.e. whether
        the URL at `position` is part of a recognized reference template.

        CHANGED: now also requires is_supported=True. Previously a
        template whose name was recognized as present but not in
        KNOWN_TEMPLATE_NAMES (is_supported=False) still made this return
        True, diverging from DeadLinkAnalyzer's own explicit is_supported
        check on the same underlying data. This aligns the two.
        """
        template = self.find_reference_template(content, url, position)
        return template is not None and template.is_supported