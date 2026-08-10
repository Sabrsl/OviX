"""
Analyzer for HTML-related issues in Wikipedia articles.

Detects:
    - Unnecessary or deprecated HTML tags (should use wikicode)
    - Deprecated HTML attributes (e.g., border, align, valign, cellpadding, cellspacing)
    - HTML entities that could be replaced with Unicode characters
    - Unclosed or mismatched HTML tags (basic balancing)
    - Excessive line breaks (<br> repeated)
    - Inline styles that should be moved to CSS classes or templates
    - Misplaced HTML tags (e.g., <p> inside list items)
    - Outdated or potentially harmful HTML comments
    - Self-closing tags with space (e.g., <br />) – suggest <br/> or just <br>
    - Uppercase tags (should be lowercase)
    - Tags inside protected areas (nowiki, pre, etc.) are ignored

All checks are non-destructive and preserve the original detection logic.
Configurable allowed tags and severity levels.

---
CORRECTIFS DE SÉCURITÉ (auto-correction sans supervision) :

1. _ENTITY_TO_UNICODE : 'nbsp'/'emsp'/'ensp'/'thinsp' mappaient vers une
   espace ASCII au lieu du vrai caractère Unicode d'espace — corrigé.
   Les entités 'lt'/'gt'/'amp'/'quot'/'apos' sont retirées du mapping
   auto-remplaçable : ce sont des caractères réservés HTML/wiki, jamais
   sûrs à décoder aveuglément.

2. _detect_html_entities : les entités numériques (&#124; etc.) ne sont
   plus auto-corrigées si le caractère décodé est un caractère
   syntaxiquement actif en wikicode (| { } [ ] = < > & " '), car une
   entité numérique encodant ces caractères est probablement intentionnelle
   (échapper le parseur MediaWiki, ex. dans un paramètre de modèle).

3. _detect_case_issues : le remplacement de casse était fait par
   `tag_text.replace(tag_name, tag_name.lower())`, une substitution GLOBALE
   sur toute la balise. Si un attribut contenait la même chaîne que le nom
   de balise (ex. <DIV title="DIV">), la correction corrompait aussi
   l'attribut. Remplacé par une correction positionnelle ciblée sur le nom
   de balise uniquement.

4. _detect_unnecessary_html :
   - Les balises avec attributs (ex. <span style="color:red">) ne sont plus
     auto-remplacées par leur équivalent nu (perte de données) —
     suggested_text=None, sévérité relevée à "medium", signalement pour
     revue manuelle uniquement.
   - <br>/<hr> ne sont plus auto-remplacés s'ils sont probablement à
     l'intérieur d'un paramètre de modèle ({{...}}), où <br> est une
     convention wiki standard et où le remplacer par '\\n' casserait la
     syntaxe du modèle. Détection heuristique via comptage de profondeur
     d'accolades sur une fenêtre de contexte avant la position.
---
"""

import re
import logging
from typing import List, Dict, Set, Optional, Tuple, Pattern, Any
from dataclasses import dataclass, field
from .base import BaseAnalyzer, Issue

logger = logging.getLogger(__name__)


@dataclass
class HTMLAnalyzerConfig:
    """Configuration for HTMLAnalyzer."""
    check_unnecessary_tags: bool = True
    check_deprecated_attributes: bool = True
    check_entities: bool = True
    check_unclosed_tags: bool = True
    check_line_breaks: bool = True
    check_inline_styles: bool = True
    check_comments: bool = True
    check_case: bool = True
    check_misplaced_tags: bool = False  # NOTE: non implémenté, voir _detect_misplaced_tags (no-op)

    # Tags that are considered legitimate and should not be flagged
    allowed_tags: Set[str] = field(default_factory=lambda: {
        'ref', 'references', 'gallery', 'math', 'score', 'nowiki', 'pre',
        'syntaxhighlight', 'source', 'includeonly', 'noinclude', 'onlyinclude',
        'translate', 'languages', 'indicator', 'inputbox', 'imagemap',
        'poem', 'timeline', 'graph', 'mapframe', 'maplink'
    })

    # Tags that are allowed but may be flagged for specific issues (e.g., <br>)
    # These are not in allowed_tags because we still want to check them.
    # But we can exempt certain attributes or patterns.
    # We'll handle per-check.


class HTMLAnalyzer(BaseAnalyzer):
    """
    Analyzes articles for HTML-related issues with comprehensive checks.
    """

    # ---- Precompiled patterns ----
    # HTML tag pattern (self-closing or opening/closing)
    _HTML_TAG_RE = re.compile(r'<([/]?)([a-zA-Z][a-zA-Z0-9]*)\s*([^>]*)>')

    # HTML comment pattern
    _COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)

    # HTML entity pattern (e.g., &nbsp;, &eacute;)
    _ENTITY_RE = re.compile(r'&([a-zA-Z]+|#[0-9]+|#x[0-9a-fA-F]+);')

    # Inline style pattern inside style attribute (supports both single and double quotes)
    _STYLE_ATTR_RE = re.compile(r'style\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.IGNORECASE)

    # Deprecated attributes (common in old wikitext)
    _DEPRECATED_ATTRS = {
        'border', 'align', 'valign', 'cellpadding', 'cellspacing',
        'bgcolor', 'background', 'width', 'height', 'nowrap',
        'clear', 'hspace', 'vspace', 'frame', 'rules', 'summary'
    }

    # Mapping of HTML entities to Unicode characters (common ones).
    # CORRIGÉ : nbsp/emsp/ensp/thinsp utilisent les vrais caractères Unicode
    # d'espace (pas une espace ASCII), et lt/gt/amp/quot/apos sont retirés
    # (caractères réservés HTML/wiki, jamais sûrs à auto-décoder).
    _ENTITY_TO_UNICODE = {
        'nbsp': '\u00A0',
        'ndash': '–',
        'mdash': '—',
        'lsquo': '‘',
        'rsquo': '’',
        'sbquo': '‚',
        'ldquo': '“',
        'rdquo': '”',
        'bdquo': '„',
        'hellip': '…',
        'permil': '‰',
        'copy': '©',
        'reg': '®',
        'euro': '€',
        'yen': '¥',
        'pound': '£',
        'sect': '§',
        'deg': '°',
        'plusmn': '±',
        'times': '×',
        'divide': '÷',
        'laquo': '«',
        'raquo': '»',
        'emsp': '\u2003',
        'ensp': '\u2002',
        'thinsp': '\u2009',
        'zwnj': '\u200C',
        'zwj': '\u200D',
        'lrm': '\u200E',
        'rlm': '\u200F',
    }

    # Caractères syntaxiquement actifs en wikicode / HTML : ne jamais les
    # auto-décoder depuis une entité numérique, l'encodage est probablement
    # intentionnel (échapper le parseur MediaWiki, ex. dans un paramètre de
    # modèle : {{Ouvrage|titre=Un &#124; deux}}).
    _WIKI_RESERVED_CHARS = {'|', '{', '}', '[', ']', '=', '<', '>', '&', '"', "'"}

    # Tags that are often misused and should be replaced with wikicode
    _UNNECESSARY_TAG_MAP = {
        'b': ("'''", "'''"),          # opening and closing
        'strong': ("'''", "'''"),
        'i': ("''", "''"),
        'em': ("''", "''"),
        # 'u': retiré - no-op, pas de remplacement réel implémenté
        'strike': ('<s>', '</s>'),    # use <s> or {{suppression}}
        # 's': retiré - déjà la forme recommandée, no-op inutile
        'del': ('<del>', '</del>'),   # use <del>
        'ins': ('<ins>', '</ins>'),   # use <ins>
        'big': ('<big>', '</big>'),   # discouraged; use {{grand}}
        # 'small': retiré - usage contextuel (notes, légendes), pas d'auto-correction
        # 'span': retiré - usage légitime avec style, pas d'auto-correction
        # 'center': retiré - contextuel, peut casser les tableaux, nécessite révision manuelle
        # 'font': retiré - no-op, pas de remplacement réel implémenté
        # 'div': retiré - usage contextuel (layout), pas d'auto-correction
        # 'p': retiré - risqué dans tableaux/infobox, nécessite révision manuelle
        'br': ('\n', None),           # replace with newline (hors tableaux/modèles)
        'hr': ('----', None),         # replace with horizontal rule wikicode (hors tableaux/modèles)
    }

    # Tags that are allowed but we might check for certain issues (like empty)
    # For 'br' we check repeated ones.
    # For 'table', we check deprecated attributes.

    def __init__(self, config: Optional[HTMLAnalyzerConfig] = None):
        super().__init__()
        self.config = config or HTMLAnalyzerConfig()

    def analyze(self, content: str) -> List[Issue]:
        """Analyze content for HTML issues."""
        self.clear_issues()
        if not content:
            return self.issues

        # Build protected mask (skip nowiki, pre, comments, etc.)
        mask = self._build_protected_mask(content)

        # ---- Existing checks (preserved and enhanced) ----
        if self.config.check_unnecessary_tags:
            self._detect_unnecessary_html(content, mask)

        if self.config.check_comments:
            self._detect_html_comments(content, mask)

        # ---- New checks ----
        if self.config.check_deprecated_attributes:
            self._detect_deprecated_attributes(content, mask)

        if self.config.check_entities:
            self._detect_html_entities(content, mask)

        if self.config.check_unclosed_tags:
            self._detect_unclosed_tags(content, mask)

        if self.config.check_line_breaks:
            self._detect_excessive_line_breaks(content, mask)

        if self.config.check_inline_styles:
            self._detect_inline_styles(content, mask)

        if self.config.check_case:
            self._detect_case_issues(content, mask)

        if self.config.check_misplaced_tags:
            self._detect_misplaced_tags(content, mask)

        # Sort issues
        self.issues.sort(key=lambda i: i.position)
        return self.issues

    def get_analyzer_name(self) -> str:
        return "HTMLAnalyzer"

    # ------------------------------------------------------------------
    # Protected mask builder (similar to other analyzers)
    # ------------------------------------------------------------------

    def _build_protected_mask(self, content: str) -> List[bool]:
        """Mark areas that should be ignored (nowiki, pre, comments, etc.)."""
        mask = [False] * len(content)
        patterns = [
            r'<nowiki>.*?</nowiki>',
            r'<pre>.*?</pre>',
            r'<syntaxhighlight[^>]*>.*?</syntaxhighlight>',
            r'<source[^>]*>.*?</source>',
            r'<math[^>]*>.*?</math>',
            r'<!--.*?-->',
        ]
        combined = re.compile('|'.join(patterns), re.IGNORECASE | re.DOTALL)
        for match in combined.finditer(content):
            for i in range(match.start(), match.end()):
                mask[i] = True
        return mask

    def _is_protected(self, mask: List[bool], pos: int) -> bool:
        """Check if a position is inside a protected area."""
        return pos < len(mask) and mask[pos]

    def _is_inside_template(self, content: str, pos: int, lookback: int = 2000) -> bool:
        """
        Heuristique : compte la profondeur d'accolades {{ / }} non fermées
        dans une fenêtre de contexte avant `pos` pour détecter si on est
        probablement à l'intérieur d'un paramètre de modèle. Utilisé pour
        éviter de casser la syntaxe d'un modèle en remplaçant un <br> par
        un saut de ligne littéral.

        NOTE : heuristique approximative (lookback limité), peut manquer
        des ouvertures de modèle très éloignées (>2000 caractères).
        """
        window = content[max(0, pos - lookback):pos]
        depth = 0
        i = 0
        n = len(window)
        while i < n - 1:
            two = window[i:i + 2]
            if two == '{{':
                depth += 1
                i += 2
            elif two == '}}':
                depth = max(0, depth - 1)
                i += 2
            else:
                i += 1
        return depth > 0

    def _is_inside_table(self, content: str, pos: int, lookback: int = 1000) -> bool:
        """
        Heuristique approximative : détecte si une position est à l'intérieur
        d'un tableau wikicode ({| ... |}) en comptant les {| non fermés avant
        la position.

        NOTE : heuristique approximative, ne gère pas les tableaux imbriqués
        correctement et peut matcher des séquences accidentelles {| qui ne
        sont pas des débuts de tableau. À utiliser comme indicateur, pas comme
        garantie fiable.
        """
        window = content[max(0, pos - lookback):pos]
        # Compter les {| non fermés
        table_open_count = window.count('{|')
        # Compter les |} fermés
        table_close_count = window.count('|}')
        return table_open_count > table_close_count

    # ------------------------------------------------------------------
    # Existing methods (preserved and enhanced)
    # ------------------------------------------------------------------

    def _detect_unnecessary_html(self, content: str, mask: List[bool]) -> None:
        """
        Detect unnecessary HTML tags that should use wikicode.
        Uses a mapping and suggests replacements.

        CORRIGÉ :
        - <br>/<hr> : pas de suggestion auto si probablement dans un modèle
          ({{...}}), où <br> est une convention wiki standard et où le
          remplacement casserait la syntaxe.
        - Balises avec attributs (ex. <span style="...">) : plus de
          remplacement par la version nue (perte de données) ; signalement
          seul, sévérité "medium".
        """
        for tag, (opening_suggestion, closing_suggestion) in self._UNNECESSARY_TAG_MAP.items():
            if tag in ('br', 'hr'):
                pattern = re.compile(r'<' + re.escape(tag) + r'\s*/?\s*>', re.IGNORECASE)
                for match in pattern.finditer(content):
                    if self._is_protected(mask, match.start()):
                        continue
                    if tag in self.config.allowed_tags:
                        continue
                    in_template = self._is_inside_template(content, match.start())
                    in_table = self._is_inside_table(content, match.start())
                    # Pas de correction auto dans tableaux ou modèles
                    should_skip = in_template or in_table
                    self.issues.append(Issue(
                        issue_type="unnecessary_html",
                        description=f"Balise HTML inutile ou déconseillée : <{tag}>" + (
                            " (dans un modèle ou tableau, à vérifier manuellement)" if should_skip else ""
                        ),
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=None if should_skip else opening_suggestion,
                        severity="medium" if should_skip else "low"
                    ))
            else:
                # Opening tag — capture attrs pour détecter leur présence
                open_pattern = re.compile(r'<' + re.escape(tag) + r'\b([^>]*)>', re.IGNORECASE)
                for match in open_pattern.finditer(content):
                    if self._is_protected(mask, match.start()):
                        continue
                    if tag in self.config.allowed_tags:
                        continue
                    attrs = (match.group(1) or "").strip()
                    has_attrs = bool(attrs) and attrs != '/'
                    self.issues.append(Issue(
                        issue_type="unnecessary_html",
                        description=f"Balise HTML inutile ou déconseillée : <{tag}>" + (
                            " (avec attributs, à vérifier manuellement)" if has_attrs else ""
                        ),
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=None if has_attrs else opening_suggestion,
                        severity="medium" if has_attrs else "low"
                    ))
                # Closing tag (jamais d'attributs, suggestion inchangée)
                close_pattern = re.compile(r'</' + re.escape(tag) + r'\s*>', re.IGNORECASE)
                for match in close_pattern.finditer(content):
                    if self._is_protected(mask, match.start()):
                        continue
                    if tag in self.config.allowed_tags:
                        continue
                    self.issues.append(Issue(
                        issue_type="unnecessary_html",
                        description=f"Balise HTML inutile ou déconseillée : </{tag}>",
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=closing_suggestion,
                        severity="low"
                    ))

    def _detect_html_comments(self, content: str, mask: List[bool]) -> None:
        """
        Detect HTML comments and flag them for review.
        Enhanced to differentiate between useful comments and potentially outdated ones.
        """
        for match in self._COMMENT_RE.finditer(content):
            if self._is_protected(mask, match.start()):
                continue
            comment = match.group(0)
            self.issues.append(Issue(
                issue_type="html_comment",
                description="Commentaire HTML (à vérifier)",
                position=match.start(),
                original_text=comment[:100],
                suggested_text=None,
                severity="low"
            ))

    # ------------------------------------------------------------------
    # New detection methods
    # ------------------------------------------------------------------

    def _detect_deprecated_attributes(self, content: str, mask: List[bool]) -> None:
        """
        Detect deprecated HTML attributes (border, align, etc.) and suggest removal or replacement.
        """
        for match in self._HTML_TAG_RE.finditer(content):
            if self._is_protected(mask, match.start()):
                continue
            closing = match.group(1)  # '/' if closing tag
            tag_name = match.group(2).lower()
            attrs = match.group(3)
            if closing:
                continue  # closing tags have no attributes

            if tag_name in self.config.allowed_tags:
                continue

            attr_pattern = re.compile(r'([a-zA-Z][a-zA-Z0-9-]*)\s*=', re.IGNORECASE)
            for attr_match in attr_pattern.finditer(attrs):
                attr_name = attr_match.group(1).lower()
                if attr_name in self._DEPRECATED_ATTRS:
                    self.issues.append(Issue(
                        issue_type="deprecated_html_attribute",
                        description=f"Attribut HTML déprécié : {attr_name}",
                        position=match.start() + attr_match.start(),
                        original_text=attr_match.group(0),
                        suggested_text=None,  # often needs manual fix
                        severity="low"
                    ))

    def _detect_html_entities(self, content: str, mask: List[bool]) -> None:
        """
        Detect HTML entities and suggest Unicode equivalents for common ones.

        CORRIGÉ : les entités numériques décodant vers un caractère
        syntaxiquement actif en wikicode (| { } [ ] = < > & " ') ne sont
        plus auto-suggérées — l'encodage est probablement intentionnel.
        """
        for match in self._ENTITY_RE.finditer(content):
            if self._is_protected(mask, match.start()):
                continue
            entity = match.group(0)
            code = match.group(1)
            if code.startswith('#'):
                try:
                    if code.startswith('#x'):
                        num = int(code[2:], 16)
                    else:
                        num = int(code[1:])
                    if 0x20 <= num <= 0x10FFFF:
                        char = chr(num)
                        if char != entity and char not in self._WIKI_RESERVED_CHARS:
                            self.issues.append(Issue(
                                issue_type="html_entity",
                                description=f"Entité HTML {entity} peut être remplacée par '{char}'",
                                position=match.start(),
                                original_text=entity,
                                suggested_text=char,
                                severity="low"
                            ))
                        elif char in self._WIKI_RESERVED_CHARS:
                            self.issues.append(Issue(
                                issue_type="html_entity",
                                description=f"Entité HTML {entity} encode un caractère réservé au wikicode ('{char}') : probablement intentionnel, à vérifier manuellement",
                                position=match.start(),
                                original_text=entity,
                                suggested_text=None,
                                severity="low"
                            ))
                except (ValueError, OverflowError):
                    pass
            else:
                if code in self._ENTITY_TO_UNICODE:
                    char = self._ENTITY_TO_UNICODE[code]
                    
                    # Pour nbsp, vérifier si on est dans un tableau
                    # Dans les tableaux, &nbsp; est souvent utilisé pour le padding visuel
                    # et ne doit pas être remplacé automatiquement
                    if code == 'nbsp' and self._is_inside_table(content, match.start()):
                        continue
                    
                    # Pour nbsp, afficher explicitement \u00A0 pour clarifier l'espace insécable
                    display_char = char if code != 'nbsp' else '\\u00A0 (espace insécable)'
                    self.issues.append(Issue(
                        issue_type="html_entity",
                        description=f"Entité HTML {entity} peut être remplacée par '{display_char}'",
                        position=match.start(),
                        original_text=entity,
                        suggested_text=char,
                        severity="low"
                    ))

    def _detect_unclosed_tags(self, content: str, mask: List[bool]) -> None:
        """
        Basic detection of unclosed or mismatched tags using a stack.
        Only for non-self-closing tags.

        CORRIGÉ : les tags listés dans allowed_tags (ref, gallery, math,
        poem, etc.) sont désormais exclus du suivi de balancement, comme
        c'est déjà le cas dans _detect_unnecessary_html et
        _detect_deprecated_attributes. Sans cette exclusion, ces balises
        wiki légitimes pouvaient être signalées à tort comme mal
        balancées.
        """
        stack: List[Tuple[str, int]] = []  # (tag_name, start_pos)
        for match in self._HTML_TAG_RE.finditer(content):
            if self._is_protected(mask, match.start()):
                continue
            closing = match.group(1)  # '/' if closing
            tag_name = match.group(2).lower()
            attrs = match.group(3)
            if attrs.rstrip().endswith('/'):
                continue
            void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                         'link', 'meta', 'param', 'source', 'track', 'wbr'}
            if tag_name in void_tags:
                continue
            if tag_name in self.config.allowed_tags:
                continue

            if not closing:
                stack.append((tag_name, match.start()))
            else:
                if not stack:
                    self.issues.append(Issue(
                        issue_type="unmatched_closing_tag",
                        description=f"Balise fermante sans ouverture correspondante : </{tag_name}>",
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="medium"
                    ))
                    continue
                last_open, open_pos = stack.pop()
                if last_open != tag_name:
                    self.issues.append(Issue(
                        issue_type="mismatched_tag",
                        description=f"Balises déséquilibrées : <{last_open}> ouvert, fermé par </{tag_name}>",
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="medium"
                    ))
                    stack.append((last_open, open_pos))

        for tag, pos in stack:
            self.issues.append(Issue(
                issue_type="unclosed_tag",
                description=f"Balise ouvrante non refermée : <{tag}>",
                position=pos,
                original_text=f"<{tag}>",
                suggested_text=None,
                severity="medium"
            ))

    def _detect_excessive_line_breaks(self, content: str, mask: List[bool]) -> None:
        """
        Detect multiple consecutive <br> tags and suggest using line breaks or templates.
        """
        pattern = re.compile(r'(<br\s*/?\s*>\s*){3,}', re.IGNORECASE)
        for match in pattern.finditer(content):
            if self._is_protected(mask, match.start()):
                continue
            self.issues.append(Issue(
                issue_type="excessive_line_breaks",
                description="Nombre excessif de balises <br> consécutives (utiliser un saut de ligne ou un modèle)",
                position=match.start(),
                original_text=match.group(0)[:50],
                suggested_text=None,
                severity="low"
            ))

    def _detect_inline_styles(self, content: str, mask: List[bool]) -> None:
        """
        Detect inline style attributes and suggest moving to CSS classes or templates.
        """
        for match in self._STYLE_ATTR_RE.finditer(content):
            if self._is_protected(mask, match.start()):
                continue
            style_value = match.group(1)
            if any(k in style_value.lower() for k in ['font-size', 'color', 'background', 'margin', 'padding', 'text-align']):
                self.issues.append(Issue(
                    issue_type="inline_style",
                    description="Style inline utilisé ; préférer une classe CSS ou un modèle",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=None,
                    severity="low"
                ))

    def _detect_case_issues(self, content: str, mask: List[bool]) -> None:
        """
        Detect uppercase HTML tags and suggest lowercase.

        CORRIGÉ : le remplacement était fait par
        `tag_text.replace(tag_name, tag_name.lower())`, une substitution
        GLOBALE sur toute la chaîne de la balise. Si un attribut contenait
        la même chaîne que le nom de balise (ex. <DIV title="DIV">), la
        correction corrompait aussi l'attribut. Remplacé par une correction
        positionnelle ciblée uniquement sur le nom de balise capturé.
        """
        pattern = re.compile(r'<[^>]*>')
        for match in pattern.finditer(content):
            if self._is_protected(mask, match.start()):
                continue
            tag_text = match.group(0)
            tag_match = re.match(r'<([/]?)([a-zA-Z][a-zA-Z0-9]*)', tag_text)
            if not tag_match:
                continue
            tag_name = tag_match.group(2)
            if tag_name != tag_name.lower():
                start, end = tag_match.span(2)
                corrected = tag_text[:start] + tag_name.lower() + tag_text[end:]
                self.issues.append(Issue(
                    issue_type="uppercase_html_tag",
                    description=f"Balise HTML en majuscules : {tag_name}",
                    position=match.start(),
                    original_text=tag_text,
                    suggested_text=corrected,
                    severity="low"
                ))

    def _detect_misplaced_tags(self, content: str, mask: List[bool]) -> None:
        """
        Detect misplaced tags, e.g., <p> inside list items, <div> inside <p>, etc.

        NOTE : non implémenté (no-op), hérité du fichier d'origine. Laisser
        `check_misplaced_tags=False` dans la config tant qu'aucune logique
        n'est ajoutée ici, pour éviter toute confusion sur ce que ce check
        est censé faire.
        """
        pass