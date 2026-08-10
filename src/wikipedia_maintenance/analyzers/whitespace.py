"""
Analyzer for whitespace-related issues in Wikipedia articles.
Full compliance with French typography and MediaWiki conventions.
Detects and suggests fixes for:
    - double/multiple spaces
    - missing/extra spaces around punctuation (French rules)
    - non-breaking space suggestions (before ; : ! ?)
    - spaces before/after links, templates, HTML tags
    - spaces inside table cells, list items, headings
    - trailing whitespace, leading spaces (with heuristics)
    - spaces before line breaks
    - spaces around equal signs in headings
    - spaces before/after ref tags, etc.
All detections are non‑destructive and preserve existing functionality.

FIX LOG (this revision):
  - _detect_spaces_before_units was inserting spurious spaces into brand
    names, redirects, template parameters and filenames (e.g. "8TV" -> "8 TV",
    "{{Voir homonymes|8tv}}" -> "{{Voir homonymes|8 tv}}") because it had
    NO awareness of templates/links and NO real unit whitelist. It now:
      * only fires on a closed whitelist of genuine units,
      * requires a word boundary before the digits (not mid-identifier),
      * skips templates, links, and filename-like tokens (digits directly
        followed by a known file extension).
  - _detect_missing_space_after_punctuation was breaking file extensions
    (e.g. "logo_8tv_2021.svg" -> "logo_8tv_2021. svg"). It now recognizes
    a trailing known extension after a '.' and skips it, and also skips
    inside links (it previously only skipped inside templates).
  - _detect_spaces_in_links never excluded File/Fichier/Image/Catégorie/
    Category/Media links even though a (dead, unused) regex documented
    that intent. It now actually excludes those namespaces, so links to
    images/files/categories are left untouched.
"""

import re
from typing import List, Optional, Tuple
from .base import BaseAnalyzer, Issue


class WhitespaceAnalyzer(BaseAnalyzer):
    """
    Enhanced whitespace analyzer with exhaustive pattern coverage.
    """

    # ---------- Compiled patterns for performance ----------

    # Double/multiple spaces (exclude those inside templates/links partially)
    DOUBLE_SPACE = re.compile(r'  +')

    # Space before punctuation that should NOT have one ( , . ) ] } )
    SPACE_BEFORE_BAD_PUNCT = re.compile(r' +([,.\]\)])')

    # Missing space BEFORE French strong punctuation ( ; : ! ? ) – suggests non-breaking
    MISSING_SPACE_BEFORE_STRONG = re.compile(r'(?<!\s)([;:!?])')

    # Normal space before strong punctuation – suggests non-breaking
    NORMAL_SPACE_BEFORE_STRONG = re.compile(r' ([;:!?])')

    # Missing space AFTER punctuation ( . , ; : ! ? )
    MISSING_SPACE_AFTER_PUNCT = re.compile(r'([.,;:!?])(?=[^\s\d])')

    # Trailing whitespace (end of line)
    TRAILING_WHITESPACE = re.compile(r'[ \t]+$', re.MULTILINE)

    # Leading spaces (indentation) – flag but low severity
    LEADING_SPACES = re.compile(r'^( +)', re.MULTILINE)

    # Spaces around link brackets: [[ space... ]] or [[... space]]
    # Exclude file/category/image links to avoid breaking filenames with spaces
    LINK_INTERNAL_SPACES = re.compile(r'\[\[(?!(?:Fichier|File|Catégorie|Category|Image|Media):)([^\[\]]*?)\s+([^\[\]]*?)\]\]')  # catches spaces inside

    # Namespaces that must NEVER have their link content touched (files, images,
    # categories, media) — spaces there are frequently meaningful (filenames,
    # sort keys) and must be preserved.
    LINK_PROTECTED_NAMESPACES = re.compile(
        r'^\s*(Fichier|File|Catégorie|Category|Image|Media)\s*:', re.IGNORECASE
    )

    # Spaces around template braces: {{ space... }} or {{... space}}
    # Disabled to avoid breaking template parameters with intentional spaces
    # TEMPLATE_SPACES = re.compile(r'\{\{([^\{\}]*?)\s+([^\{\}]*?)\}\}')

    # Spaces before/after heading equals signs.
    # IMPORTANT: "== Titre ==" (a single space on each side) is the standard,
    # desired convention on the French Wikipedia — it must NEVER be touched.
    # This pattern only matches genuine problems: 2+ spaces/tabs, or a tab,
    # on either side of the title. A single regular space does not match.
    HEADING_SPACES = re.compile(r'^(={2,6})([ \t]*)([^=\n]*?)([ \t]*)\1[ \t]*$', re.MULTILINE)

    # Spaces before line breaks (not just trailing)
    SPACE_BEFORE_NEWLINE = re.compile(r' \n')

    # Spaces before pipe in tables (|) – often extra space before |
    # Exclude template parameters (inside {{ ... }}) to avoid breaking template syntax
    SPACE_BEFORE_PIPE = re.compile(r' +\|')

    # Spaces after pipe in tables (| ) – often extra space after |
    # Exclude template parameters (inside {{ ... }}) to avoid breaking template syntax
    SPACE_AFTER_PIPE = re.compile(r'\| +')

    # Spaces before list markers ( * , # , : , ; ) – usually not wanted
    SPACE_BEFORE_LIST_MARKER = re.compile(r'^ +([*#:;])', re.MULTILINE)

    # Spaces around HTML tags (e.g., <ref> </ref>)
    SPACE_BEFORE_HTML_TAG = re.compile(r' +(<[^>]+>)')
    SPACE_AFTER_HTML_TAG = re.compile(r'(</?[^>]+>) +')

    # Spaces around comments <!-- -->
    SPACE_BEFORE_COMMENT = re.compile(r' +(<!--)')
    SPACE_AFTER_COMMENT = re.compile(r'(-->) +')

    # Non-breaking spaces with normal spaces before ; : ! ? already covered

    # ---------- Generalized "protected zone" system ----------
    #
    # Anticipates the whole class of bugs seen so far (namespace colons,
    # filename extensions, CSS attributes...) by protecting technical spans
    # OUTRIGHT, regardless of which detector would otherwise touch them.
    #
    # Covered:
    #   - <nowiki>/<pre>/<syntaxhighlight>/<source>/<math>/<code> blocks:
    #     their content is opaque and must be preserved byte-for-byte
    #     (code samples, literal syntax demonstrations, formulas).
    #   - HTML comments <!-- ... -->: invisible to readers, don't touch.
    #   - Any single HTML/wiki tag <...>: protects attribute internals
    #     like style="text-align:center;" from punctuation rules.
    #   - Double-quoted strings "...": catches CSS/HTML attribute values
    #     even outside a recognized tag (e.g. inside wikitable syntax).
    #   - Single-bracket spans [...]: external links, footnote markers,
    #     "[citation needed]"-style notes.
    OPAQUE_TAG_BLOCK = re.compile(
        r'<(nowiki|pre|syntaxhighlight|source|math|code)\b[^>]*>.*?</\1>',
        re.IGNORECASE | re.DOTALL
    )
    HTML_COMMENT_BLOCK = re.compile(r'<!--.*?-->', re.DOTALL)
    SINGLE_TAG = re.compile(r'<[^>]+>')
    QUOTED_STRING = re.compile(r'"[^"\n]*"')
    SINGLE_BRACKET_SPAN = re.compile(r'\[[^\[\]\n]*\]')
    
    # Graph/Chart syntax blocks (TimeAxis, Colors, PlotData, etc.)
    GRAPH_SECTION_PATTERN = re.compile(
        r'^(TimeAxis|Colors|Legend|BackgroundColors|ScaleMajor|ScaleMinor|LineData|BarData|PlotData)\s*=',
        re.MULTILINE | re.IGNORECASE
    )
    
    # Graph data lines (bar:, at:, text:, etc.)
    GRAPH_DATA_PATTERN = re.compile(
        r'^(bar|at|text|color|layer|width|textcolor|align|anchor|shift|value|legend|orientation|position|increment|start|from|till)\s*:[^\n]*',
        re.MULTILINE | re.IGNORECASE
    )

    # Consecutive punctuation ("...", "?!", "!!!") must never get spaces
    # forced between the marks themselves.
    PUNCT_CHARS = set('.,;:!?')

    # Non-breaking spaces with normal spaces before ; : ! ? already covered

    # ---------- Guards for the unit / filename heuristic ----------

    # Closed whitelist of genuine units we're willing to suggest spacing for.
    # Anything not in this list is left alone (brand names, model numbers,
    # template params, abbreviations like "8TV" must never match).
    #
    # Deliberately MULTI-LETTER ONLY. Single letters were removed: "h" is
    # the standard French time-of-day notation ("8h", "14h30" is CORRECT
    # as-is — flagging it as "8 h" would be introducing an error, not
    # fixing one), and "a" collides with legal/administrative references
    # like "Article 10a" or "§ 2a". Multi-letter units (km, kg, kWh...)
    # don't have this ambiguity in running text.
    KNOWN_UNITS = {
        'km', 'kg', 'cm', 'mm', 'ha', 'kw', 'mw', 'gw', 'kwh', 'mwh',
        'kb', 'mb', 'gb', 'tb', 'hz', 'khz', 'mhz', 'ghz',
    }
    UNIT_PATTERN = re.compile(
        r'(?<![A-Za-z0-9_])(\d+(?:[.,]\d+)?)(' +
        '|'.join(sorted(KNOWN_UNITS, key=len, reverse=True)) +
        r')(?![A-Za-z0-9_])'
    )

    # Common file extensions — a number immediately followed by one of these
    # after a dot must never be touched (it's a filename, not a sentence).
    FILE_EXTENSIONS = {
        'svg', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'ogg', 'ogv',
        'webm', 'mp3', 'mp4', 'tif', 'tiff', 'djvu', 'xcf', 'flac', 'wav',
    }

    # ---------- Guard for "structural" colons ----------
    #
    # The French "space before ; : ! ?" rule is meant for sentence
    # punctuation. It must NEVER touch a colon that is actually MediaWiki
    # syntax: a namespace prefix ("Fichier:Logo.png", "Catégorie:Chaînes"),
    # a URL scheme ("http://..."), or a time ("12:30"). Inserting a space
    # there breaks the link/file reference outright.
    NAMESPACE_PREFIXES = {
        # French namespaces
        'fichier', 'catégorie', 'spécial', 'utilisateur', 'utilisatrice',
        'wikipédia', 'wp', 'projet', 'portail', 'modèle', 'aide',
        'discussion', 'sujet', 'module', 'medium',
        # English namespaces (also valid on most wikis / interwiki)
        'file', 'category', 'special', 'user', 'wikipedia', 'project',
        'portal', 'template', 'help', 'talk', 'topic', 'module',
        # Generic MediaWiki namespace
        'media', 'mediawiki', 'timedtext',
        # URL schemes
        'http', 'https', 'ftp', 'ftps', 'mailto', 'irc', 'news', 'gopher',
        # Common identifier schemes seen in citations / external links
        'doi', 'isbn', 'issn', 'pmid', 'pmc', 'oclc', 'urn', 'tel', 'geo',
        # Wikipedia graph/chart syntax keywords (TimeAxis, Colors, PlotData, etc.)
        'timeaxis', 'colors', 'legend', 'backgroundcolors', 'scalemajor', 'scaleminor',
        'linedata', 'bardata', 'plotdata', 'width', 'textcolor', 'align', 'anchor',
        'shift', 'value', 'orientation', 'position', 'increment', 'start',
        # Graph data keywords (bar, at, text, color, layer, etc.)
        'bar', 'at', 'text', 'color', 'layer', 'from', 'till',
    }
    _WORD_BEFORE = re.compile(r'([A-Za-zÀ-ÖØ-öø-ÿ]+)$')

    def _is_structural_colon(self, content: str, pos: int) -> bool:
        """
        True if content[pos] == ':' is MediaWiki/URL/time syntax rather than
        French sentence punctuation, and must be left completely untouched.
        """
        if content[pos] != ':':
            return False
        # Time format, e.g. "12:30" — never insert a space in a time.
        if pos > 0 and pos + 1 < len(content) and content[pos - 1].isdigit() and content[pos + 1].isdigit():
            return True
        # Namespace prefix / URL scheme immediately before the colon,
        # with no space in between (that's precisely what makes it syntax).
        word_match = self._WORD_BEFORE.search(content[max(0, pos - 30):pos])
        if word_match and word_match.group(1).lower() in self.NAMESPACE_PREFIXES:
            return True
        return False

    def __init__(self, language: str = 'fr', check_non_breaking: bool = True):
        """
        Initialize the analyzer.

        Args:
            language: Language code (currently 'fr' for French specific rules).
            check_non_breaking: Whether to suggest non‑breaking spaces.
        """
        super().__init__()
        self.language = language.lower()
        self.check_non_breaking = check_non_breaking
        self._protected_spans: List[Tuple[int, int]] = []
        self._opaque_spans: List[Tuple[int, int]] = []

    def analyze(self, content: str) -> List[Issue]:
        """
        Run all whitespace checks.
        """
        self.clear_issues()
        # Precompute technical zones (code blocks, comments, tag internals,
        # quoted attributes, bracketed spans) that NO detector below may
        # touch, regardless of which specific check would otherwise fire.
        self._protected_spans = self._compute_protected_spans(content)
        self._opaque_spans = self._compute_opaque_spans(content)

        # ----- Core checks (always run) -----
        self._detect_double_spaces(content)
        self._detect_spaces_before_bad_punctuation(content)
        self._detect_trailing_whitespace(content)
        self._detect_leading_spaces(content)
        self._detect_spaces_around_headings(content)
        self._detect_spaces_before_newline(content)

        # ----- French‑specific typography -----
        if self.language == 'fr':
            self._detect_missing_space_before_strong_punct(content)
            if self.check_non_breaking:
                self._detect_non_breaking_space_needed(content)

        # ----- Punctuation after (all languages) -----
        self._detect_missing_space_after_punctuation(content)

        # ----- MediaWiki syntax checks -----
        self._detect_spaces_in_links(content)
        # self._detect_spaces_in_templates(content)  # Disabled to avoid breaking templates
        self._detect_spaces_around_pipes(content)
        self._detect_spaces_before_list_markers(content)
        self._detect_spaces_around_html_tags(content)
        self._detect_spaces_around_comments(content)

        # Additional optional checks (low severity)
        self._detect_spaces_before_units(content)  # e.g., "10 km" vs "10km"
        self._detect_spaces_around_quotes(content)  # French guillemets

        return self.issues

    # ------------------------------------------------------------------
    #   Existing methods (preserved and improved)
    # ------------------------------------------------------------------

    def _is_inside_template(self, content: str, position: int) -> bool:
        """
        Check if position is inside a template {{ ... }}.
        More robust than simple brace counting.
        """
        text_before = content[:position]
        open_positions = [m.start() for m in re.finditer(r'\{\{', text_before)]
        close_positions = [m.start() for m in re.finditer(r'\}\}', text_before)]
        return len(open_positions) > len(close_positions)

    def _is_inside_voir_template(self, content: str, position: int) -> bool:
        """
        Check if position is inside a "Voir" template ({{Voir...}}).
        These templates must never be modified as they contain technical parameters.
        """
        # Find the template this position is in
        text_before = content[:position]
        # Find the last opening {{ before this position
        open_matches = list(re.finditer(r'\{\{', text_before))
        if not open_matches:
            return False
        
        last_open = open_matches[-1]
        # Find the closing }} after this position
        text_after = content[position:]
        close_match = re.search(r'\}\}', text_after)
        if not close_match:
            return False
        
        # Extract the template content
        template_start = last_open.end()
        template_end = position + close_match.start()
        template_content = content[template_start:template_end].strip()
        
        # Check if it's a "Voir" template
        return template_content.startswith('Voir') or template_content.startswith('voir')

    def _is_inside_link(self, content: str, position: int) -> bool:
        """
        Check if position is inside a link [[ ... ]].
        """
        text_before = content[:position]
        open_positions = [m.start() for m in re.finditer(r'\[\[', text_before)]
        close_positions = [m.start() for m in re.finditer(r'\]\]', text_before)]
        return len(open_positions) > len(close_positions)

    def _looks_like_filename(self, content: str, match_end: int) -> bool:
        """
        Returns True if, right after `match_end`, the text looks like a file
        extension (".svg", ".png", ...). Used to protect filenames from
        being mangled by the "missing space after punctuation" check.
        """
        tail = content[match_end:match_end + 6].lower()
        for ext in self.FILE_EXTENSIONS:
            if tail.startswith(ext):
                # must be a clean word boundary after the extension
                after = content[match_end + len(ext):match_end + len(ext) + 1]
                if after == '' or not (after.isalnum() or after == '_'):
                    return True
        return False

    def _compute_protected_spans(self, content: str) -> List[Tuple[int, int]]:
        """
        Precompute (once per analyze() call) every span of text that must be
        left completely untouched by every detector: opaque code/formula
        blocks, HTML comments, tag internals, quoted attribute strings, bracketed
        link/note syntax, and graph/chart syntax. Overlapping spans are merged
        so lookups are a simple sorted scan.
        """
        spans: List[Tuple[int, int]] = []
        
        # First, add graph/chart syntax sections
        for m in self.GRAPH_SECTION_PATTERN.finditer(content):
            section_start = m.start()
            # Find the end of this section (next section at same level or end)
            section_end = len(content)
            next_section = self.GRAPH_SECTION_PATTERN.search(content, m.end())
            if next_section:
                section_end = next_section.start()
            else:
                # Look for next major section (template, heading, etc.)
                next_heading = re.search(r'\n={2,6}', content[m.end():])
                next_template = re.search(r'\n\{\{', content[m.end():])
                if next_heading and next_template:
                    section_end = m.end() + min(next_heading.start(), next_template.start())
                elif next_heading:
                    section_end = m.end() + next_heading.start()
                elif next_template:
                    section_end = m.end() + next_template.start()
            spans.append((section_start, section_end))
        
        # Add individual graph data lines
        for m in self.GRAPH_DATA_PATTERN.finditer(content):
            line_start = m.start()
            line_end = content.find('\n', line_start)
            if line_end == -1:
                line_end = len(content)
            spans.append((line_start, line_end))
        
        # Then add other protected spans
        for pattern in (
            self.OPAQUE_TAG_BLOCK,
            self.HTML_COMMENT_BLOCK,
            self.SINGLE_TAG,
            self.QUOTED_STRING,
            self.SINGLE_BRACKET_SPAN,
        ):
            spans.extend((m.start(), m.end()) for m in pattern.finditer(content))
        return self._merge_spans(spans)

    def _compute_opaque_spans(self, content: str) -> List[Tuple[int, int]]:
        """
        Narrower list used only by detectors that work AT tag/comment
        boundaries (space before/after a <tag>, before/after <!-- -->).
        Those must only be suppressed when genuinely nested inside an
        opaque block or another comment — not simply because they touch
        a tag, or the detector would never fire at all.
        """
        spans: List[Tuple[int, int]] = []
        for pattern in (self.OPAQUE_TAG_BLOCK, self.HTML_COMMENT_BLOCK):
            spans.extend((m.start(), m.end()) for m in pattern.finditer(content))
        return self._merge_spans(spans)

    @staticmethod
    def _merge_spans(spans: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if not spans:
            return []
        spans.sort()
        merged = [spans[0]]
        for start, end in spans[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged

    def _is_protected(self, position: int) -> bool:
        """
        True if `position` falls inside a precomputed protected span
        (opaque block, comment, tag, quoted string, or bracketed span).
        Spans are sorted, so we can stop scanning once we've passed
        `position` — cheap even for long articles.
        """
        return self._position_in_spans(position, self._protected_spans)

    def _is_in_opaque_block(self, position: int) -> bool:
        """
        True only if `position` is nested inside an opaque code/formula
        block or an HTML comment — used by tag/comment-boundary detectors
        that must not be disabled just because they touch a tag.
        """
        return self._position_in_spans(position, self._opaque_spans)

    @staticmethod
    def _position_in_spans(position: int, spans: List[Tuple[int, int]]) -> bool:
        for start, end in spans:
            if start > position:
                break
            if start <= position < end:
                return True
        return False

    def _is_consecutive_punctuation(self, content: str, position: int, direction: str) -> bool:
        """
        True if the character immediately before/after `position` is itself
        a punctuation mark from PUNCT_CHARS. Prevents detectors from forcing
        a space INSIDE a run of punctuation such as an ellipsis ("...") or
        an interrobang-style combo ("?!", "!!!") — inserting spaces there
        would turn "..." into ". . ." instead of leaving it alone.
        direction: 'before' checks content[position-1], 'after' checks
        content[position+1] relative to the punctuation character at
        content[position].
        """
        if direction == 'before':
            idx = position - 1
        else:
            idx = position + 1
        if 0 <= idx < len(content):
            return content[idx] in self.PUNCT_CHARS
        return False

    def _detect_double_spaces(self, content: str) -> None:
        for match in self.DOUBLE_SPACE.finditer(content):
            pos = match.start()
            if self._is_inside_template(content, pos):
                continue
            if self._is_inside_link(content, pos):
                continue
            if self._is_inside_voir_template(content, pos):
                continue
            if self._is_protected(pos):
                continue
            self.issues.append(Issue(
                issue_type="double_space",
                description="Doubles espaces ou plus",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=" ",
                severity="low"
            ))

    def _detect_spaces_before_bad_punctuation(self, content: str) -> None:
        for match in self.SPACE_BEFORE_BAD_PUNCT.finditer(content):
            pos = match.start()
            if self._is_inside_template(content, pos):
                continue
            if self._is_inside_link(content, pos):
                continue
            if self._is_inside_voir_template(content, pos):
                continue
            if self._is_protected(pos):
                continue
            self.issues.append(Issue(
                issue_type="space_before_punctuation",
                description=f"Espace superflu avant '{match.group(1)}'",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=match.group(1),
                severity="low"
            ))

    def _detect_trailing_whitespace(self, content: str) -> None:
        for match in self.TRAILING_WHITESPACE.finditer(content):
            if self._is_protected(match.start()):
                continue
            self.issues.append(Issue(
                issue_type="trailing_whitespace",
                description="Espace en fin de ligne",
                position=match.start(),
                original_text=match.group(0),
                suggested_text="",
                severity="low"
            ))

    def _detect_leading_spaces(self, content: str) -> None:
        for match in self.LEADING_SPACES.finditer(content):
            start = match.start()
            if start > 0 and content[start - 1] != '\n':
                continue
            if self._is_protected(start):
                continue
            rest = content[match.end():]
            if rest and rest[0] in ('*', '#', ':', ';', '|'):
                continue
            self.issues.append(Issue(
                issue_type="leading_spaces",
                description="Espaces en début de ligne (indentation non standard)",
                position=match.start(),
                original_text=match.group(1),
                suggested_text="",
                severity="low"
            ))

    # ------------------------------------------------------------------
    #   New enhanced detections
    # ------------------------------------------------------------------

    def _detect_missing_space_before_strong_punct(self, content: str) -> None:
        for match in self.MISSING_SPACE_BEFORE_STRONG.finditer(content):
            pos = match.start()
            if self._is_inside_template(content, pos):
                continue
            if self._is_inside_link(content, pos):
                continue
            if self._is_inside_voir_template(content, pos):
                continue
            if self._is_structural_colon(content, pos):
                continue
            if self._is_protected(pos):
                continue
            # Don't force a space INSIDE a run of punctuation, e.g. an
            # ellipsis "..." or a combo like "?!" / "!!!" — that would turn
            # "..." into ". . ." instead of leaving it alone.
            if self._is_consecutive_punctuation(content, pos, 'before'):
                continue
            self.issues.append(Issue(
                issue_type="missing_space_before_punctuation",
                description=f"Espace manquant avant '{match.group(1)}' (préférer une espace insécable)",
                position=match.start(),
                original_text=match.group(1),
                suggested_text="\u00A0" + match.group(1),
                severity="medium"
            ))

    def _detect_non_breaking_space_needed(self, content: str) -> None:
        for match in self.NORMAL_SPACE_BEFORE_STRONG.finditer(content):
            pos = match.start()
            if self._is_inside_template(content, pos):
                continue
            if self._is_inside_link(content, pos):
                continue
            if self._is_inside_voir_template(content, pos):
                continue
            if self._is_structural_colon(content, match.end() - 1):
                continue
            if self._is_protected(pos):
                continue
            self.issues.append(Issue(
                issue_type="non_breaking_space_needed",
                description=f"Utiliser une espace insécable avant '{match.group(1)}'",
                position=match.start(),
                original_text=match.group(0),
                suggested_text="\u00A0" + match.group(1),
                severity="low"
            ))

    def _detect_missing_space_after_punctuation(self, content: str) -> None:
        """
        Punctuation should be followed by a space (except in numbers,
        abbreviations, and — critically — filenames/extensions).
        Skips templates AND links (previously only skipped templates).
        """
        for match in self.MISSING_SPACE_AFTER_PUNCT.finditer(content):
            pos = match.start()
            if self._is_inside_template(content, pos):
                continue
            if self._is_inside_link(content, pos):
                continue
            if self._is_inside_voir_template(content, pos):
                continue
            if self._is_structural_colon(content, pos):
                continue
            if self._is_protected(pos):
                continue
            # Same ellipsis / "?!" / "!!!" protection as the other detector.
            if self._is_consecutive_punctuation(content, pos, 'after'):
                continue
            # Never break a filename/extension like "....2021.svg"
            # NOTE: match.end() already points to the character right after
            # the punctuation (the group only captures the punctuation
            # itself, the lookahead isn't consumed) — passing match.end()-1
            # here was an off-by-one bug that pointed AT the dot instead of
            # after it, so the extension check ("svg".startswith(...)) never
            # matched and filenames kept getting mangled whenever they
            # weren't also caught by the template/link guard above.
            if self._looks_like_filename(content, match.end()):
                continue
            before = content[match.start() - 1:match.start()] if match.start() > 0 else ''
            after = content[match.end():match.end() + 1]
            if before.isdigit() and after.isdigit():
                continue
            severity = "low" if before.isalpha() and after.isalpha() else "medium"
            self.issues.append(Issue(
                issue_type="missing_space_after_punctuation",
                description=f"Espace manquant après '{match.group(1)}'",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=match.group(1) + " ",
                severity=severity
            ))

    def _detect_spaces_around_headings(self, content: str) -> None:
        """
        Only flags genuinely irregular spacing (2+ spaces, or a tab) around a
        section title. A single regular space ("== Titre ==") is the normal,
        desired convention and must never be flagged or stripped — that was
        the previous bug. If some spacing was present, it's normalized down
        to exactly one space rather than removed entirely; if there was no
        spacing at all on a side, that side is left untouched.
        """
        for match in self.HEADING_SPACES.finditer(content):
            if self._is_protected(match.start()):
                continue
            marker, leading, title, trailing = match.group(1), match.group(2), match.group(3), match.group(4)
            leading_ok = leading in ("", " ")
            trailing_ok = trailing in ("", " ")
            if leading_ok and trailing_ok:
                continue
            fixed_leading = " " if leading else ""
            fixed_trailing = " " if trailing else ""
            self.issues.append(Issue(
                issue_type="heading_spaces",
                description="Espacement irrégulier autour du titre de section (espaces multiples ou tabulation)",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=f"{marker}{fixed_leading}{title}{fixed_trailing}{marker}",
                severity="low"
            ))

    def _detect_spaces_before_newline(self, content: str) -> None:
        for match in self.SPACE_BEFORE_NEWLINE.finditer(content):
            if self._is_protected(match.start()):
                continue
            self.issues.append(Issue(
                issue_type="space_before_newline",
                description="Espace avant un saut de ligne",
                position=match.start(),
                original_text=" ",
                suggested_text="",
                severity="low"
            ))

    def _detect_spaces_in_links(self, content: str) -> None:
        """
        Internal links should not have leading/trailing spaces: [[ link ]] -> [[link]].
        Files/images/categories/media are EXCLUDED: spaces there can be part
        of the actual filename or a meaningful sort key and must be left alone.
        """
        link_pattern = re.compile(r'\[\[([^\[\]]*?)\]\]')
        for match in link_pattern.finditer(content):
            inner = match.group(1)
            if self.LINK_PROTECTED_NAMESPACES.match(inner):
                continue
            stripped = inner.strip()
            if inner != stripped:
                self.issues.append(Issue(
                    issue_type="link_spaces",
                    description="Espaces superflus dans le lien interne",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text="[[" + stripped + "]]",
                    severity="low"
                ))

    def _detect_spaces_in_templates(self, content: str) -> None:
        template_pattern = re.compile(r'\{\{([^\{\}]*?)\}\}')
        for match in template_pattern.finditer(content):
            inner = match.group(1)
            stripped = inner.strip()
            if inner != stripped:
                self.issues.append(Issue(
                    issue_type="template_spaces",
                    description="Espaces superflus dans le modèle",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text="{{" + stripped + "}}",
                    severity="low"
                ))

    def _detect_spaces_around_pipes(self, content: str) -> None:
        for match in self.SPACE_BEFORE_PIPE.finditer(content):
            pos = match.start()
            if self._is_inside_template(content, pos):
                continue
            if self._is_inside_link(content, pos):
                continue
            if self._is_inside_voir_template(content, pos):
                continue
            if self._is_protected(pos):
                continue
            self.issues.append(Issue(
                issue_type="space_before_pipe",
                description="Espace superflu avant la barre verticale (|)",
                position=match.start(),
                original_text=match.group(0),
                suggested_text="|",
                severity="low"
            ))
        for match in self.SPACE_AFTER_PIPE.finditer(content):
            pos = match.start()
            if self._is_inside_template(content, pos):
                continue
            if self._is_inside_link(content, pos):
                continue
            if self._is_inside_voir_template(content, pos):
                continue
            if self._is_protected(pos):
                continue
            self.issues.append(Issue(
                issue_type="space_after_pipe",
                description="Espace superflu après la barre verticale (|)",
                position=match.start(),
                original_text=match.group(0),
                suggested_text="|",
                severity="low"
            ))

    def _detect_spaces_before_list_markers(self, content: str) -> None:
        for match in self.SPACE_BEFORE_LIST_MARKER.finditer(content):
            if self._is_protected(match.start()):
                continue
            self.issues.append(Issue(
                issue_type="space_before_list_marker",
                description="Espace superflu avant le marqueur de liste",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=match.group(1),
                severity="low"
            ))

    def _detect_spaces_around_html_tags(self, content: str) -> None:
        for match in self.SPACE_BEFORE_HTML_TAG.finditer(content):
            if self._is_in_opaque_block(match.start()):
                continue
            self.issues.append(Issue(
                issue_type="space_before_html_tag",
                description="Espace superflu avant la balise HTML",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=match.group(1),
                severity="low"
            ))
        for match in self.SPACE_AFTER_HTML_TAG.finditer(content):
            if self._is_in_opaque_block(match.start()):
                continue
            self.issues.append(Issue(
                issue_type="space_after_html_tag",
                description="Espace superflu après la balise HTML",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=match.group(1),
                severity="low"
            ))

    def _detect_spaces_around_comments(self, content: str) -> None:
        for match in self.SPACE_BEFORE_COMMENT.finditer(content):
            if self._is_in_opaque_block(match.start()):
                continue
            self.issues.append(Issue(
                issue_type="space_before_comment",
                description="Espace superflu avant le commentaire",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=match.group(1),
                severity="low"
            ))
        for match in self.SPACE_AFTER_COMMENT.finditer(content):
            if self._is_in_opaque_block(match.start()):
                continue
            self.issues.append(Issue(
                issue_type="space_after_comment",
                description="Espace superflu après le commentaire",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=match.group(1),
                severity="low"
            ))

    # ----- Additional heuristics (low severity) -----

    def _detect_spaces_before_units(self, content: str) -> None:
        """
        Suggest adding a space between number and unit (e.g., "10km" -> "10 km").

        Rewritten to stop mangling brand names, redirects, and filenames:
          - only matches a closed whitelist of real units (km, kg, mm, ...),
            never an arbitrary 1-3 letter suffix (this is what previously
            turned "8TV" into "8 TV" and "8tv" into "8 tv"),
          - requires a clean word boundary before the digits, so it can't
            fire mid-identifier,
          - skips anything inside a template or a link entirely,
          - skips anything that looks like a filename/extension.
        """
        for match in self.UNIT_PATTERN.finditer(content):
            pos = match.start()
            if self._is_inside_template(content, pos):
                continue
            if self._is_inside_link(content, pos):
                continue
            if self._is_protected(pos):
                continue
            if self._looks_like_filename(content, pos):
                continue
            self.issues.append(Issue(
                issue_type="missing_space_before_unit",
                description="Espace manquant entre le nombre et l'unité",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=match.group(1) + " " + match.group(2),
                severity="low"
            ))

    def _detect_spaces_around_quotes(self, content: str) -> None:
        if self.language == 'fr':
            quote_pattern = re.compile(r'«([^»]*)»')
            for match in quote_pattern.finditer(content):
                if self._is_protected(match.start()):
                    continue
                inner = match.group(1).strip()
                self.issues.append(Issue(
                    issue_type="guillemet_spacing",
                    description="Guillemets français : utiliser des espaces insécables à l'intérieur",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text="«\u00A0" + inner + "\u00A0»",
                    severity="low"
                ))

    # ------------------------------------------------------------------
    #   Helper: detect if position is inside [[...]] or {{...}}
    # ------------------------------------------------------------------

    def _is_inside_special_syntax(self, content: str, position: int) -> bool:
        open_brackets = 0
        open_braces = 0
        i = position - 1
        start = max(0, position - 500)
        while i >= start:
            ch = content[i]
            if ch == ']' and i > 0 and content[i - 1] == ']':
                open_brackets -= 1
                i -= 1
            elif ch == '[' and i > 0 and content[i - 1] == '[':
                open_brackets += 1
                i -= 1
            elif ch == '}' and i > 0 and content[i - 1] == '}':
                open_braces -= 1
                i -= 1
            elif ch == '{' and i > 0 and content[i - 1] == '{':
                open_braces += 1
                i -= 1
            i -= 1
        return open_brackets > 0 or open_braces > 0

    def get_analyzer_name(self) -> str:
        """Return the analyzer name."""
        return "WhitespaceAnalyzer"