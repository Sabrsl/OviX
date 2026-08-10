"""Patterns regex pour l'analyseur typographique."""

import re
from typing import List

# ---------------------------------------------------------------------------
# Masquage du wikicode non pertinent
# ---------------------------------------------------------------------------

_PROTECTED_INLINE_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"<nowiki\b[^>]*>.*?</nowiki>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<nowiki\b[^>]*/>", re.IGNORECASE),
    re.compile(r"<pre\b[^>]*>.*?</pre>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<source\b[^>]*>.*?</source>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<syntaxhighlight\b[^>]*>.*?</syntaxhighlight>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<math\b[^>]*>.*?</math>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<chem\b[^>]*>.*?</chem>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<ce\b[^>]*>.*?</ce>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<code\b[^>]*>.*?</code>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<gallery\b[^>]*>.*?</gallery>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<timeline\b[^>]*>.*?</timeline>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<score\b[^>]*>.*?</score>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<templatedata\b[^>]*>.*?</templatedata>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<imagemap\b[^>]*>.*?</imagemap>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<inputbox\b[^>]*>.*?</inputbox>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<graph\b[^>]*>.*?</graph>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<mapframe\b[^>]*/>", re.IGNORECASE),
    re.compile(r"<mapframe\b[^>]*>.*?</mapframe>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<templatestyles\b[^>]*/>", re.IGNORECASE),
    re.compile(r"<references\b[^>]*/>", re.IGNORECASE),
    re.compile(r"<references\b[^>]*>.*?</references>", re.IGNORECASE | re.DOTALL),
    re.compile(r"<ref\b[^>]*/>", re.IGNORECASE),
    re.compile(r"<ref\b[^>]*>.*?</ref>", re.IGNORECASE | re.DOTALL),
    re.compile(r"\[https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+(?:\s[^\]]*)?\]", re.IGNORECASE),
    re.compile(r"https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+", re.IGNORECASE),
    # Masquer les attributs HTML et paramètres de template (style=, class=, rowspan=, colspan=, etc.)
    re.compile(r'\b[a-zA-Z_-]+=(?:"[^"]*"|\'[^\']*\')', re.IGNORECASE),
    # Masquer les paramètres de template wikicode (paramètre=valeur) - permet les liens dans les valeurs
    re.compile(r'\|\s*[a-zA-Z_-]+\s*=\s*[^|\}]*\[\[[^\]]+\]\][^|\}]*', re.IGNORECASE),
    re.compile(r'\|\s*[a-zA-Z_-]+\s*=\s*[^|\}]+', re.IGNORECASE),
    # Masquer les lignes de tableaux wikicode (commençant par | ou !)
    re.compile(r'^[|!].*$', re.MULTILINE),
    # Masquer les lignes avec paramètres de tableaux HTML
    re.compile(r'^\s*\{\|.*$', re.MULTILINE),
    re.compile(r'^\s*\|\}.*$', re.MULTILINE),
]

_TECHNICAL_NAMESPACES = re.compile(
    r"^\s*(cat[ée]gorie|category|fichier|file|image|m[ée]dia|media)\s*:",
    re.IGNORECASE,
)

_GENERIC_TAG_RE = re.compile(r"</?[a-zA-Z][\w:-]*(?:\s+[^<>]*?)?\s*/?>")

# ---------------------------------------------------------------------------
# Tableaux
# ---------------------------------------------------------------------------

TABLE_START_RE = re.compile(r"{\|")
TABLE_END_RE = re.compile(r"\|}")
TABLE_ROW_SEP_RE = re.compile(r"\|-")
TABLE_MARKER_RE = re.compile(r"!")
TABLE_ATTR_RE = re.compile(r"\|\+")

# ---------------------------------------------------------------------------
# Ordinaux
# ---------------------------------------------------------------------------

ORDINAL_ABBREVIATION_RE = re.compile(r"\b(\d+)(?:ère|ere|ème|eme)(s?)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

DATE_NUMERIC_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
DATE_NUMERIC_DASH_RE = re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b")

# ---------------------------------------------------------------------------
# Gras et italique
# ---------------------------------------------------------------------------

# Gras+italique combiné ('''''texte''''', 5 apostrophes) : traité en priorité
# pour éviter que BOLD_PATTERN/ITALIC_PATTERN ne le comptent en double ou de
# façon incohérente dans detect_abusive_bold_italic.
BOLD_ITALIC_PATTERN = re.compile(r"'''''[^']{1,}'''''")
BOLD_PATTERN = re.compile(r"'''[^']{3,}'''")
ITALIC_PATTERN = re.compile(r"''[^']{2,}''")
BOLD_SHORT_PATTERN = re.compile(r"'''[^']{1,}'''")

# ---------------------------------------------------------------------------
# Sections et prix
# ---------------------------------------------------------------------------

SECTION_PATTERN = re.compile(r"^(={1,6})\s*(.+?)\s*\1$", re.MULTILINE)

# ---------------------------------------------------------------------------
# Typographie - espaces et ponctuation
# ---------------------------------------------------------------------------

DOUBLE_SPACE_PATTERN = re.compile(r'  +')
TRAILING_SPACE_PATTERN = re.compile(r' +$')
MULTIPLE_BLANK_LINES_PATTERN = re.compile(r'\n{3,}')
PUNCTUATION_SPACING_PATTERN = re.compile(r'(\S)([:;?!])')

# ---------------------------------------------------------------------------
# Typographie - guillemets et intervalles
# ---------------------------------------------------------------------------

FRENCH_QUOTES_PATTERN = re.compile(r'(?<!\')"([^"=<>{}\|\n\']{1,500})"(?!\')')
NUMERIC_INTERVAL_PATTERN = re.compile(r'(\d+)\s+-\s+(\d+)')
PERCENT_SPACING_PATTERN = re.compile(r'(\d)%')

# ---------------------------------------------------------------------------
# Typographie - catégories
# ---------------------------------------------------------------------------

CATEGORY_PATTERN = re.compile(r'\[\[\s*(?:Cat[ée]gorie|Category)\s*:\s*([^\]|]+?)(?:\s*\|[^\]]*)?\s*\]\]', re.IGNORECASE)

# ---------------------------------------------------------------------------
# Typographie - degré
# ---------------------------------------------------------------------------

DEGREE_ALONE_PATTERN = re.compile(r'(\d)°\b')

# ---------------------------------------------------------------------------
# Protection patterns
# ---------------------------------------------------------------------------

TEMPLATE_COLON_PATTERN = re.compile(r'\{\{[A-Za-z0-9_]+\s*:')
HTML_ATTR_PATTERN = re.compile(r'\b[a-zA-Z_-]+\s*=\s*"[^"]*"')
TEMPLATE_PARAM_PATTERN = re.compile(r'\|\s*[a-zA-Z_-]+\s*=')
AWARDS_PATTERN = re.compile(r"\{\{Prix\b[^}]*\}\}")