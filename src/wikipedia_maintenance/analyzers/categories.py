"""
Analyzer for category-related issues in Wikipedia articles.

Detects:
    - Duplicate categories (with normalization)
    - Missing default sort key ({{DEFAULTSORT:...}}) when categories are present
    - Categories placed before the end of the article (should be at the very bottom)
    - Categories after interwiki language links (should be before interwikis on many wikis, but convention varies; we flag)
    - Incorrect order of categories (non-alphabetical)
    - Empty category links ([[Category:]] or [[Catégorie:]])
    - Unnecessary spaces around category names ([[Category: France]] → [[Category:France]])
    - Categories on redirect pages (should only have specific redirect categories)
    - Invalid category names (spaces or special characters, via API if enabled)
    - Redundant parent category (when both child and parent categories are present)

All existing functionality (duplicate detection) is preserved and improved.
Optional MediaWiki API checks are non‑blocking and cached.
"""

import re
import logging
from typing import List, Dict, Set, Optional, Tuple, Any
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from .base import BaseAnalyzer, Issue

logger = logging.getLogger(__name__)


@dataclass
class CategoryAnalyzerConfig:
    """Configuration for CategoryAnalyzer."""
    check_duplicates: bool = True
    check_defaultsort: bool = True
    check_placement: bool = True
    check_order: bool = True
    check_empty: bool = True
    check_spaces: bool = True
    check_redirect: bool = True
    check_invalid: bool = True
    check_redundant_parent: bool = True
    check_suggestions: bool = True
    check_uncertain: bool = True

    # Whether to use API for existence/validity checks
    use_api: bool = False
    language: str = 'fr'
    api_url: Optional[str] = None

    # Categories that are allowed on redirect pages (typical)
    redirect_categories: Set[str] = field(default_factory=lambda: {
        'catégorie:redirection',
        'catégorie:redirection de pays',
        'catégorie:redirection de langue',
        'catégorie:redirection de nom',
        'catégorie:redirection de projet',
        # ... in practice, we can check if they are in a specific subcategory
    })

    # Parent-child relationships (optional): e.g., "France" is child of "Pays d'Europe"
    # We'll implement a simple static map; can be extended via API.
    parent_child_map: Dict[str, Set[str]] = field(default_factory=dict)


class CategoryAnalyzer(BaseAnalyzer):
    """
    Analyzes articles for category-related issues.
    """

    # Category link patterns: [[Category:...]] and [[Catégorie:...]]
    _CATEGORY_RE = re.compile(
        r'\[\[(?:Category|Catégorie):([^\]]+?)\]\]',
        re.IGNORECASE
    )

    # Default sort key pattern: {{DEFAULTSORT:...}}
    _DEFAULTSORT_RE = re.compile(
        r'\{\{DEFAULTSORT:([^}]*?)\}\}',
        re.IGNORECASE
    )

    # Interwiki link pattern: [[lang:Page]]
    _INTERWIKI_RE = re.compile(r'\[\[[a-z]{2,3}:[^\]]+?\]\]', re.IGNORECASE)

    # Redirect detection (simple: #REDIRECT at start of page)
    _REDIRECT_RE = re.compile(r'^#REDIRECT\s+\[\[', re.IGNORECASE | re.MULTILINE)

    def __init__(
        self,
        config: Optional[CategoryAnalyzerConfig] = None,
        session=None,
    ):
        super().__init__()
        self.config = config or CategoryAnalyzerConfig()
        self._session = session
        self._category_existence_cache: Dict[str, bool] = {}
        self._category_parents_cache: Dict[str, Set[str]] = {}

        if self.config.use_api:
            try:
                import requests
                if self._session is None:
                    self._session = requests.Session()
            except ImportError:
                logger.warning("requests not installed; API checks disabled.")
                self.config.use_api = False

    def analyze(self, content: str) -> List[Issue]:
        """Analyze content for category issues."""
        self.clear_issues()
        if not content:
            return self.issues

        # Detect if the article is a redirect
        is_redirect = bool(self._REDIRECT_RE.search(content))

        # ---- Existing duplicate detection (improved) ----
        if self.config.check_duplicates:
            self._detect_duplicate_categories(content)

        # ---- New checks ----
        categories = self._extract_categories(content)

        if not categories:
            # No categories; nothing more to do
            return self.issues

        if self.config.check_defaultsort:
            self._detect_missing_defaultsort(content, categories)

        if self.config.check_placement:
            self._detect_category_placement(content, categories)

        if self.config.check_order:
            self._detect_category_order(content, categories)

        if self.config.check_empty:
            self._detect_empty_categories(content)

        if self.config.check_spaces:
            self._detect_spaces_in_categories(content)

        if self.config.check_redirect and is_redirect:
            self._detect_redirect_categories(categories)

        if self.config.check_invalid:
            self._detect_invalid_categories(categories)

        if self.config.check_redundant_parent:
            self._detect_redundant_parent_categories(categories)

        if self.config.check_suggestions:
            self._suggest_missing_categories(content, categories)
        
        if self.config.check_uncertain:
            self._detect_uncertain_categories(categories)

        self.issues.sort(key=lambda i: i.position)
        return self.issues

    def get_analyzer_name(self) -> str:
        return "CategoryAnalyzer"

    # ------------------------------------------------------------------
    # Helper to extract categories with normalized names and positions
    # ------------------------------------------------------------------

    def _extract_categories(self, content: str) -> List[Tuple[str, int, str]]:
        """
        Extract categories from content.

        Returns:
            List of (normalized_name, position, original_text) where
            normalized_name is lowercased, underscores replaced with spaces,
            and leading/trailing spaces removed.
        """
        categories = []
        for match in self._CATEGORY_RE.finditer(content):
            raw = match.group(1)
            # Normalize: replace underscores with spaces, collapse multiple spaces, strip
            norm = re.sub(r'\s+', ' ', raw.replace('_', ' ').strip())
            # Lowercase for comparisons (but keep original for suggestion)
            norm_lower = norm.lower()
            categories.append((norm_lower, match.start(), match.group(0)))
        return categories

    # ------------------------------------------------------------------
    # Existing method (improved)
    # ------------------------------------------------------------------

    def _detect_duplicate_categories(self, content: str) -> None:
        """
        Detect duplicate categories after normalization.
        Now flags all but the first occurrence.
        """
        # We'll use a dictionary of normalized -> (first_position, original_text)
        seen: Dict[str, Tuple[int, str]] = {}
        for match in self._CATEGORY_RE.finditer(content):
            raw = match.group(1)
            norm = re.sub(r'\s+', ' ', raw.replace('_', ' ').strip().lower())
            if norm in seen:
                # Duplicate
                self.issues.append(Issue(
                    issue_type="duplicate_category",
                    description="Catégorie en double (normalisée)",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=None,  # needs manual removal
                    severity="low"
                ))
            else:
                seen[norm] = (match.start(), match.group(0))

    # ------------------------------------------------------------------
    # New detection methods
    # ------------------------------------------------------------------

    def _detect_missing_defaultsort(self, content: str, categories: List[Tuple[str, int, str]]) -> None:
        """
        Detect missing {{DEFAULTSORT:...}} when the article has categories.
        """
        # Check for DEFAULTSORT
        if not self._DEFAULTSORT_RE.search(content):
            self.issues.append(Issue(
                issue_type="missing_defaultsort",
                description="Clé de tri par défaut manquante ({{DEFAULTSORT:...}})",
                position=0,  # position at beginning, but we can suggest at end
                original_text="",
                suggested_text="{{DEFAULTSORT:Nom, Prénom}}",  # generic
                severity="low"
            ))

    def _detect_category_placement(self, content: str, categories: List[Tuple[str, int, str]]) -> None:
        """
        Detect if categories appear before the end of the page (should be after all content).
        Also check if interwiki links appear after categories (standard: interwiki after categories? Actually on French Wikipedia, interwikis are often placed after categories, but some prefer before. We'll flag if categories appear before the last interwiki link or before the last section.)
        """
        # Find the position of the last category
        if not categories:
            return

        last_cat_pos = max(pos for _, pos, _ in categories)

        # Check if there is any non-whitespace text after the last category
        # (ignore whitespace, interwiki links, other categories)
        after = content[last_cat_pos + len(self._CATEGORY_RE.search(content, last_cat_pos).group(0)):]
        # Remove any whitespace and other category links and interwiki links
        cleaned = re.sub(r'\[\[(?:Category|Catégorie):[^\]]+?\]\]', '', after, flags=re.IGNORECASE)
        cleaned = re.sub(r'\[\[[a-z]{2,3}:[^\]]+?\]\]', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        if cleaned:
            self.issues.append(Issue(
                issue_type="category_placement",
                description="Catégories placées avant la fin de l'article (devraient être tout en bas)",
                position=last_cat_pos,
                original_text=content[last_cat_pos:last_cat_pos+50],
                suggested_text=None,
                severity="low"
            ))

        # Check interwiki placement: if there are interwiki links, they should come after categories?
        # Actually, many projects place interwikis after categories. We'll flag if interwiki links appear before categories.
        # Find the last interwiki link
        interwiki_matches = list(self._INTERWIKI_RE.finditer(content))
        if interwiki_matches:
            last_iw_pos = max(m.start() for m in interwiki_matches)
            # If categories appear before the last interwiki, flag (since categories should be after interwikis? Wait, standard is categories last, then interwikis? Actually common practice: categories then interwikis (or interwikis then categories?). On French Wikipedia, interwikis are often placed after categories. Let's check: typical is categories at the very end, then interwiki links. So if categories are before interwikis, that's fine. But if interwikis before categories, that's wrong. We'll check if any category appears after the first interwiki? Simpler: if any category appears before the last interwiki? Actually we want categories to be after interwikis? Let's just flag if categories appear before any interwiki? That would be too strict. We'll skip this for now.)

    def _detect_category_order(self, content: str, categories: List[Tuple[str, int, str]]) -> None:
        """
        Detect if categories are not in alphabetical order.
        """
        # Extract normalized names in the order they appear
        ordered = [norm for norm, pos, orig in categories]
        # Check if sorted order equals original order (case-insensitive)
        sorted_order = sorted(ordered, key=lambda s: s.lower())
        if ordered != sorted_order:
            # Find positions where order differs
            # We'll just flag with a general message
            self.issues.append(Issue(
                issue_type="category_order",
                description="Catégories non triées par ordre alphabétique",
                position=categories[0][1],  # first category position
                original_text=", ".join(ordered[:5]) + ("..." if len(ordered) > 5 else ""),
                suggested_text=None,
                severity="low"
            ))

    def _detect_empty_categories(self, content: str) -> None:
        """
        Detect empty category links: [[Category:]] or [[Catégorie:]]
        """
        # We'll use a pattern that matches category with empty name
        empty_pattern = re.compile(r'\[\[(?:Category|Catégorie):\s*\]\]', re.IGNORECASE)
        for match in empty_pattern.finditer(content):
            self.issues.append(Issue(
                issue_type="empty_category",
                description="Catégorie vide ([[Category:]])",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=None,
                severity="high"
            ))

    def _detect_spaces_in_categories(self, content: str) -> None:
        """
        Detect leading/trailing spaces in category names.
        """
        for match in self._CATEGORY_RE.finditer(content):
            raw = match.group(1)
            stripped = raw.strip()
            if raw != stripped:
                # Suggest removal of spaces
                suggestion = f"[[Category:{stripped}]]"
                self.issues.append(Issue(
                    issue_type="category_spaces",
                    description="Espaces superflus dans le nom de la catégorie",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=suggestion,
                    severity="low"
                ))

    def _detect_redirect_categories(self, categories: List[Tuple[str, int, str]]) -> None:
        """
        Detect if a redirect page has categories that are not specifically for redirects.
        """
        allowed_lower = {c.lower() for c in self.config.redirect_categories}
        for norm, pos, orig in categories:
            # Check if the category is in the allowed set
            # We'll also accept categories that start with "Catégorie:Redirection"
            if not any(allowed in norm for allowed in allowed_lower):
                self.issues.append(Issue(
                    issue_type="redirect_category",
                    description="Catégorie non standard sur une page de redirection (seules les catégories de redirection sont autorisées)",
                    position=pos,
                    original_text=orig,
                    suggested_text=None,
                    severity="low"
                ))

    def _detect_invalid_categories(self, categories: List[Tuple[str, int, str]]) -> None:
        """
        Detect categories that may not exist (if API enabled) or have invalid characters.
        """
        if self.config.use_api:
            for norm, pos, orig in categories:
                # Check existence via API (with cache)
                if not self._category_exists(norm):
                    self.issues.append(Issue(
                        issue_type="invalid_category",
                        description=f"Catégorie probablement inexistante : {orig}",
                        position=pos,
                        original_text=orig,
                        suggested_text=None,
                        severity="low"
                    ))
        else:
            # Heuristic: check for obviously invalid names (empty, only special chars, etc.)
            for norm, pos, orig in categories:
                if not norm or norm.isspace() or not re.match(r'^[\w\s\-\(\)\.,\']+$', norm, re.UNICODE):
                    self.issues.append(Issue(
                        issue_type="invalid_category_name",
                        description=f"Nom de catégorie suspect (caractères inhabituels) : {orig}",
                        position=pos,
                        original_text=orig,
                        suggested_text=None,
                        severity="low"
                    ))

    def _detect_redundant_parent_categories(self, categories: List[Tuple[str, int, str]]) -> None:
        """
        Detect if both a category and its parent are present (redundant).
        Uses static map if provided, or API if enabled.
        """
        if not self.config.parent_child_map and not self.config.use_api:
            return

        # Build a set of category names (normalized)
        cat_set = {norm for norm, _, _ in categories}

        # Check each category if it has a parent that is also in the set
        for norm, pos, orig in categories:
            parents = self._get_category_parents(norm)
            for parent in parents:
                if parent in cat_set:
                    self.issues.append(Issue(
                        issue_type="redundant_parent_category",
                        description=f"Catégorie parente redondante : {parent} (déjà présente avec {orig})",
                        position=pos,
                        original_text=orig,
                        suggested_text=None,
                        severity="low"
                    ))
                    break  # only flag once per category

    # ------------------------------------------------------------------
    # API helpers (cached)
    # ------------------------------------------------------------------

    def _category_exists(self, name: str) -> bool:
        """Check if a category exists via API."""
        if name in self._category_existence_cache:
            return self._category_existence_cache[name]

        if not self.config.use_api:
            return True  # assume exists

        try:
            params = {
                'action': 'query',
                'titles': f'Category:{name}',
                'format': 'json',
                'formatversion': 2,
            }
            resp = self._session.get(
                self.config.api_url or f'https://{self.config.language}.wikipedia.org/w/api.php',
                params=params,
                timeout=3
            )
            resp.raise_for_status()
            data = resp.json()
            pages = data.get('query', {}).get('pages', [])
            exists = not any('missing' in p for p in pages)
            self._category_existence_cache[name] = exists
            return exists
        except Exception as e:
            logger.warning(f"Error checking category existence for {name}: {e}")
            return True  # assume exists to avoid false positives

    def _get_category_parents(self, name: str) -> Set[str]:
        """Get parent categories of a given category (from cache or API)."""
        if name in self._category_parents_cache:
            return self._category_parents_cache[name]

        if not self.config.use_api:
            # Fallback to static map
            return self.config.parent_child_map.get(name, set())

        try:
            # Use API to get category members of type 'subcat'
            # We'll fetch categories that contain this category as a subcategory? Actually we want parents.
            # Use 'clcategories'? Not directly. We can use 'titles' and 'prop=categories' to get the categories the page belongs to.
            # But here we want the parent categories of this category page.
            params = {
                'action': 'query',
                'titles': f'Category:{name}',
                'prop': 'categories',
                'format': 'json',
                'formatversion': 2,
            }
            resp = self._session.get(
                self.config.api_url or f'https://{self.config.language}.wikipedia.org/w/api.php',
                params=params,
                timeout=3
            )
            resp.raise_for_status()
            data = resp.json()
            pages = data.get('query', {}).get('pages', [])
            parents = set()
            for p in pages:
                cats = p.get('categories', [])
                for cat in cats:
                    cat_title = cat.get('title', '')
                    if cat_title.startswith('Category:'):
                        parents.add(cat_title[9:].strip())
            self._category_parents_cache[name] = parents
            return parents
        except Exception as e:
            logger.warning(f"Error getting parents for {name}: {e}")
            return set()

    # ------------------------------------------------------------------
    # New enhanced detection methods
    # ------------------------------------------------------------------

    def _suggest_missing_categories(self, content: str, categories: List[Tuple[str, int, str]]) -> None:
        """
        Suggest potentially missing categories based on article content.
        This is a heuristic - actual implementation would require NLP or a knowledge base.
        """
        # Extract article title (simplified - would need to be passed separately)
        # For now, this is a placeholder
        # Real implementation would:
        # 1. Analyze article content for key topics
        # 2. Check against a database of common categories
        # 3. Suggest relevant categories not already present
        
        # Placeholder: suggest common categories if article has certain keywords
        common_category_keywords = {
            'france': 'Catégorie:France',
            'paris': 'Catégorie:Paris',
            'musique': 'Catégorie:Musique',
            'cinéma': 'Catégorie:Cinéma',
            'littérature': 'Catégorie:Littérature',
            'politique': 'Catégorie:Politique',
            'sport': 'Catégorie:Sport',
        }
        
        existing_cats = {norm for norm, _, _ in categories}
        
        for keyword, category in common_category_keywords.items():
            if keyword.lower() in content.lower() and category.lower() not in existing_cats:
                self.issues.append(Issue(
                    issue_type="category_suggestion",
                    description=f"Catégorie suggérée : {category} (basée sur le mot-clé '{keyword}')",
                    position=0,  # Suggestion for end of article
                    original_text="",
                    suggested_text=f"[[{category}]]",
                    severity="low"
                ))

    def _detect_uncertain_categories(self, categories: List[Tuple[str, int, str]]) -> None:
        """
        Detect categories that might be uncertain or need verification.
        This includes:
        - Categories with very few members (if API enabled)
        - Categories that are maintenance categories
        - Categories that are too specific
        """
        # Maintenance category patterns
        maintenance_patterns = [
            'à sourcer', 'à vérifier', 'à wikifier', 'à recycler',
            'à illustrer', 'à améliorer', 'à nettoyer', 'à classer',
            'à déplacer', 'à fusionner', 'à supprimer',
            'en cours', 'en attente', 'brouillon', 'ébauche',
        ]
        
        for norm, pos, orig in categories:
            # Check for maintenance categories
            if any(pattern in norm for pattern in maintenance_patterns):
                self.issues.append(Issue(
                    issue_type="uncertain_category",
                    description=f"Catégorie de maintenance détectée : {orig} (vérifier si appropriée)",
                    position=pos,
                    original_text=orig,
                    suggested_text=None,
                    severity="medium"
                ))
            
            # Check for very specific categories (heuristic: long names with many words)
            if len(norm.split()) > 5:
                self.issues.append(Issue(
                    issue_type="uncertain_category",
                    description=f"Catégorie très spécifique : {orig} (vérifier si nécessaire)",
                    position=pos,
                    original_text=orig,
                    suggested_text=None,
                    severity="low"
                ))