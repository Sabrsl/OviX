"""
URL Extraction and Validation Utilities.

This module provides pure functions for URL detection, validation, and extraction
from wikitext content. These functions have no network dependencies and no instance state,
making them highly reusable and testable.

Responsibilities:
- URL pattern matching and extraction
- Syntactic validation of URLs
- Archive URL detection and original URL extraction
- Domain-based filtering

Design Principles:
- Pure functions (text -> text/bool)
- No network calls
- No instance state
- High reusability across analyzers
"""

import re
import logging
from typing import Final, List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_HOST_STRIP_PREFIXES: Final[tuple] = ('www.', 'm.')


def _normalize_host(netloc: str) -> Optional[str]:
    """
    Shared host normalization: drop userinfo/port, lowercase, strip
    leading www./m. — used by extract_domain(), is_archive_url(), and
    is_syntactically_valid()'s domain-exclusion check alike so none of
    them ever drift apart.
    """
    if not netloc:
        return None

    host = netloc.rsplit('@', 1)[-1].split(':', 1)[0].strip().lower()
    if not host:
        return None

    for prefix in _HOST_STRIP_PREFIXES:
        if host.startswith(prefix):
            host = host[len(prefix):]
            break

    return host or None


class UrlExtractor:
    """
    Utility class for URL extraction and validation from wikitext.

    All methods are pure functions that can be used independently
    without requiring network access or instance state.
    """

    # Whitelist of valid URL characters; wikitext delimiters |{}[] are
    # intentionally excluded so a URL match stops before them instead of
    # swallowing trailing template syntax (e.g. "url|consulté le=..." or
    # "[url texte]").
    # Extended to include Unicode characters beyond \uFFFF for better international support
    URL_PATTERN: Final = re.compile(
        r'https?://[a-zA-Z0-9\-._~:/?#@!$&\'()*+,;=%\u0080-\U0010FFFF]+', re.IGNORECASE
    )

    # Regex to extract original URL from archive URLs like:
    # https://web.archive.org/web/20200101/https://example.com/page
    # https://web.archive.org/web/20200101id_/https://example.com/page (with id_ suffix)
    # Works directly on the raw string and never invokes urlparse on the
    # embedded URL, so query strings and fragments are preserved exactly
    # as written.
    _ARCHIVE_ORIGINAL_RE: Final = re.compile(r'/web/\d+[^/]*/(https?://.+)$')
    
    # Regex for arquivo.pt: https://arquivo.pt/wayback/20200101/https://example.com/page
    _ARQUIVO_ORIGINAL_RE: Final = re.compile(r'/wayback/\d+/(https?://.+)$')
    
    # Regex for archive.today: https://archive.today/https://example.com/page
    _ARCHIVE_TODAY_ORIGINAL_RE: Final = re.compile(r'archive\.today/(https?://.+)$')
    
    # Regex for archive.is: https://archive.is/https://example.com/page
    _ARCHIVE_IS_ORIGINAL_RE: Final = re.compile(r'archive\.is/(https?://.+)$')

    _INVALID_PERCENT_RE: Final = re.compile(r'%(?![0-9A-Fa-f]{2})')

    ARCHIVE_DOMAINS: Final[frozenset] = frozenset({
        'web.archive.org',
        'archive.org',
        'webcache.googleusercontent.com',
        'arquivo.pt',
        'archive.today',
        'archive.is',
    })

    @staticmethod
    def is_syntactically_valid(url: str, excluded_domains: Optional[Set[str]] = None) -> bool:
        """
        Check if URL is syntactically valid before attempting network requests.

        Args:
            url: URL to validate.
            excluded_domains: Set of domains to exclude (e.g., academic sites).
                Matching is by exact host or subdomain (via _normalize_host),
                not substring — "nature.com" will not match
                "badnature.com.evil.tld".

        Returns:
            True if URL is syntactically valid, False otherwise (including
            for empty/non-string input).
        """
        if not url or not isinstance(url, str):
            return False

        if excluded_domains is None:
            excluded_domains = set()

        if any(ch in url for ch in ('|', '{', '}', '[', ']')):
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=contains_template_delimiters")
            return False

        if url.endswith('|') or url.endswith('='):
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=ends_with_delimiter")
            return False

        if url.endswith('%'):
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=ends_with_percent")
            return False

        if UrlExtractor._INVALID_PERCENT_RE.search(url):
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=invalid_percent_encoding")
            return False

        if not url.startswith(('http://', 'https://')):
            logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=invalid_scheme")
            return False

        # Exclude specified domains (e.g., academic sites). Matched against
        # the normalized host — exact match or subdomain — never a raw
        # substring, so "nature.com" cannot accidentally exclude
        # "badnature.com.evil.tld" or match inside a path/query string.
        if excluded_domains:
            try:
                netloc = urlparse(url).netloc
            except ValueError as e:
                logger.warning(f"URL_SYNTAX_INVALID | url={url} | reason=unparseable ({e})")
                return False

            url_domain = _normalize_host(netloc)
            if url_domain:
                for excluded in excluded_domains:
                    excluded_norm = _normalize_host(excluded) or (excluded or '').strip().lower()
                    if not excluded_norm:
                        continue
                    if url_domain == excluded_norm or url_domain.endswith(f".{excluded_norm}"):
                        logger.info(f"URL_EXCLUDED | url={url} | reason=excluded_domain_{excluded}")
                        return False

        return True

    @staticmethod
    def is_archive_url(url: str) -> bool:
        """
        Check if a URL is an archive URL.

        Args:
            url: URL to check.

        Returns:
            True if URL is from an archive service, False otherwise
            (including for empty/non-string/unparseable input).
        """
        if not url or not isinstance(url, str):
            return False

        try:
            netloc = urlparse(url).netloc.lower()
        except ValueError as e:
            logger.warning(f"ARCHIVE_CHECK_FAILED | url={url} | error={e}")
            return False

        return netloc in UrlExtractor.ARCHIVE_DOMAINS

    @staticmethod
    def extract_original_from_archive(archive_url: str) -> Optional[str]:
        """
        Extract the original URL from an archive URL, preserving any
        query string or fragment on the embedded original URL.

        Args:
            archive_url: Archive URL to extract original URL from.

        Returns:
            Original URL if found, None otherwise.
        """
        if not archive_url or not isinstance(archive_url, str):
            return None

        # Try different archive patterns
        if 'web.archive.org' in archive_url.lower() or 'archive.org' in archive_url.lower():
            match = UrlExtractor._ARCHIVE_ORIGINAL_RE.search(archive_url)
            if match:
                return match.group(1)
        
        if 'arquivo.pt' in archive_url.lower():
            match = UrlExtractor._ARQUIVO_ORIGINAL_RE.search(archive_url)
            if match:
                return match.group(1)
        
        if 'archive.today' in archive_url.lower():
            match = UrlExtractor._ARCHIVE_TODAY_ORIGINAL_RE.search(archive_url)
            if match:
                return match.group(1)
        
        if 'archive.is' in archive_url.lower():
            match = UrlExtractor._ARCHIVE_IS_ORIGINAL_RE.search(archive_url)
            if match:
                return match.group(1)
        
        return None

    @staticmethod
    def find_urls_in_content(content: str) -> List[Tuple[str, int, int]]:
        """
        Find all URLs in wikitext content using the URL_PATTERN.

        Args:
            content: Wikitext content to search.

        Returns:
            List of (url, start_position, end_position) tuples. Empty list
            for empty/non-string input.
        """
        if not content or not isinstance(content, str):
            return []

        return [
            (match.group(0), match.start(), match.end())
            for match in UrlExtractor.URL_PATTERN.finditer(content)
        ]

    @staticmethod
    def extract_domain(url: str) -> Optional[str]:
        """
        Extract domain from URL, removing www. and m. prefixes.

        Args:
            url: URL to extract domain from.

        Returns:
            Domain name or None if URL cannot be parsed, is empty/not a
            string, or has no host.
        """
        if not url or not isinstance(url, str):
            return None

        try:
            netloc = urlparse(url).netloc
        except ValueError as e:
            logger.warning(f"DOMAIN_EXTRACTION_FAILED | url={url} | error={e}")
            return None

        return _normalize_host(netloc)