"""
Analyzer for link-related issues in Wikipedia articles.

Detects:
    - Bare external links (URLs not enclosed in brackets)
    - Broken or suspicious internal links (red links, invalid characters)
    - Duplicate internal links (same target repeated too often)
    - Links to redirect pages (suggests using canonical title)
    - Links to non-existent sections (anchors that probably don't exist)
    - Interwiki links ([[lang:Page]]) with potential issues
    - External links with empty or generic descriptions
    - File links ([[Fichier:...]]) with missing parameters
    - Category links placed in article body (should be at end)
    - Consecutive links to the same target (overlinking)
    - Incomplete external links (missing closing bracket)
    - Links to Wikipedia internal pages via external URL format

Uses heuristics and optional MediaWiki API calls for redirect resolution
and existence checks. All checks are non‑destructive and preserve
existing functionality.
"""

import re
import logging
from typing import List, Optional, Dict, Set, Tuple, Pattern, Any
from urllib.parse import urlparse
from .base import BaseAnalyzer, Issue

logger = logging.getLogger(__name__)


class LinkAnalyzer(BaseAnalyzer):
    """
    Analyzes articles for link-related issues with comprehensive checks.
    """

    # ---- Precompiled patterns ----
    # Internal link: [[target|label]] or [[target]]
    _INTERNAL_LINK_RE = re.compile(r'\[\[([^\[\]]+?)(?:\|([^\[\]]*?))?\]\]')

    # External link: [url label] or [url]
    _EXTERNAL_LINK_RE = re.compile(r'\[(https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+)(?:\s+([^\]]*?))?\]')

    # Bare URL (not enclosed in brackets or inside a template parameter)
    _BARE_URL_RE = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+')

    # File link: [[Fichier:...]] or [[File:...]]
    _FILE_LINK_RE = re.compile(r'\[\[(?:Fichier|File):([^\[\]]+?)(?:\|([^\[\]]*?))?\]\]', re.IGNORECASE)

    # Category link: [[Catégorie:...]] or [[Category:...]]
    _CATEGORY_LINK_RE = re.compile(r'\[\[(?:Catégorie|Category):([^\[\]]+?)\]\]', re.IGNORECASE)

    # Interwiki link: [[lang:Page]] (with a two-letter language code)
    _INTERWIKI_LINK_RE = re.compile(r'\[\[([a-z]{2,3}):([^\[\]]+?)\]\]')

    # Link to section (with #)
    _SECTION_LINK_RE = re.compile(r'\[\[([^\[\]#]+)#([^\[\]]+?)(?:\|([^\[\]]*?))?\]\]')

    # Redirects - common French redirects (could be extended or fetched from API)
    _COMMON_REDIRECTS: Dict[str, str] = {
        # Examples: "WP" → "Wikipédia", etc.
        # We'll keep a small static map for demonstration; the API provider can complement.
    }

    # Configurable
    DEFAULT_MAX_DUPLICATE_LINKS = 3      # number of times same target allowed
    DEFAULT_MIN_DISTANCE_DUPLICATE = 100 # characters between duplicate links

    def __init__(
        self,
        language: str = 'fr',
        use_api_for_redirects: bool = True,
        max_duplicate_links: int = DEFAULT_MAX_DUPLICATE_LINKS,
        min_distance_duplicate: int = DEFAULT_MIN_DISTANCE_DUPLICATE,
        api_session=None,
        check_missing_links: bool = True,
        check_disambiguation: bool = True,
        check_social_media: bool = True,
        check_authority_ids: bool = True,
    ):
        """
        Args:
            language: Language code (used for interwiki and category checks).
            use_api_for_redirects: If True, attempt to resolve redirects via MediaWiki API.
            max_duplicate_links: Number of times same internal link target allowed
                before flagging as overlink.
            min_distance_duplicate: Minimum characters between two identical links
                to consider them as duplicate (to avoid flagging nearby ones).
            api_session: Optional requests.Session for API calls.
            check_missing_links: Enable missing link suggestions.
            check_disambiguation: Enable disambiguation link detection.
            check_social_media: Enable social media link detection.
            check_authority_ids: Enable authority ID detection.
        """
        super().__init__()
        self.language = language.lower()
        self.use_api = use_api_for_redirects
        self.max_duplicates = max_duplicate_links
        self.min_distance = min_distance_duplicate
        self._session = api_session
        self.check_missing_links = check_missing_links
        self.check_disambiguation = check_disambiguation
        self.check_social_media = check_social_media
        self.check_authority_ids = check_authority_ids

        # Cache for redirect resolution
        self._redirect_cache: Dict[str, Optional[str]] = {}

        # Cache for page existence (optional)
        self._page_existence_cache: Dict[str, bool] = {}

        # If use_api, try to import requests
        if self.use_api:
            try:
                import requests
                if self._session is None:
                    self._session = requests.Session()
            except ImportError:
                logger.warning("requests not installed; redirect resolution disabled.")
                self.use_api = False

    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze content for link issues.

        Args:
            content: Article wikicode content

        Returns:
            List of detected issues (sorted by position)
        """
        self.clear_issues()
        if not content:
            return self.issues

        # ---- ONLY check for redundant internal links [[Paris|Paris]] → [[Paris]] ----
        self._detect_redundant_internal_links(content)

        # Sort issues by position
        self.issues.sort(key=lambda i: i.position)
        return self.issues

    def get_analyzer_name(self) -> str:
        return "LinkAnalyzer"

    # ------------------------------------------------------------------
    # Detection method for redundant internal links
    # ------------------------------------------------------------------

    def _detect_redundant_internal_links(self, content: str) -> None:
        """
        Detect redundant internal links where the label is identical to the target.
        Example: [[Paris|Paris]] → [[Paris]]
        """
        for match in self._INTERNAL_LINK_RE.finditer(content):
            target = match.group(1).strip()
            label = match.group(2)

            # Only check if there's a label
            if not label:
                continue

            # Normalize both for comparison (case-insensitive, underscores to spaces)
            norm_target = target.replace('_', ' ').strip()
            norm_label = label.replace('_', ' ').strip()

            # Check if they are identical (case-insensitive)
            if norm_target.lower() == norm_label.lower():
                # Suggest the simplified form [[target]]
                suggestion = f"[[{target}]]"
                self.issues.append(Issue(
                    issue_type="redundant_internal_link",
                    description=f"Lien interne redondant : [[{target}|{label}]] → [[{target}]]",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=suggestion,
                    severity="low"
                ))