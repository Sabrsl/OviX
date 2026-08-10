"""Fonctions utilitaires pour l'analyseur typographique."""

import re
from typing import List, Tuple

MASK_CHAR = "\u2063"  # séparateur invisible : ne matche jamais \w ni la ponctuation


def find_balanced_spans(text: str, open_tok: str, close_tok: str) -> List[Tuple[int, int]]:
    """Repère les paires équilibrées open_tok/close_tok, imbrication comprise.

    Ne renvoie que les portées les plus externes : une portée interne
    (modèle ou lien imbriqué) est de toute façon couverte par le masquage
    de la portée qui l'englobe.
    """
    spans: List[Tuple[int, int]] = []
    stack: List[int] = []
    i, n = 0, len(text)
    ol, cl = len(open_tok), len(close_tok)
    while i < n:
        if text.startswith(open_tok, i):
            stack.append(i)
            i += ol
        elif text.startswith(close_tok, i):
            if stack:
                start = stack.pop()
                if not stack:
                    spans.append((start, i + cl))
            i += cl
        else:
            i += 1
    return spans


def mask_table_syntax(text: str) -> str:
    """Masque la syntaxe des tableaux wikicode."""
    buf = list(text)
    
    def fill(a: int, b: int) -> None:
        for i in range(a, b):
            buf[i] = MASK_CHAR
    
    from .typography_patterns import (
        TABLE_START_RE, TABLE_END_RE, TABLE_ROW_SEP_RE,
        TABLE_MARKER_RE, TABLE_ATTR_RE
    )
    
    for m in TABLE_START_RE.finditer(text):
        fill(m.start(), m.end())
    for m in TABLE_END_RE.finditer(text):
        fill(m.start(), m.end())
    for m in TABLE_ROW_SEP_RE.finditer(text):
        fill(m.start(), m.end())
    for m in TABLE_MARKER_RE.finditer(text):
        fill(m.start(), m.end())
    for m in TABLE_ATTR_RE.finditer(text):
        fill(m.start(), m.end())
    
    return "".join(buf)


def mask_content(text: str) -> str:
    """Masque le contenu wikicode non pertinent pour l'analyse typographique."""
    buf = list(text)
    
    def fill(a: int, b: int) -> None:
        for i in range(a, b):
            buf[i] = MASK_CHAR
    
    from .typography_patterns import (
        _PROTECTED_INLINE_PATTERNS, _GENERIC_TAG_RE, _TECHNICAL_NAMESPACES
    )
    
    # PRIORITÉ HAUTE : Masquer les graphiques Wikipédia (Timeline, Chart, etc.)
    # Ces zones utilisent une syntaxe spéciale avec : qui ne doit pas être modifiée
    
    # Masquer les modèles de graphique
    graph_patterns = [
        r'\{\{[Tt]imeline[^\}]*\}\}.*?\{\{[Ee]nd[^\}]*\}\}',  # Timeline blocks
        r'\{\{[Cc]hart[^\}]*\}\}.*?\{\{[Ee]nd[^\}]*\}\}',    # Chart blocks
        r'\{\{[Gg]raph[^\}]*\}\}.*?\{\{[Ee]nd[^\}]*\}\}',    # Graph blocks
        r'\{\{[Pp]lot[^\}]*\}\}.*?\{\{[Ee]nd[^\}]*\}\}',     # Plot blocks
    ]
    
    for pattern in graph_patterns:
        graph_re = re.compile(pattern, re.DOTALL | re.IGNORECASE)
        for m in graph_re.finditer(text):
            fill(m.start(), m.end())
    
    # Masquer la syntaxe directe de graphiques (sans modèles)
    # Protège les sections qui ressemblent à des paramètres de graphique
    # comme "TimeAxis =", "Colors =", "PlotData =", etc.
    graph_section_pattern = re.compile(
        r'^(TimeAxis|Colors|Legend|BackgroundColors|ScaleMajor|ScaleMinor|LineData|BarData|PlotData)\s*=',
        re.MULTILINE | re.IGNORECASE
    )
    
    # Quand on trouve une section de graphique, masquer tout jusqu'à la prochaine section de même niveau
    for m in graph_section_pattern.finditer(text):
        section_start = m.start()
        # Chercher la fin de cette section (prochaine ligne qui commence par un mot clé de section ou fin du texte)
        section_end = len(text)
        next_section = graph_section_pattern.search(text, m.end())
        if next_section:
            section_end = next_section.start()
        else:
            # Sinon, chercher jusqu'à la fin du fichier ou un modèle
            template_start = text.find('{{', m.end())
            if template_start != -1:
                section_end = template_start
        
        fill(section_start, section_end)
    
    # Masquer également les lignes de données de graphique (commençant par bar:, at:, etc.)
    # Ceci est une protection supplémentaire pour les cas où les sections ne sont pas détectées
    graph_data_pattern = re.compile(
        r'^(bar|at|text|color|layer|width|textcolor|align|anchor|shift|value|legend|orientation|position|increment|start)\s*:',
        re.MULTILINE | re.IGNORECASE
    )
    for m in graph_data_pattern.finditer(text):
        line_start = m.start()
        line_end = text.find('\n', line_start)
        if line_end == -1:
            line_end = len(text)
        fill(line_start, line_end)
    
    # PRIORITÉ HAUTE : Masquer les liens techniques (Fichier:, Image:, etc.) en premier
    # Approche agressive : tout ce qui commence par [[Fichier: ou [[Image: est masqué complètement
    technical_link_pattern = re.compile(r'\[\[(?:Fichier|File|Image|image)\s*:', re.IGNORECASE)
    for m in technical_link_pattern.finditer(text):
        # Trouver la fin du lien avec ]] équilibré
        link_start = m.start()
        # Chercher le ]] correspondant en gérant l'imbrication
        depth = 0
        i = link_start
        found_end = False
        while i < len(text):
            if text[i:i+2] == '[[':
                depth += 1
                i += 2
            elif text[i:i+2] == ']]':
                depth -= 1
                if depth == 0:
                    fill(link_start, i + 2)
                    found_end = True
                    break
                i += 2
            else:
                i += 1
    
    # Masquer les liens internes standards (avec détection technique améliorée)
    for start, end in find_balanced_spans("".join(buf), "[[", "]]"):
        inner_start, inner_end = start + 2, end - 2
        inner = "".join(buf[inner_start:inner_end])
        
        if _TECHNICAL_NAMESPACES.match(inner):
            # Masquer complètement les liens techniques (Fichier:, Image:, etc.)
            fill(start, end)
        elif "|" in inner:
            # Pour les liens non techniques, masquer seulement l'alias de tri
            pipe_idx = inner.index("|")
            fill(start, start + 2 + pipe_idx)
        else:
            fill(start, end)
    
    # Masquer les autres patterns protégés
    for pattern in _PROTECTED_INLINE_PATTERNS:
        snapshot = "".join(buf)
        for m in pattern.finditer(snapshot):
            fill(m.start(), m.end())
    
    # Masquer spécifiquement les templates sensibles avec compteur de profondeur.
    # NB : chaque pattern doit matcher jusqu'au "|" inclus pour que
    # find_balanced_spans démarre bien sur le "{{" du template repéré.
    _sensitive_template_patterns = [
        re.compile(r'\{\{lang\s*\|', re.IGNORECASE),
        # {{lang-xx|...}} / {{lang-xxx|...}} : code langue requis avant le "|".
        # L'ancienne entrée 'lang-' (sans code langue) ne matchait jamais
        # {{lang-en|...}} — corrigé ici.
        re.compile(r'\{\{lang-[a-z]{2,3}\s*\|', re.IGNORECASE),
        re.compile(r'\{\{Lien\s*\|', re.IGNORECASE),
        re.compile(r'\{\{Prix\s*\|', re.IGNORECASE),
        re.compile(r'\{\{w\s*\|', re.IGNORECASE),
        re.compile(r'\{\{wikipedia\s*\|', re.IGNORECASE),
    ]
    current_text = "".join(buf)
    
    for pattern in _sensitive_template_patterns:
        for match in pattern.finditer(current_text):
            start = match.start()
            # Trouver la fin équilibrée en utilisant find_balanced_spans
            spans = find_balanced_spans(current_text[start:], '{{', '}}')
            if spans:
                # Le premier span est le plus externe
                first_span = spans[0]
                end = start + first_span[1]
                fill(start, end)
                # Mettre à jour current_text après modification
                current_text = "".join(buf)
    
    # Masquer les modèles généraux (pas déjà masqués)
    for start, end in find_balanced_spans("".join(buf), "{{", "}}"):
        # Vérifier si cette zone n'est pas déjà masquée
        if "".join(buf[start:end]) != MASK_CHAR * (end - start):
            fill(start, end)
    
    # Masquer les tableaux
    buf = list(mask_table_syntax("".join(buf)))
    
    # Masquer les balises HTML génériques
    snapshot = "".join(buf)
    for m in _GENERIC_TAG_RE.finditer(snapshot):
        fill(m.start(), m.end())
    
    return "".join(buf)


def find_first_sentence_end(text: str) -> int:
    """Trouve la fin de la première phrase dans le texte."""
    sentence_enders = re.compile(r'[.!?]+')
    match = sentence_enders.search(text)
    if match:
        return match.end()
    return len(text)
