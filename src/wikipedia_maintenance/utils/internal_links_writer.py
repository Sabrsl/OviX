"""
Internal Links Writer - Archive Service Link Injection.

This module provides functionality to add internal links to archive services
in the "Voir aussi" section of Wikipedia articles. This is wikitext manipulation
(section search, insertion) completely independent of dead link detection/repair logic.

Responsibilities:
- Generate formatted internal links to archive services
- Add links to "Voir aussi" section
- Handle section creation if needed
- Group by provider to avoid duplicates

Design Principles:
- Pure wikitext manipulation (no network calls)
- Reusable by other analyzers
- Conservative section insertion
"""

import re
import logging
from typing import Dict, Final, List
from datetime import datetime

logger = logging.getLogger(__name__)

_MONTH_NAMES_FR: Final[tuple] = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
)

_VOIR_AUSSI_RE: Final = re.compile(r'==\s*[Vv]oir aussi\s*==')
_LIENS_EXTERNES_RE: Final = re.compile(r'==\s*[Ll]iens externes\s*==')


class InternalLinksWriter:
    """
    Writer for adding internal links to archive services in Wikipedia articles.

    Handles the "Voir aussi" section manipulation to add archive service links
    after dead link repairs.
    """

    # Map provider names to Wikipedia article names
    PROVIDER_ARTICLE_NAMES: Final[Dict[str, str]] = {
        'WaybackMachine': 'Internet Archive',
        'Archive.org': 'Internet Archive',
        'Arquivo.pt': 'Arquivo.pt',
        'Wikiwix': 'Wikiwix',
    }

    def __init__(self):
        """Initialize the internal links writer."""
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def generate_archive_internal_link(self, original_url: str, archive_url: str,
                                        archive_date: str, provider: str) -> str:
        """
        Generate an internal link to the archive service for the corrected link.

        Format: * [archive du 1er janvier 2020] sur [[Internet Archive]]

        Args:
            original_url: Original dead URL (currently unused in the output
                format, kept for signature stability / future use).
            archive_url: Archive URL (currently unused in the output format,
                kept for signature stability / future use).
            archive_date: Archive date (YYYY-MM-DD). Falls back to the raw
                value verbatim if it doesn't match this format.
            provider: Archive provider name (WaybackMachine, Arquivo.pt, etc.).
                Falls back to the raw provider name if unmapped.

        Returns:
            Formatted internal link string.
        """
        formatted_date = archive_date

        if archive_date:
            try:
                date_obj = datetime.strptime(archive_date, '%Y-%m-%d')
                day = date_obj.day
                day_str = f"{day}er" if day == 1 else str(day)
                month_str = _MONTH_NAMES_FR[date_obj.month - 1]
                formatted_date = f"{day_str} {month_str} {date_obj.year}"
            except (ValueError, IndexError):
                formatted_date = archive_date

        provider_article = self.PROVIDER_ARTICLE_NAMES.get(provider, provider or 'Unknown')

        return f"* [archive du {formatted_date}] sur [[{provider_article}]]"

    def add_archive_links(self, content: str, archive_repairs: List[Dict]) -> str:
        """
        Add internal links to archive services in the "Voir aussi" section.

        Args:
            content: Article content.
            archive_repairs: List of dicts with repair info (original_url,
                archive_url, archive_date, provider).

        Returns:
            Updated content with internal links added. Returns content
            unchanged if archive_repairs is empty, content is not a
            valid string, or every generated link is already present
            in the content (idempotent re-run).
        """
        if not archive_repairs or not content or not isinstance(content, str):
            return content

        # Group repairs by provider to avoid duplicates
        provider_links: Dict[str, str] = {}
        for repair in archive_repairs:
            if not isinstance(repair, dict):
                continue
            provider = repair.get('provider') or 'Unknown'
            if provider not in provider_links:
                provider_links[provider] = self.generate_archive_internal_link(
                    repair.get('original_url', ''),
                    repair.get('archive_url', ''),
                    repair.get('archive_date', ''),
                    provider,
                )

        if not provider_links:
            return content

        # CHANGED: guard against duplicate insertion when this method runs
        # more than once on the same article (retry, re-run, reprocessing
        # after a crash). Previously nothing checked whether a link was
        # already present, so a second pass could append a second, near-
        # identical "* [archive du ...] sur [[Internet Archive]]" line to
        # "Voir aussi" every time. Only lines not already verbatim present
        # in `content` are kept; if that empties the set, the content is
        # returned unchanged, exactly like the pre-existing
        # "not provider_links" early return above.
        new_links = {
            provider: link
            for provider, link in provider_links.items()
            if link not in content
        }

        if not new_links:
            self._logger.info(
                f"ARCHIVE_INTERNAL_LINKS_SKIPPED | reason=already_present | count={len(provider_links)}"
            )
            return content

        skipped = len(provider_links) - len(new_links)
        if skipped:
            self._logger.info(f"ARCHIVE_INTERNAL_LINKS_DEDUPED | skipped_existing={skipped}")

        links_block = "\n".join(new_links.values())

        voir_aussi_match = _VOIR_AUSSI_RE.search(content)

        if voir_aussi_match:
            insert_position = voir_aussi_match.end()
            links_text = f"\n{links_block}\n"
            content = content[:insert_position] + links_text + content[insert_position:]
            self._logger.info(
                f"ARCHIVE_INTERNAL_LINKS_ADDED | section=Voir_aussi | count={len(new_links)}"
            )
            return content

        liens_externes_match = _LIENS_EXTERNES_RE.search(content)

        if liens_externes_match:
            insert_position = liens_externes_match.start()
            section_text = f"\n== Voir aussi ==\n{links_block}\n"
            content = content[:insert_position] + section_text + content[insert_position:]
            self._logger.info(
                f"ARCHIVE_INTERNAL_LINKS_ADDED | section=Voir_aussi_created | count={len(new_links)}"
            )
            return content

        section_text = f"\n\n== Voir aussi ==\n{links_block}\n"
        content = content + section_text
        self._logger.info(
            f"ARCHIVE_INTERNAL_LINKS_ADDED | section=Voir_aussi_appended | count={len(new_links)}"
        )
        return content