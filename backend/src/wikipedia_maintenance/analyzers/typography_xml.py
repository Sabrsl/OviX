"""
XML-based Typography Analyzer for Wikipedia articles.

This module uses the normalise_typo.xml file to apply typographic corrections
to Wikipedia articles. It provides a rule-based alternative to AI-based correction.

This is designed to work alongside the existing Gemini-based correction system
without breaking it - it's a separate analyzer that can be enabled/disabled independently.
"""

import re
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from .base import BaseAnalyzer, Issue
from wikipedia_maintenance.utils.typography_xml_analyzer_config import TypographyXMLAnalyzerConfig

logger = logging.getLogger(__name__)

# Regex timeout in seconds to prevent ReDoS attacks
REGEX_TIMEOUT = 5.0

# Regex matching raw URLs (used only inside this analyzer, NOT in BaseAnalyzer,
# so it never affects DeadLinkAnalyzer or any other analyzer that needs to see
# URLs). This prevents typography rules (case changes, punctuation fixes, etc.)
# from corrupting URLs found in wikitext (e.g. inside {{Lien web|url=...}}).
_URL_RE = re.compile(r'https?://[^\s\|\]\}<>]+')

# Matches the TARGET portion of a wiki link: [[Target]] or [[Target|Displayed text]].
# Only the target (before the first '|') is masked - the displayed text after '|'
# must remain editable by typo rules. This stops rules from inserting '|' or
# templates into the link target and corrupting the [[target|text]] structure,
# as seen with [[Bajirao ler|...]] being mangled into a 3-part link.
_WIKILINK_TARGET_RE = re.compile(r'\[\[([^\|\]]+)')

# Matches a template NAME: {{Name or {{Name|... . Only the name (before the
# first '|') is masked, so a rule cannot turn a template invocation into
# broken/nested syntax by editing its name.
_TEMPLATE_NAME_RE = re.compile(r'\{\{([^\|\}]+)')


def _build_url_mask(text: str) -> List[Tuple[int, int]]:
    """
    Build a local mask of (start, end) spans covering raw URLs, wiki-link
    targets, and template names in the text.

    This is intentionally separate from BaseAnalyzer.build_protected_mask:
    that shared mask is used by other analyzers (like DeadLinkAnalyzer) whose
    job is specifically to find URLs, so URLs must NOT be globally protected
    there. This local mask only affects XMLTypographyAnalyzer's own rule
    application, and only protects the structural parts of wikitext syntax
    (URL, link target, template name) - not the visible/displayed text.
    """
    spans: List[Tuple[int, int]] = []
    spans.extend((m.start(), m.end()) for m in _URL_RE.finditer(text))
    spans.extend((m.start(1), m.end(1)) for m in _WIKILINK_TARGET_RE.finditer(text))
    spans.extend((m.start(1), m.end(1)) for m in _TEMPLATE_NAME_RE.finditer(text))
    return spans


def _is_in_url(url_mask: List[Tuple[int, int]], pos: int) -> bool:
    """Check whether a given position falls inside a locally-masked URL span."""
    for start, end in url_mask:
        if start <= pos < end:
            return True
    return False


def _build_category_section_mask(text: str) -> List[Tuple[int, int]]:
    """
    Build a mask of category and portal section spans to exclude them from typo analysis.
    
    This function identifies lines containing [[Catégorie:, {{Portail|, {{DEFAULTSORT:, etc.
    and returns their (start, end) spans.
    """
    spans: List[Tuple[int, int]] = []
    # Match category and portal lines: [[Catégorie:, {{Portail|, {{DEFAULTSORT:, etc.
    category_line_re = re.compile(r'^(\[\[Catégorie:|{{Portail\||{{DEFAULTSORT:)', re.MULTILINE)
    
    for match in category_line_re.finditer(text):
        line_start = match.start()
        # Find the end of this line
        line_end = text.find('\n', line_start)
        if line_end == -1:
            line_end = len(text)
        spans.append((line_start, line_end))
    
    return spans


def _is_in_category_section(category_mask: List[Tuple[int, int]], pos: int) -> bool:
    """Check whether a given position falls inside a category section."""
    for start, end in category_mask:
        if start <= pos < end:
            return True
    return False


@dataclass
class TypoRule:
    """Represents a single typo correction rule from the XML file."""
    word: str
    find: str
    replace: str


def _replace_with_backreferences(replacement_pattern: str, match_obj: "re.Match") -> str:
    """
    Substitute $0..$N placeholders in a replacement pattern using groups
    from a regex match. Defined at module level so it is created once,
    not re-created on every rule/loop iteration.
    """
    result = replacement_pattern
    # Replace $0 with the full match
    result = result.replace('$0', match_obj.group(0))
    # Replace $n with the corresponding group from the match
    for i in range(1, len(match_obj.groups()) + 1):
        group_val = match_obj.group(i)
        result = result.replace(f'${i}', group_val if group_val is not None else '')
    return result


class XMLTypographyAnalyzer(BaseAnalyzer):
    """
    Typography analyzer that uses rules from normalise_typo.xml file.

    This analyzer reads typo correction rules from the XML file and applies them
    to article text. It's designed to be a deterministic, rule-based alternative
    to AI-based correction.
    """

    def __init__(self, xml_path: Optional[str] = None, enabled: bool = True,
                 max_corrections_per_article: int = 100,
                 ignore_protected_areas: bool = True,
                 case_sensitive: bool = False):
        """
        Initialize the XML typography analyzer.

        Args:
            xml_path: Path to the normalise_typo.xml file. If None, uses default path.
            enabled: If False, analyzer returns no issues (disabled state).
            max_corrections_per_article: Maximum corrections to apply per article.
            ignore_protected_areas: Whether to ignore protected areas (nowiki, comments, etc.).
            case_sensitive: Whether regex matching should be case-sensitive.
        """
        super().__init__()
        self.enabled = enabled
        self.max_corrections_per_article = max_corrections_per_article
        self.ignore_protected_areas = ignore_protected_areas
        self.case_sensitive = case_sensitive
        self.rules: List[TypoRule] = []

        if xml_path is None:
            # Default path relative to this file
            xml_path = Path(__file__).parent / "normalise_typo.xml"

        self.xml_path = Path(xml_path)

        # Single shared executor reused across all rule applications instead of
        # creating/destroying a ThreadPoolExecutor per rule (was a major perf issue).
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="xmltypo-regex")

        if self.enabled:
            self._load_rules()

    @classmethod
    def from_config(cls, config: Optional[TypographyXMLAnalyzerConfig] = None) -> "XMLTypographyAnalyzer":
        """
        Create analyzer instance from configuration.

        Args:
            config: TypographyXMLAnalyzerConfig instance. If None, loads from default config.

        Returns:
            XMLTypographyAnalyzer instance configured with settings from config.
        """
        if config is None:
            config = TypographyXMLAnalyzerConfig.load()

        return cls(
            xml_path=config.xml_rules_path,
            enabled=config.enabled,
            max_corrections_per_article=config.max_corrections_per_article,
            ignore_protected_areas=config.ignore_protected_areas,
            case_sensitive=config.case_sensitive
        )

    def get_analyzer_name(self) -> str:
        """Return a human-readable name for this analyzer."""
        return "XMLTypographyAnalyzer"

    def _load_rules(self) -> None:
        """Load typo rules from the XML file using a proper, strict XML parser."""
        try:
            if not self.xml_path.exists():
                logger.error(f"XML file not found: {self.xml_path}")
                self.rules = []
                return

            try:
                tree = ET.parse(self.xml_path)
            except ET.ParseError as e:
                # Malformed XML: fail loudly and load zero rules rather than
                # silently guessing. The file must be fixed at the source.
                logger.error(f"XML parsing error in {self.xml_path}: {e}")
                logger.error(
                    "The XML file has syntax errors (missing quotes, unclosed "
                    "tags, unescaped '<'/'>'/'&', etc.). Typo corrections are "
                    "disabled until the file is fixed."
                )
                self.rules = []
                return

            root = tree.getroot()

            valid_rules: List[TypoRule] = []
            skipped_count = 0

            for typo_elem in root.findall('Typo'):
                word = typo_elem.get('word')
                find = typo_elem.get('find')
                replace = typo_elem.get('replace')

                if not word or not find or replace is None:
                    logger.warning(
                        f"Skipping Typo element missing required attributes: "
                        f"word={word!r}, find={find!r}, replace={replace!r}"
                    )
                    skipped_count += 1
                    continue

                # Convert escape sequences from XML to actual characters
                # XML attributes contain literal \n as two characters, convert to real newline
                if find:
                    find = find.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
                if replace:
                    replace = replace.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')

                try:
                    # Test if the regex is valid before accepting the rule
                    re.compile(find)
                except re.error as e:
                    logger.debug(f"Skipping invalid regex pattern for '{word}': {find} ({e})")
                    skipped_count += 1
                    continue

                valid_rules.append(TypoRule(word=word, find=find, replace=replace))

            self.rules = valid_rules
            logger.info(
                f"Loaded {len(self.rules)} valid typo rules from {self.xml_path} "
                f"(skipped {skipped_count} invalid/incomplete patterns)"
            )

        except Exception as e:
            logger.error(f"Failed to load XML file: {e}")
            self.rules = []

    def _regex_flags(self) -> int:
        flags = re.MULTILINE
        if not self.case_sensitive:
            flags |= re.IGNORECASE
        return flags

    def _run_with_timeout(self, fn: Callable, *args, rule_word: str, **kwargs):
        """
        Run a potentially slow regex operation with a timeout using the shared
        executor. On timeout, logs a warning and returns None; the caller must
        treat None as "skip this rule". Note: CPython threads cannot be forcibly
        killed, so a timed-out worker may keep running in the background; using
        a single persistent worker (instead of one throwaway pool per rule)
        avoids unbounded thread accumulation and keeps this a bounded cost.
        """
        future = self._executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=REGEX_TIMEOUT)
        except FutureTimeoutError:
            logger.warning(f"Regex timeout for rule '{rule_word}': pattern too complex, skipping")
            return None

    def analyze(self, text: str) -> List[Issue]:
        """
        Analyze text for typography issues using XML rules.

        Args:
            text: The article text to analyze

        Returns:
            List of Issue objects describing typography issues found
        """
        if not self.enabled or not self.rules:
            return []

        issues: List[Issue] = []

        # Build protected area mask if needed (nowiki, pre, comments, etc. -
        # shared logic from BaseAnalyzer, used by all analyzers)
        protected_mask = None
        if self.ignore_protected_areas:
            protected_mask = self.build_protected_mask(text)

        # Build local URL mask - specific to this analyzer only. Prevents typo
        # rules (e.g. case normalization) from mangling raw URLs, without
        # affecting DeadLinkAnalyzer or other analyzers that rely on the
        # shared protected mask to actually find URLs.
        url_mask = _build_url_mask(text)

        # Build category section mask to exclude category sections from typo analysis
        category_mask = _build_category_section_mask(text)

        flags = self._regex_flags()

        for rule in self.rules:
            try:
                matches = self._run_with_timeout(
                    lambda: list(re.finditer(rule.find, text, flags)),
                    rule_word=rule.word
                )
                if matches is None:
                    continue

                for match in matches:
                    # Skip if in protected area (nowiki, comments, etc.)
                    if protected_mask and self.is_protected(protected_mask, match.start()):
                        continue

                    # Skip if inside a raw URL (local protection, this analyzer only)
                    if _is_in_url(url_mask, match.start()):
                        continue

                    # Skip if inside a category section
                    if _is_in_category_section(category_mask, match.start()):
                        continue

                    original_text = match.group(0)
                    corrected_text = _replace_with_backreferences(rule.replace, match)

                    if original_text != corrected_text:
                        issue = Issue(
                            issue_type='typo',
                            description=f"Typo correction: {rule.word}",
                            position=match.start(),
                            original_text=original_text,
                            suggested_text=corrected_text,
                            severity='low'
                        )
                        issues.append(issue)

            except re.error as e:
                logger.warning(f"Invalid regex in rule '{rule.word}': {e}")
                continue
            except Exception as e:
                logger.warning(f"Error applying rule '{rule.word}': {e}")
                continue

        return issues

    def apply_corrections(self, text: str) -> Tuple[str, int]:
        """
        Apply all typo corrections to the text.

        Args:
            text: The original text

        Returns:
            Tuple of (corrected_text, number_of_corrections)
        """
        if not self.enabled or not self.rules:
            return text, 0

        # Build protected area mask if needed
        protected_mask = None
        if self.ignore_protected_areas:
            protected_mask = self.build_protected_mask(text)

        # Build category section mask to exclude category sections from typo analysis
        category_mask = _build_category_section_mask(text)

        corrected_text = text
        corrections_count = 0

        flags = self._regex_flags()

        for rule in self.rules:
            # Stop if we've reached the maximum corrections limit
            if corrections_count >= self.max_corrections_per_article:
                logger.info(f"Reached max corrections limit ({self.max_corrections_per_article})")
                break

            try:
                # Apply replacements one at a time, recalculating matches after each replacement
                # This prevents position offset issues when text is modified by previous rules
                search_start = 0
                iterations = 0
                max_iterations = 1000  # Safety limit to prevent infinite loops
                while True:
                    iterations += 1
                    if iterations > max_iterations:
                        logger.warning(f"Rule '{rule.word}' exceeded max iterations ({max_iterations}), stopping to prevent infinite loop")
                        break

                    match = self._run_with_timeout(
                        lambda: re.search(rule.find, corrected_text[search_start:], flags),
                        rule_word=rule.word
                    )
                    if match is None:
                        break

                    # Adjust match position to be relative to full text
                    actual_match_start = search_start + match.start()
                    actual_match_end = search_start + match.end()

                    # Skip if in protected area
                    if protected_mask:
                        current_mask = self.build_protected_mask(corrected_text)
                        if self.is_protected(current_mask, actual_match_start):
                            # Skip this match and continue searching from after it
                            search_start = actual_match_end
                            continue

                    # Skip if inside a raw URL. Recomputed on each iteration since
                    # corrected_text mutates as replacements are applied, which
                    # shifts URL spans. This is local to this analyzer only.
                    current_url_mask = _build_url_mask(corrected_text)
                    if _is_in_url(current_url_mask, actual_match_start):
                        search_start = actual_match_end
                        continue

                    # Skip if inside a category section. Recomputed on each iteration
                    # since corrected_text mutates as replacements are applied.
                    current_category_mask = _build_category_section_mask(corrected_text)
                    if _is_in_category_section(current_category_mask, actual_match_start):
                        search_start = actual_match_end
                        continue

                    original = match.group(0)
                    replacement = _replace_with_backreferences(rule.replace, match)

                    if original == replacement:
                        # No change needed, skip this match and continue searching
                        search_start = actual_match_end
                        continue

                    # Replace this single occurrence
                    corrected_text = (
                        corrected_text[:actual_match_start] + 
                        replacement + 
                        corrected_text[actual_match_end:]
                    )
                    corrections_count += 1

                    # Continue searching from after the replacement
                    # This prevents infinite loops while finding all matches
                    search_start = actual_match_start + len(replacement)

                    # Stop if we've reached the maximum corrections limit
                    if corrections_count >= self.max_corrections_per_article:
                        logger.info(f"Reached max corrections limit ({self.max_corrections_per_article})")
                        break

            except re.error as e:
                logger.warning(f"Invalid regex in rule '{rule.word}': {e}")
                continue
            except Exception as e:
                logger.warning(f"Error applying rule '{rule.word}': {e}")
                continue

        logger.info(
            f"Applied {corrections_count} typo corrections using XML rules "
            f"(limit: {self.max_corrections_per_article})"
        )
        return corrected_text, corrections_count

    def reload_rules(self) -> None:
        """Reload rules from the XML file (useful for dynamic updates)."""
        self.rules = []
        if self.enabled:
            self._load_rules()

    def close(self) -> None:
        """Release the shared regex worker thread pool."""
        self._executor.shutdown(wait=False)

    def __del__(self):
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass