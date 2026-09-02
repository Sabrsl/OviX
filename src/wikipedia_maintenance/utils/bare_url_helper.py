"""
Helper for converting bare URLs (without {{Lien web}} templates) into proper reference templates.

This module handles the detection and conversion of bare URLs in Wikipedia articles,
ensuring that dead links are repaired using proper reference templates ({{Lien web}},
{{article}}, {{ouvrage}}, {{Lien brisé}}, ...) with archive-url, archive-date, and
brisé le parameters — never leaving raw URLs in the article body.

Hardened version: excludes archive URLs from being treated as dead links, scopes
"existing archive nearby" detection to the same line (not a fixed character window),
extracts the archive date from the archive URL itself when not explicitly provided,
normalizes template name casing consistently with ReferenceTemplateHelper, AND
(FIX) correctly detects semi-bare "[url texte]" wiki external links, extracting
the human-written link label as the title and consuming the entire "[...]"
span so no orphaned label text or closing bracket is left behind in the
article body after repair.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse

from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper, ReferenceTemplate


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BareUrlRef:
    """
    Represents a bare (or semi-bare) URL reference found in article text.

    Attributes:
        dead_url: The dead URL that needs repair
        dead_url_start: Start position of the dead URL in the content
        dead_url_end: End position of the dead URL in the content
        replacement_end: End position of the full text to replace (includes
            trailing context, or the closing ']' of a wiki external link
            when link_label is set)
        line_start: Start position of the line containing the URL
        line_end: End position of the line containing the URL
        existing_archive_url: Optional archive URL already present on the same line
        context_text: The full line containing the URL (for diagnostics/title extraction)
        link_label: Optional human-written label from a "[url texte]" wiki
            external link. When present, this is the preferred title
            source and `replacement_end` already accounts for consuming
            the whole "[url texte]" span including the closing ']'.
        replacement_start: Start position of the full span to replace.
            Equals dead_url_start for plain bare URLs, or the position of
            the opening '[' when this is a "[url texte]" wiki link.
    """
    dead_url: str
    dead_url_start: int
    dead_url_end: int
    replacement_end: int
    line_start: int
    line_end: int
    existing_archive_url: Optional[str] = None
    context_text: Optional[str] = None
    link_label: Optional[str] = None
    replacement_start: int = -1

    def __post_init__(self) -> None:
        # Default replacement_start to dead_url_start for backward
        # compatibility with any caller constructing this without it.
        if self.replacement_start == -1:
            object.__setattr__(self, 'replacement_start', self.dead_url_start)


class BareUrlHelper:
    """
    Helper for detecting and converting bare URLs into proper reference templates.
    """

    # Bare URL in free text. Deliberately excludes '(' ')' from the char
    # class terminators is NOT done here (URLs can legitimately contain
    # parens); trailing punctuation cleanup is handled separately in
    # _strip_trailing_punctuation.
    BARE_URL_PATTERN = re.compile(r'https?://[^\s\]\}<>"]+')

    # Recognized web-archive providers. Used both to detect an
    # already-archived URL and to exclude archive URLs from being
    # mistaken for dead links themselves.
    ARCHIVE_URL_PATTERN = re.compile(
        r'https?://(web\.archive\.org|archive\.org|archive\.today|archive\.ph|'
        r'arquivo\.pt|webcache\.googleusercontent\.com)/[^\s\]\}<>"]+'
    )

    # Extracts a YYYYMMDDHHMMSS (or shorter) timestamp from a
    # web.archive.org URL, e.g. .../web/20210411185258/https://...
    _WAYBACK_TIMESTAMP_RE = re.compile(r'web\.archive\.org/web/(\d{8,14})/')

    # Trailing punctuation that commonly gets swept up by a greedy URL
    # match but isn't actually part of the URL (sentence-ending periods,
    # stray strikethrough markers, closing brackets left over from
    # malformed markup).
    _TRAILING_JUNK_RE = re.compile(r'[.,;:~\s]+$')

    # Pattern to detect trailing context after a bare URL that should be
    # included in the replacement (e.g., domain names, date templates)
    # Matches: domain.com, {{date-|...}}, (context), etc.
    _TRAILING_CONTEXT_RE = re.compile(
        r'(?:,\s*[\w.-]+(?:,\s*{{[^}]+}})?|,\s*{{[^}]+}}|\s*\([^)]*\)|,\s*\([^)]*\))+$'
    )

    # FIX: detects a MediaWiki "semi-bare" external link of the form
    # "[https://example.com/page Some human-readable label]". Captures
    # the URL and the label separately. The label itself may not contain
    # ']' (that would end the link) but may contain nested [[wikilinks]]
    # in theory; we keep this conservative and simple since reference
    # link labels are effectively always plain text in practice, and a
    # false negative here just falls back to old (safe) bare-URL handling.
    _WIKI_EXTERNAL_LINK_RE = re.compile(
        r'\[(https?://[^\s\]]+)[ \t]+([^\]\n]*?)\]'
    )

    def __init__(self) -> None:
        self._logger = logger

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def find_bare_urls(self, content: str) -> List[BareUrlRef]:
        """
        Find all bare or semi-bare dead-link URLs in the given content.
        Archive URLs (web.archive.org, archive.today, arquivo.pt, ...) are
        never themselves reported as dead links needing repair.

        This detects two forms:
          1. A fully bare URL floating in text: "https://example.com/page"
          2. A MediaWiki external link with a label:
             "[https://example.com/page Some Title]"
             In this case the entire "[...]" span (including brackets) is
             what must be replaced, and "Some Title" is captured as
             `link_label` so callers can use it as the reference title
             instead of guessing one from the URL path.

        Args:
            content: Article content to search

        Returns:
            List of BareUrlRef objects representing found bare URLs.
        """
        if not content:
            return []

        bare_refs: List[BareUrlRef] = []
        # Track spans already consumed by a wiki-link match so the plain
        # BARE_URL_PATTERN pass below doesn't also report the same URL a
        # second time as an unlabeled bare URL.
        consumed_spans: List[Tuple[int, int]] = []

        # --- Pass 1: semi-bare "[url texte]" wiki external links -------
        for match in self._WIKI_EXTERNAL_LINK_RE.finditer(content):
            raw_url = match.group(1)
            raw_label = match.group(2)
            url, _trimmed = self._strip_trailing_punctuation(raw_url)
            if not url:
                continue

            # Never treat an archive URL itself as a dead link to repair.
            if self.ARCHIVE_URL_PATTERN.match(url):
                continue

            link_start = match.start()      # position of '['
            link_end = match.end()          # position just past ']'
            url_start = match.start(1)
            url_end = url_start + len(url)

            line_start = content.rfind('\n', 0, link_start) + 1
            line_end = content.find('\n', link_start)
            if line_end == -1:
                line_end = len(content)

            label = raw_label.strip()
            label = label if label else None

            line = content[line_start:line_end]
            existing_archive = None
            for archive_match in self.ARCHIVE_URL_PATTERN.finditer(line):
                candidate, _ = self._strip_trailing_punctuation(archive_match.group(0))
                if candidate and candidate != url:
                    existing_archive = candidate
                    break

            bare_ref = BareUrlRef(
                dead_url=url,
                dead_url_start=url_start,
                dead_url_end=url_end,
                replacement_start=link_start,
                replacement_end=link_end,
                line_start=line_start,
                line_end=line_end,
                existing_archive_url=existing_archive,
                context_text=line,
                link_label=label,
            )
            bare_refs.append(bare_ref)
            consumed_spans.append((link_start, link_end))

            self._logger.info(
                f"WIKI_LINK_BARE_URL_FOUND | url={url[:80]} | label={label!r} | "
                f"has_existing_archive={existing_archive is not None}"
            )

        # --- Pass 2: plain bare URLs not already consumed above --------
        for match in self.BARE_URL_PATTERN.finditer(content):
            start_pos = match.start()
            end_pos_raw = match.end()

            # Skip if this URL occurrence falls inside a span already
            # handled as a "[url texte]" wiki link above.
            if any(span_start <= start_pos < span_end for span_start, span_end in consumed_spans):
                continue

            raw_url = match.group(0)
            url, trimmed = self._strip_trailing_punctuation(raw_url)
            if not url:
                continue

            start_pos = match.start()
            end_pos = start_pos + len(url)

            # Calculate line boundaries first
            line_start = content.rfind('\n', 0, start_pos) + 1
            line_end = content.find('\n', start_pos)
            if line_end == -1:
                line_end = len(content)

            # Detect trailing context that should be included in replacement
            # (e.g., domain names, date templates, parenthetical notes)
            replacement_end = end_pos
            if end_pos < line_end:
                # Look ahead for trailing context patterns
                remaining_line = content[end_pos:line_end]
                context_match = self._TRAILING_CONTEXT_RE.search(remaining_line)
                if context_match:
                    replacement_end = end_pos + context_match.end()
                    self._logger.info(f"TRAILING_CONTEXT_DETECTED | url={url[:80]} | context={context_match.group(0)[:50]}")

            # An archive URL is never itself a "dead link to repair".
            if self.ARCHIVE_URL_PATTERN.match(url):
                self._logger.info(f"SKIP_ARCHIVE_URL_AS_DEAD_LINK | url={url[:80]}")
                continue

            line = content[line_start:line_end]

            # Only look for an existing archive URL on the SAME line,
            # never in a fixed character window that could bleed into
            # a neighbouring, unrelated reference.
            existing_archive = None
            for archive_match in self.ARCHIVE_URL_PATTERN.finditer(line):
                candidate, _ = self._strip_trailing_punctuation(archive_match.group(0))
                if candidate and candidate != url:
                    existing_archive = candidate
                    break

            bare_ref = BareUrlRef(
                dead_url=url,
                dead_url_start=start_pos,
                dead_url_end=end_pos,
                replacement_start=start_pos,
                replacement_end=replacement_end,
                line_start=line_start,
                line_end=line_end,
                existing_archive_url=existing_archive,
                context_text=line,
                link_label=None,
            )
            bare_refs.append(bare_ref)

            self._logger.info(
                f"BARE_URL_FOUND | url={url[:80]} | has_existing_archive={existing_archive is not None}"
                + (f" | trimmed={trimmed!r}" if trimmed else "")
            )

        # Keep results in document order regardless of which pass found them.
        bare_refs.sort(key=lambda r: r.replacement_start)
        return bare_refs

    @classmethod
    def _strip_trailing_punctuation(cls, url: str) -> tuple:
        """
        Remove trailing punctuation/whitespace/strikethrough markers that
        a greedy regex match may have swept in but aren't part of the URL
        (e.g. "https://example.com/page." or "https://example.com/page~~").

        Returns (cleaned_url, trimmed_suffix).
        """
        cleaned = cls._TRAILING_JUNK_RE.sub('', url)
        trimmed = url[len(cleaned):]
        return cleaned, trimmed

    # ------------------------------------------------------------------
    # Title validation (shared by link_label and title_hint paths)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_title_candidate(title: Optional[str], dead_url: str, logger_: logging.Logger,
                                   source: str) -> Optional[str]:
        """
        Apply the same anti-fragment quality checks to any candidate
        title string, regardless of whether it came from `title_hint` or
        from a "[url texte]" wiki link label. Returns the cleaned title,
        or None if it should be rejected.
        """
        if not title or not title.strip():
            return None

        candidate = title.strip()

        if len(candidate) < 3:
            logger_.warning(f"SKIP_TITLE_TOO_SHORT | source={source} | title={candidate!r} | url={dead_url[:80]}")
            return None
        # A raw '|' inside a candidate title is always a parsing/markup
        # artifact (e.g. an unescaped pipe from surrounding wikitext, or
        # multiple pipe-joined fragments concatenated by an upstream
        # mis-split), never a legitimate part of a title. Reject rather
        # than let it ride into the generated template/prose, where it
        # would corrupt param parsing or Markdown-link rendering downstream.
        if '|' in candidate:
            logger_.warning(f"SKIP_TITLE_CONTAINS_PIPE | source={source} | title={candidate!r} | url={dead_url[:80]}")
            return None
        # Unbalanced brackets in a title are similarly always an artifact
        # of malformed markup, not a real title — reject defensively so
        # they can't produce a dangling '[' or ']' once embedded in
        # generated wikitext or Markdown-style prose links.
        if candidate.count('[') != candidate.count(']'):
            logger_.warning(f"SKIP_TITLE_UNBALANCED_BRACKETS | source={source} | title={candidate!r} | url={dead_url[:80]}")
            return None
        if re.match(r'^\d{1,2}\.\d{1,2}$', candidate):
            logger_.warning(f"SKIP_SUSPICIOUS_DATE_TITLE | source={source} | title={candidate!r} | url={dead_url[:80]}")
            return None
        if candidate.startswith('«') and candidate.endswith('»') and len(candidate) < 10:
            logger_.warning(f"SKIP_SHORT_QUOTED_TITLE | source={source} | title={candidate!r} | url={dead_url[:80]}")
            return None
        if re.search(r'20\d{2}', candidate) and len(candidate) < 20:
            logger_.warning(f"SKIP_DATE_DOMINATED_TITLE | source={source} | title={candidate!r} | url={dead_url[:80]}")
            return None

        return candidate

    # ------------------------------------------------------------------
    # Repair
    # ------------------------------------------------------------------

    def build_repaired_reference_template(
        self,
        ref: BareUrlRef,
        archive_url: str,
        archive_date: str,
        title_hint: Optional[str] = None,
        provider: Optional[str] = None,
        template_name: str = 'Lien web',
        extra_params: Optional[Dict[str, str]] = None,
        template_helper: Optional[ReferenceTemplateHelper] = None,
    ) -> Optional[str]:
        """
        Convert a bare (or semi-bare "[url texte]") dead URL with a VALID
        archive correction into a proper Wikipedia reference template —
        Lien web, article, ouvrage, Lien brisé, or any other template
        listed in ReferenceTemplateHelper.TEMPLATE_SPECIFIC_PARAMETERS.

        Returns None if no valid correction is available: the bot must then
        leave the line untouched rather than guessing.

        Title resolution priority (FIX: previously `ref.link_label`, the
        human-written wiki-link text, was never consulted at all, so the
        bot fell back to a poor URL-path-derived title while the real
        label text was left dangling, unconsumed, in the article body):

          1. `title_hint`, if provided and it passes quality checks.
          2. `ref.link_label` (the text of a "[url texte]" wiki link),
             if present and it passes the same quality checks.
          3. `UrlMetadataExtractor.extract_title(ref.dead_url)` — a
             best-effort guess from the URL path.
          4. The bare domain, capitalized, as an absolute last resort.

        Args:
            ref: The BareUrlRef to convert.
            archive_url: Archive URL to use for repair. Ignored if `ref`
                already carries a valid existing_archive_url on the same line.
            archive_date: Archive date from provider (YYYYMMDDHHMMSS or
                YYYY-MM-DD). If empty/None and the archive URL is a
                web.archive.org URL, the date is extracted from the URL
                itself.
            title_hint: Optional title to use in the template. Takes
                priority over ref.link_label when both are present.
            provider: Archive provider name (e.g., WaybackMachine, Arquivo.pt).
            template_name: Template type to use (default: 'Lien web').
                Matched case-insensitively against
                ReferenceTemplateHelper.KNOWN_TEMPLATE_NAMES, consistent
                with template detection elsewhere in the pipeline.
            extra_params: Additional parameters for the template (auteur,
                éditeur, isbn, etc.).
            template_helper: ReferenceTemplateHelper instance (a new one is
                created if not supplied).

        Returns:
            A properly formatted template string, or None if no valid
            correction is available.
        """
        if template_helper is None:
            template_helper = ReferenceTemplateHelper()

        # --- Resolve and validate the archive URL --------------------
        final_archive_url = (ref.existing_archive_url or archive_url or "").strip()

        if not final_archive_url:
            self._logger.info(f"SKIP_NO_ARCHIVE_URL | url={ref.dead_url[:80]}")
            return None
        if not final_archive_url.startswith(("http://", "https://")):
            self._logger.info(
                f"SKIP_INVALID_ARCHIVE_URL | url={ref.dead_url[:80]} | archive={final_archive_url[:80]}"
            )
            return None
        if not self.ARCHIVE_URL_PATTERN.match(final_archive_url):
            self._logger.info(
                f"SKIP_UNKNOWN_ARCHIVE_HOST | url={ref.dead_url[:80]} | archive={final_archive_url[:80]}"
            )
            return None

        # --- Resolve archive date, falling back to the URL's own timestamp
        resolved_archive_date = (archive_date or "").strip()
        if not resolved_archive_date:
            timestamp_match = self._WAYBACK_TIMESTAMP_RE.search(final_archive_url)
            if timestamp_match:
                resolved_archive_date = timestamp_match.group(1)
                self._logger.info(
                    f"ARCHIVE_DATE_EXTRACTED_FROM_URL | url={ref.dead_url[:80]} | "
                    f"date={resolved_archive_date}"
                )

        if not resolved_archive_date:
            self._logger.info(f"SKIP_NO_ARCHIVE_DATE | url={ref.dead_url[:80]}")
            return None

        # --- Resolve and validate the template name -------------------
        normalized_key = template_name.strip().lower().replace('_', ' ')
        resolved_template_name = template_helper.KNOWN_TEMPLATE_NAMES.get(normalized_key)
        if resolved_template_name is None:
            # Not a recognized alias; accept it as-is only if it's an
            # exact, already-canonical key (e.g. someone passed 'ouvrage'
            # directly and it matches a TEMPLATE_SPECIFIC_PARAMETERS key).
            if template_name in template_helper.TEMPLATE_SPECIFIC_PARAMETERS:
                resolved_template_name = template_name
            else:
                self._logger.warning(
                    f"SKIP_UNKNOWN_TEMPLATE | template={template_name!r} | url={ref.dead_url[:80]}"
                )
                return None

        # --- Build base parameters from what we can extract ------------
        base_params: Dict[str, str] = {}

        # FIX: title resolution now tries, in order: title_hint ->
        # ref.link_label -> URL-path extraction -> bare domain. Both
        # title_hint and link_label go through the exact same quality
        # gate (_validate_title_candidate) so a wiki-link label with a
        # suspicious shape (too short, date-like, etc.) is rejected just
        # like a bad title_hint would be, and falls through to the next
        # tier instead of being trusted blindly.
        title_to_use = self._validate_title_candidate(title_hint, ref.dead_url, self._logger, source='title_hint')

        if not title_to_use and ref.link_label:
            title_to_use = self._validate_title_candidate(
                ref.link_label, ref.dead_url, self._logger, source='link_label'
            )
            if title_to_use:
                self._logger.info(f"TITLE_FROM_LINK_LABEL | url={ref.dead_url[:80]} | title={title_to_use!r}")

        if title_to_use:
            base_params['titre'] = title_to_use
        else:
            # Fallback to URL-based title extraction
            from wikipedia_maintenance.utils.url_metadata import UrlMetadataExtractor
            extracted_title = UrlMetadataExtractor.extract_title(ref.dead_url)
            if extracted_title:
                base_params['titre'] = extracted_title
            else:
                # Ultimate fallback: use domain as generic title
                domain = self._safe_extract_domain(ref.dead_url)
                if domain:
                    base_params['titre'] = domain[0].upper() + domain[1:] if domain else "Page web"

        domain = self._safe_extract_domain(ref.dead_url)
        if domain and resolved_template_name != 'ouvrage':
            # Resolve the domain to its human-readable display name
            # (e.g. "lemonde.fr" -> "Le Monde") via the SAME resolver
            # ReferenceTemplateHelper uses when it fills |site= itself, so
            # a bare-URL repair and an existing-template repair for the
            # same outlet produce the same |site= value.
            base_params['site'] = template_helper._resolve_site_display_name(domain)

        if extra_params:
            base_params.update(extra_params)

        synthetic_template = ReferenceTemplate(
            template_name=resolved_template_name,
            parameters=base_params,
            full_match='',
            start_position=ref.replacement_start,
            end_position=ref.line_end,
        )

        template_str = template_helper.generate_archive_repair_template(
            synthetic_template,
            archive_url=final_archive_url,
            archive_date=resolved_archive_date,
            original_url=ref.dead_url,
            assume_patch_deployed=False,  # keep url=original, archive as parameter
            provider=provider,
        )

        self._logger.info(
            f"BARE_URL_CONVERTED | original={ref.dead_url[:80]} | "
            f"template={resolved_template_name} | had_link_label={ref.link_label is not None} | "
            f"result={template_str[:120]}"
        )

        return template_str

    @staticmethod
    def _safe_extract_domain(url: str) -> str:
        try:
            return urlparse(url).netloc
        except (ValueError, AttributeError):
            return ""