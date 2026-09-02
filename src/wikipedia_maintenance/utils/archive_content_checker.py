"""
Archive Content Checker - Soft-404 Detection.

This module provides functionality to detect soft-404 pages in archive snapshots.
A Wayback snapshot can return HTTP 200 (checked via HEAD upstream) while the stored body
is itself an already-dead "page not found" page — a soft-404 that was already broken at
capture time. A HEAD request has no body, so the HTTP-status check alone cannot see this;
a small GET + keyword check is the only way to catch it without a full content-diff pipeline.

Responsibilities:
- Detect soft-404 content in archive snapshots
- Provide safety net for archive-fallback repairs
- Conservative approach to avoid false positives

Design Principles:
- Conservative: false negatives expected, blocks only obvious cases
- Small GET requests (20KB limit) to minimize bandwidth
- Multi-language markers (FR + EN) for international coverage
"""

import logging
import ssl
import urllib.request
from typing import Final, List

logger = logging.getLogger(__name__)

_READ_LIMIT_BYTES: Final[int] = 20_000
_DEFAULT_TIMEOUT: Final[int] = 10
_USER_AGENT: Final[str] = 'WikipediaMaintenanceTool/1.0 (Archive Content Check)'


class ArchiveSoftDeadChecker:
    """
    Checker for detecting soft-404 content in archive snapshots.

    This is deliberately conservative and imperfect: false negatives are expected
    (some soft-404 pages won't match any marker). It exists to catch demonstrated
    failure cases, not to be a general soft-404 detector.
    """

    # Best-effort markers indicating a page body is a "not found" page
    # even though the HTTP status was 200 (soft-404). Not exhaustive by
    # design: this is a defense-in-depth check on top of the HTTP status
    # check, not a replacement for it. FR + EN covers the two languages
    # observed so far in practice.
    NOT_FOUND_MARKERS: Final[tuple] = (
        'page non-trouvée', 'page non trouvée', "n'est pas disponible à l'adresse",
        'contenu introuvable', 'page introuvable',
        'page not found', '404 not found', 'this page does not exist',
        "the page you requested could not be found",
    )

    def __init__(self, timeout: int = _DEFAULT_TIMEOUT):
        """
        Initialize the archive content checker.

        Args:
            timeout: Request timeout in seconds. Falls back to the default
                if a non-positive value is provided.
        """
        self.timeout = timeout if isinstance(timeout, (int, float)) and timeout > 0 else _DEFAULT_TIMEOUT
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def looks_dead(self, archive_url: str) -> bool:
        """
        Check if an archive URL contains soft-404 content.

        Args:
            archive_url: Archive URL to check.

        Returns:
            True if archive content matches not-found markers, False
            otherwise — including on empty/invalid input or any failure
            to fetch/decode the page (fail-safe: never blocks a repair
            due to a transient error, only due to positive evidence).
        """
        if not archive_url or not isinstance(archive_url, str):
            return False

        try:
            request = urllib.request.Request(
                archive_url,
                headers={'User-Agent': _USER_AGENT},
                method='GET',
            )
            context = ssl.create_default_context()
            with urllib.request.urlopen(request, timeout=self.timeout, context=context) as response:
                chunk = response.read(_READ_LIMIT_BYTES).decode('utf-8', errors='ignore').lower()

            return any(marker in chunk for marker in self.NOT_FOUND_MARKERS)

        except Exception as e:
            self._logger.warning(f"ARCHIVE_CONTENT_CHECK_FAILED | url={archive_url} | error={e}")
            return False  # Conservative: assume not dead if check fails

    def get_markers(self) -> List[str]:
        """
        Get the list of not-found markers used for detection.

        Returns:
            List of marker strings (a fresh copy; safe to mutate).
        """
        return list(self.NOT_FOUND_MARKERS)