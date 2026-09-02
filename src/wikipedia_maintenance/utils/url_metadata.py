"""
URL Metadata Extraction Utilities.

This module provides pure functions for extracting metadata from URLs,
such as site names and titles. These functions have no network dependencies
and no instance state, making them highly reusable and testable.

Responsibilities:
- Extract site names from URLs for Wikipedia template parameters
- Extract titles from URL paths for template parameters
- Clean and normalize extracted metadata

Design Principles:
- Pure functions (URL -> metadata)
- No network calls
- No instance state
- Conservative extraction (prefer simple, accurate over complex, risky)
- Single source of truth for host normalization, shared with url_extractor
"""

import logging
from typing import Final, Optional
from urllib.parse import urlparse, unquote

from .url_extraction import _normalize_host

logger = logging.getLogger(__name__)

# Shared extension list used by both extract_title() and clean_filename().
# Centralized so the two never silently drift apart.
_KNOWN_FILE_EXTENSIONS: Final[tuple] = (
    '.html', '.htm', '.php', '.asp', '.aspx', '.jsp', '.xhtml', '.pdf', '.doc', '.docx',
)

_MIN_TITLE_LENGTH: Final[int] = 3


def _strip_known_extension(text: str) -> str:
    """Remove a single trailing known file extension, if present (case-insensitive)."""
    lowered = text.lower()
    for ext in _KNOWN_FILE_EXTENSIONS:
        if lowered.endswith(ext):
            return text[:-len(ext)]
    return text


def _normalize_candidate_title(raw: str) -> Optional[str]:
    """
    Shared normalization: decode, strip extension/query/fragment remnants,
    replace separators with spaces, trim, and title-case the first letter.
    Returns None if the result is too short or purely numeric (looks like an ID).

    Callers must pass a single path segment (or filename); this does not
    itself split on '/'. Query strings / fragments are stripped defensively
    even though urlparse-based callers should already have removed them.
    """
    if not raw:
        return None

    title = unquote(raw)
    title = _strip_known_extension(title)

    # Defensive: query/fragment should already be split off by urlparse,
    # but keep this in case a caller passes a raw path segment directly.
    title = title.split('?', 1)[0].split('#', 1)[0]

    title = title.replace('_', ' ').replace('-', ' ').strip()

    if not title:
        return None

    title = title[0].upper() + title[1:]

    if len(title) < _MIN_TITLE_LENGTH or title.isdigit():
        return None

    return title


class UrlMetadataExtractor:
    """
    Utility class for extracting metadata from URLs.

    All methods are pure functions (static, side-effect-free aside from
    logging) that can be used independently without requiring network
    access or instance state.
    """

    @staticmethod
    def extract_site_name(url: str) -> Optional[str]:
        """
        Best-effort derivation of a human-facing "site" value from a URL's
        domain, for auto-filling the |site= parameter of a reference
        template when it was left empty.

        Deliberately conservative: strips only the leading "www." and a
        leading "m." (mobile subdomain), and returns the bare registrable
        host otherwise (e.g. "https://www.lemonde.fr/article/..." ->
        "lemonde.fr"). This mirrors the convention already used by many
        Wikipedia maintenance bots for |site= when no cleaner name is
        available, and avoids guessing a "pretty" title-cased name that
        could be wrong (e.g. acronyms, non-Latin scripts, multi-word
        outlet names).

        Host normalization is delegated to url_extractor._normalize_host,
        the single source of truth shared with UrlExtractor.extract_domain
        and UrlExtractor.is_syntactically_valid, so the rules can never
        drift apart between modules.

        Args:
            url: URL to extract site name from.

        Returns:
            Site name (lowercase host, e.g. "lemonde.fr"), or None if the
            URL cannot be parsed, is empty/not a string, or has no host.
        """
        if not url or not isinstance(url, str):
            return None

        try:
            netloc = urlparse(url).netloc
        except (ValueError, AttributeError) as e:
            # urlparse can raise ValueError on malformed input (e.g. bad IPv6 literal).
            logger.warning(f"SITE_EXTRACTION_FAILED | url={url!r} | error={e}")
            return None

        return _normalize_host(netloc)

    @staticmethod
    def extract_title(url: str) -> Optional[str]:
        """
        Best-effort derivation of a title from a URL's path for auto-filling
        the |titre= parameter of a reference template when it was left empty.

        Extracts the last meaningful segment of the URL path (after the last
        '/') and cleans it up by removing file extensions, query parameters,
        and common URL artifacts. This provides a reasonable fallback title
        when the actual page title is not available.

        If the last segment looks like an ID (too short or purely numeric),
        tries the second-to-last segment as a fallback.

        As a last resort, when no path segment yields a usable title, this
        returns None rather than fabricating one from the bare domain
        (e.g. "bbc.co.uk" capitalized to "Bbc.co.uk") — a raw hostname
        title-cased like a sentence reads as a bot artifact, not a real
        article title, and callers should treat a None title as "leave
        |titre= unset" rather than fill it with a low-quality guess.

        Args:
            url: URL to extract title from.

        Returns:
            Title, or None if the URL cannot be parsed, is empty/not a
            string, or has no meaningful path segment.
        """
        if not url or not isinstance(url, str):
            return None

        try:
            path = urlparse(url).path
        except (ValueError, AttributeError) as e:
            logger.warning(f"TITLE_EXTRACTION_FAILED | url={url!r} | error={e}")
            return None

        if not path or path == '/':
            return None

        segments = [seg for seg in path.split('/') if seg]
        if not segments:
            return None

        # Try the last segment first
        title = _normalize_candidate_title(segments[-1])
        if title:
            return title

        # If last segment looks like an ID, try the second-to-last segment
        if len(segments) >= 2:
            title = _normalize_candidate_title(segments[-2])
            if title:
                return title

        return None

    @staticmethod
    def clean_filename(filename: str) -> Optional[str]:
        """
        Clean a filename extracted from a URL by removing common artifacts
        and making it more suitable as a title.

        Expects a single path segment or bare filename (e.g. as produced by
        splitting a URL path on '/'), not a full URL — query strings and
        fragments are stripped defensively but the caller should not rely
        on that; use extract_title() to go straight from a full URL.

        Args:
            filename: Raw filename from URL path.

        Returns:
            Cleaned filename, or None if empty/not a string or too short
            after cleaning.
        """
        if not filename or not isinstance(filename, str):
            return None

        return _normalize_candidate_title(_strip_known_extension(filename))