"""
Module de gestion des résumés d'édition pour Wikipedia.

Fournit un résumé d'édition unique et déterministe pour chaque type de
correction, construit au format OviX à partir des compteurs de corrections
appliquées.

Format OviX: Action principale - page(s) de référence/correction - (test OviX)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Final

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Format OviX: Action principale - page(s) de référence/correction - (test OviX)
# ----------------------------------------------------------------------
TEST_SIGNATURE = "test [[Utilisateur:OviXCore|OviX]]"

# Nombre maximum d'éléments détaillés affichés par catégorie (liens morts,
# enrichissements, etc.) dans le commentaire du résumé.
MAX_DETAIL_ITEMS = 1

# Pages de référence Wikipedia pour chaque type de correction
REFERENCE_PAGES: Final[Dict[str, List[str]]] = {
    "dead_link": ["[[Wikipédia:Vérifiabilité|vérifiabilité]]"],
    "http_link": ["[[Wikipédia:Liens externes|liens externes]]"],
    "reference_enrichment": ["[[Wikipédia:Vérifiabilité|vérifiabilité]]"],
    "case_normalization": [],
    "typo": [],
    "bare_url": ["[[Wikipédia:Vérifiabilité|vérifiabilité]]"],
    "duplicate_refs": ["[[Wikipédia:Vérifiabilité|vérifiabilité]]"],
    "uppercase_parameter": ["[[Wikipédia:Typographie|typographie]]"],
    "invalid_isbn": ["[[Wikipédia:ISBN|ISBN]]"],
    "template_type": ["[[Wikipédia:Modèle|modèles]]"],
    "broken_link": ["[[Wikipédia:Vérifiabilité|vérifiabilité]]"],
}

# Action principale unique pour chaque type de correction (un seul libellé
# par analyseur : plus de tirage aléatoire entre variantes équivalentes).
ACTIONS: Final[Dict[str, str]] = {
    "dead_link": "Réparation de liens morts (404/410)",
    "http_link": "Sécurisation des liens (HTTPS)",
    "reference_enrichment": "Complément de références (site, date de consultation)",
    "case_normalization": "Harmonisation typographique (casse)",
    "typo": "Correction typographique",
    "bare_url": "Conversion de liens nus en références",
    "duplicate_refs": "Suppression de références dupliquées",
    "uppercase_parameter": "Correction de paramètres en majuscules",
    "invalid_isbn": "Correction de format ISBN",
    "template_type": "Correction de type de modèle",
    "broken_link": "Vérification de liens brisés",
}

# Libellés courts utilisés pour les corrections secondaires du résumé
# (ex: "liens morts (3)" quand ce n'est pas l'action principale).
SHORT_LABELS: Final[Dict[str, str]] = {
    "dead_link": "liens morts",
    "http_link": "HTTPS",
    "case_normalization": "casse",
    "reference_enrichment": "réf",
    "typo": "typo",
    "bare_url": "liens nus",
    "duplicate_refs": "doublons",
    "uppercase_parameter": "majuscules",
    "invalid_isbn": "ISBN",
    "template_type": "modèles",
    "broken_link": "liens brisés",
}

# Priorité d'affichage en tant qu'action principale quand plusieurs types
# de corrections sont présents dans la même édition.
PRIORITY_ORDER: Final[List[str]] = [
    "dead_link", "reference_enrichment", "http_link", "case_normalization",
    "bare_url", "duplicate_refs", "uppercase_parameter", "invalid_isbn",
    "template_type", "broken_link", "typo",
]

# Types d'issues regroupés sous l'étiquette "typographie" — centralisé pour
# ne plus dupliquer cette liste entre les deux chemins d'entrée de get_summary
# (issue_types et l'ancienne interface correction_types).
_TYPO_ISSUE_TYPES: Final[frozenset] = frozenset({
    "double_space", "trailing_space", "multiple_blank_lines",
    "punctuation_spacing", "french_quotes", "numeric_interval",
    "percent_spacing", "unit_spacing", "degree_spacing",
})

_KNOWN_CORRECTION_TYPES: Final[frozenset] = frozenset({
    "dead_link", "http_link", "case_normalization", "lia_correction", "reference_enrichment",
    "bare_url", "duplicate_refs", "uppercase_parameter", "invalid_isbn", "template_type", "broken_link",
})

# Mois en français pour le formatage des dates "consulté le".
_MOIS_FR: Final[List[str]] = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _format_date_fr(raw_date: str) -> str:
    """
    Convertit une date au format AAAA-MM-JJ (ou AAAA/MM/JJ) en format
    français toutes lettres, ex: "2025-02-22" -> "22 février 2025".

    Si la date ne correspond à aucun format reconnu, elle est retournée
    telle quelle (aucune exception levée).
    """
    raw_date = raw_date.strip()
    for sep in ("-", "/"):
        parts = raw_date.split(sep)
        if len(parts) == 3:
            try:
                nums = [int(p) for p in parts]
            except ValueError:
                continue
            # AAAA-MM-JJ / AAAA/MM/JJ : le premier segment est l'année (4 chiffres)
            if len(parts[0]) == 4:
                year, month, day = nums
            # JJ-MM-AAAA / JJ/MM/AAAA
            else:
                day, month, year = nums
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f"{day} {_MOIS_FR[month - 1]} {year}"
    return raw_date


__all__ = [
    'get_summary',
    'get_summary_from_issues',
]


def _build_ovix_summary(correction_counts: Dict[str, int], include_counts: bool = True) -> str:
    """
    Construit un résumé au format OviX: Action avec compteurs — page(s) de référence — (Test OviX)

    Un seul libellé est utilisé par type de correction (voir ACTIONS et
    SHORT_LABELS) : aucune variation aléatoire, le résumé est déterministe
    pour un même jeu de compteurs.

    Args:
        correction_counts: Dictionnaire des types de corrections et leurs
            compteurs (ex: {"dead_link": 5, "http_link": 3}).
        include_counts: Si True, inclut les compteurs dans le résumé principal.
            Si False, n'inclut pas les compteurs (utilisé pour affichage pré-publication).

    Returns:
        Résumé au format OviX avec ou sans compteurs.
    """
    if not correction_counts:
        return f"Maintenance - {TEST_SIGNATURE}"

    # Filtrer les corrections avec compteur > 0. Copie défensive: on ne
    # doit jamais muter le dict fourni par l'appelant.
    active_corrections = {k: v for k, v in correction_counts.items() if v > 0}

    if not active_corrections:
        return f"Maintenance - {TEST_SIGNATURE}"

    # Déterminer l'action principale selon PRIORITY_ORDER ; si aucun type
    # connu n'est présent, prendre le premier disponible.
    primary_correction = next(
        (t for t in PRIORITY_ORDER if t in active_corrections),
        next(iter(active_corrections)),
    )

    action_label = ACTIONS.get(primary_correction, "Maintenance")
    if include_counts:
        action_with_count = f"{action_label} ({active_corrections[primary_correction]})"
    else:
        action_with_count = action_label

    # Ajouter les autres corrections avec leurs compteurs, sous forme courte.
    if include_counts:
        other_corrections = [
            f"{SHORT_LABELS[correction_type]} ({count})"
            for correction_type, count in active_corrections.items()
            if correction_type != primary_correction and correction_type in SHORT_LABELS
        ]
    else:
        other_corrections = [
            SHORT_LABELS[correction_type]
            for correction_type, _count in active_corrections.items()
            if correction_type != primary_correction and correction_type in SHORT_LABELS
        ]

    # Collecter les pages de référence uniques, en préservant l'ordre
    seen: set = set()
    unique_references: List[str] = []
    for correction_type in active_corrections:
        for page in REFERENCE_PAGES.get(correction_type, []):
            if page not in seen:
                seen.add(page)
                unique_references.append(page)

    action_str = (
        f"{action_with_count}, {', '.join(other_corrections)}"
        if other_corrections
        else action_with_count
    )

    if unique_references:
        references_str = " - ".join(unique_references)
        return f"{action_str} - {references_str} - {TEST_SIGNATURE}"
    return f"{action_str} - {TEST_SIGNATURE}"


def get_summary(corrections_count: int = 0,
                correction_types: Optional[List[str]] = None,
                issue_types: Optional[Dict[str, int]] = None) -> str:
    """
    Génère un résumé d'édition basé sur les corrections appliquées.

    Format OviX: Action avec compteurs — page(s) de référence — (Test OviX)

    Args:
        corrections_count: Nombre de corrections appliquées (non utilisé
            directement, conservé pour compatibilité de signature).
        correction_types: Liste des types de corrections (optionnel, déprécié).
        issue_types: Dictionnaire des types d'issues et leurs comptes
            (ex: {"http_link": 5, "double_space": 2}).

    Returns:
        Un résumé d'édition au format OviX avec compteurs. Ne lève jamais
        d'exception sur des entrées malformées (valeurs négatives, clés
        inconnues, etc.) — retombe sur un résumé générique dans ces cas.
    """
    if issue_types:
        def _safe_count(value) -> int:
            return value if isinstance(value, int) and value > 0 else 0

        correction_counts: Dict[str, int] = {}
        for key in ("dead_link", "http_link", "case_normalization", "reference_enrichment",
                    "bare_url", "duplicate_refs", "uppercase_parameter", "invalid_isbn",
                    "template_type", "broken_link"):
            count = _safe_count(issue_types.get(key, 0))
            if count > 0:
                correction_counts[key] = count

        # Les corrections LIA et les issues typographiques partagent le même
        # libellé "typo" dans le résumé final ; elles sont donc fusionnées.
        typo_count = sum(
            _safe_count(count) for issue_type, count in issue_types.items()
            if issue_type in _TYPO_ISSUE_TYPES
        )
        total_typo = typo_count + _safe_count(issue_types.get("lia_correction", 0))
        if total_typo > 0:
            correction_counts["typo"] = total_typo

        logger.info(
            f"get_summary (OviX format with counts): correction_counts={correction_counts}, "
            f"issue_types={issue_types}"
        )
        return _build_ovix_summary(correction_counts)

    # Fallback pour l'ancienne interface avec correction_types (liste à plat).
    if correction_types:
        correction_counts = {}
        for key in ("dead_link", "http_link", "case_normalization", "reference_enrichment"):
            count = correction_types.count(key)
            if count > 0:
                correction_counts[key] = count

        # Types inconnus considérés comme typo, fusionnés avec lia_correction.
        unknown_types = [t for t in correction_types if t not in _KNOWN_CORRECTION_TYPES]
        total_typo = len(unknown_types) + correction_types.count("lia_correction")
        if total_typo > 0:
            correction_counts["typo"] = total_typo

        logger.info(
            f"get_summary (OviX format with counts, old interface): correction_counts={correction_counts}, "
            f"correction_types={correction_types}"
        )
        return _build_ovix_summary(correction_counts)

    return f"Maintenance - {TEST_SIGNATURE}"


def _has_internal_link(entry: str) -> bool:
    """
    Indique si une entrée de détail (enrichissement) contient un lien
    interne wiki ([[...]]) dans son "site ajouté". Ces entrées ont plus de
    valeur éditoriale et doivent être mises en avant dans l'affichage.
    """
    import re
    return bool(re.search(r'site ajouté\s*:\s*\[\[', entry, re.IGNORECASE))


def _detect_enrichment_mapping(original_content: str, corrected_content: str) -> tuple[List[str], int]:
    """
    Détecte les enrichissements de références (ajout de `site=` et/ou
    `consulté le=`) entre le contenu original et le contenu corrigé.

    Robuste à trois cas de figure pour retrouver le template corrigé
    correspondant à un template original donné :
    1. même URL présente dans les deux contenus ;
    2. URL remplacée par une archive, mais même domaine repérable ;
    3. en dernier repli, même paramètre `titre=`.

    Un repli supplémentaire (recherche de tout template corrigé contenant
    site=/consulté le= absent de l'original) s'exécute TOUJOURS en complément
    de la boucle principale, pas seulement quand elle est vide, pour capturer
    les enrichissements que l'appariement précis n'a pas su relier à un
    template original. Les doublons entre les deux passes sont évités via un
    set des entrées déjà trouvées.

    Les entrées comportant un lien interne wiki ([[Nom du site]]) dans leur
    "site ajouté" sont TOUJOURS priorisées AVANT la troncature à
    MAX_DETAIL_ITEMS, pour garantir qu'un enrichissement à plus forte valeur
    éditoriale (lien interne) ne soit jamais coupé au profit d'un simple
    ajout de date, quel que soit l'ordre de détection.

    La liste retournée est dédupliquée (via `already_found`) et tronquée à
    MAX_DETAIL_ITEMS pour l'affichage ; le compte total (avant troncature)
    est retourné séparément pour usage dans le résumé.

    Returns:
        Tuple (liste de chaînes formatées et tronquées pour affichage,
        nombre total détecté avant troncature).
    """
    import re
    from urllib.parse import urlparse

    enrichment_mapping: List[str] = []

    template_pattern = r'\{\{[^}]+\|url\s*=\s*(https?://[^\s|\}]+)[^}]*\}\}'
    original_templates = re.findall(template_pattern, original_content, re.IGNORECASE)
    # Dédup des URLs sources : si une même URL apparaît plusieurs fois dans
    # l'original (référence dupliquée), on ne veut la traiter/compter qu'une
    # seule fois, sinon un seul enrichissement réel serait compté plusieurs fois.
    original_templates = list(dict.fromkeys(original_templates))
    logger.info(f"Enrichment detection: found {len(original_templates)} unique templates in original_content")

    for url in original_templates:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')

        original_template_match = re.search(r'\{\{[^}]*' + re.escape(url) + r'[^}]*\}\}', original_content, re.IGNORECASE)
        if not original_template_match:
            continue
        original_template = original_template_match.group(0)

        # 1. Même URL dans le contenu corrigé
        corrected_template_match = re.search(r'\{\{[^}]*' + re.escape(url) + r'[^}]*\}\}', corrected_content, re.IGNORECASE)

        # 2. Repli par domaine (cas d'une URL remplacée par une archive)
        if not corrected_template_match:
            domain_pattern = r'\{\{[^}]*' + re.escape(domain) + r'[^}]*\}\}'
            corrected_template_match = re.search(domain_pattern, corrected_content, re.IGNORECASE)

        # 3. Repli par titre (cas d'un template reformaté sans URL ni domaine identiques)
        if not corrected_template_match:
            titre_match = re.search(r'\|\s*titre\s*=\s*([^|\}]+)', original_template, re.IGNORECASE)
            if titre_match:
                titre_escaped = re.escape(titre_match.group(1).strip()[:40])
                if titre_escaped:
                    titre_pattern = r'\{\{[^}]*' + titre_escaped + r'[^}]*\}\}'
                    corrected_template_match = re.search(titre_pattern, corrected_content, re.IGNORECASE)

        if not corrected_template_match:
            logger.info(f"Enrichment detection: no corrected template found for {url}")
            continue

        corrected_template = corrected_template_match.group(0)
        mapping_parts = []

        # Capture le paramètre site= en entier, y compris un lien interne wiki
        # complet du type [[Nom du site]] ou [[Nom du site|Alias]] : le pattern
        # non-greedy gère les deux cas (texte simple ou lien interne avec un
        # ou deux crochets fermants).
        site_match = re.search(r'\|\s*site\s*=\s*(\[\[[^\]]+\]\]|[^|\}]+)', corrected_template, re.IGNORECASE)
        site_part = None
        if site_match:
            site_value = site_match.group(1).strip()
            if not re.search(r'\|\s*site\s*=', original_template, re.IGNORECASE):
                site_part = f"site ajouté : {site_value}"

        consulte_match = re.search(r'\|\s*consulté le\s*=\s*([^|\}]+)', corrected_template, re.IGNORECASE)
        date_part = None
        if consulte_match:
            consulte_value = _format_date_fr(consulte_match.group(1).strip())
            if not re.search(r'\|\s*consulté le\s*=', original_template, re.IGNORECASE):
                date_part = f"date ajoutée : {consulte_value}"

        # Ordre d'affichage : site avant date.
        if site_part:
            mapping_parts.append(site_part)
        if date_part:
            mapping_parts.append(date_part)

        if mapping_parts:
            enrichment_mapping.append(", ".join(mapping_parts))

    # Repli supplémentaire (TOUJOURS exécuté, en complément) : chercher dans
    # corrected_content tout template contenant site= ou consulté le= qui
    # n'existe pas tel quel dans original_content. Capture les cas où le
    # template a trop changé pour être apparié précisément ci-dessus. Les
    # doublons avec la boucle principale sont évités via already_found.
    all_corrected_templates = re.findall(r'\{\{[^}]+\}\}', corrected_content, re.IGNORECASE)
    already_found = set(enrichment_mapping)
    for corrected_template in all_corrected_templates:
        if corrected_template in original_content:
            continue
        has_site = re.search(r'\|\s*site\s*=\s*(\[\[[^\]]+\]\]|[^|\}]+)', corrected_template, re.IGNORECASE)
        has_consulte = re.search(r'\|\s*consulté le\s*=\s*([^|\}]+)', corrected_template, re.IGNORECASE)
        if not (has_site or has_consulte):
            continue
        mapping_parts = []
        if has_site:
            mapping_parts.append(f"site ajouté : {has_site.group(1).strip()}")
        if has_consulte:
            mapping_parts.append(f"date ajoutée : {_format_date_fr(has_consulte.group(1).strip())}")
        if mapping_parts:
            entry = ", ".join(mapping_parts)
            if entry not in already_found:
                enrichment_mapping.append(entry)
                already_found.add(entry)

    # Le total (avant troncature) doit refléter TOUTES les entrées détectées,
    # indépendamment de l'ordre de tri appliqué ensuite.
    total_count = len(enrichment_mapping)

    # Prioriser les entrées dont le site ajouté est un lien interne wiki
    # ([[Nom]]) : elles sont placées en tête de liste. Ce tri s'effectue
    # AVANT la troncature à MAX_DETAIL_ITEMS (contrairement à avant), pour
    # garantir qu'une entrée à lien interne ne soit jamais éliminée par la
    # troncature au profit d'une entrée moins pertinente détectée plus tôt.
    enrichment_mapping.sort(key=lambda entry: 0 if _has_internal_link(entry) else 1)

    if len(enrichment_mapping) > MAX_DETAIL_ITEMS:
        enrichment_mapping = enrichment_mapping[:MAX_DETAIL_ITEMS]
        enrichment_mapping.append("...")

    logger.info(f"Enrichment mapping detected: {enrichment_mapping}, total_count={total_count}")
    return enrichment_mapping, total_count


def _detect_brise_le_mapping(corrected_content: str) -> List[str]:
    """
    Détecte les liens marqués comme brisés (brisé le= / brise le= / dead-url=)
    dans le contenu corrigé.

    Returns:
        Liste de chaînes formatées pour affichage, format : "brisé le : DATE".
    """
    import re

    brise_le_patterns = [
        r'\{\{[^}]*\|\s*(?:brisé le|brise le|dead-url)\s*=\s*([^|\}]+)[^}]*\}\}',
    ]

    brise_le_mapping: List[str] = []
    seen_dates = set()

    for pattern in brise_le_patterns:
        for match in re.findall(pattern, corrected_content, re.IGNORECASE):
            brise_date = match.strip()
            if brise_date and brise_date not in seen_dates:
                seen_dates.add(brise_date)
                formatted_date = _format_date_fr(brise_date)
                brise_le_mapping.append(f"brisé le : {formatted_date}")

    if len(brise_le_mapping) > MAX_DETAIL_ITEMS:
        brise_le_mapping = brise_le_mapping[:MAX_DETAIL_ITEMS]
        brise_le_mapping.append("...")

    logger.info(f"Brise le mapping detected: {brise_le_mapping}")
    return brise_le_mapping


def _detect_dead_link_mapping(original_content: str, corrected_content: str) -> tuple[List[str], int]:
    """
    Détecte les remplacements de liens morts par des URLs d'archive
    (web.archive.org, wikiwix, arquivo.pt) apparues dans le contenu corrigé
    mais absentes du contenu original.

    Dédupliqué par URL source : si la même URL source apparaît plusieurs fois
    dans l'article (référence dupliquée) et est archivée séparément avec des
    timestamps différents pour chaque occurrence, elle ne compte qu'une seule
    fois dans le total (on compte des liens distincts réparés, pas des
    occurrences de réparation).

    Returns:
        Tuple (liste de chaînes formatées et tronquées pour affichage,
        nombre total de liens distincts détectés avant troncature).
        Format de chaque entrée : "domaine.com → web.archive.org/web/TIMESTAMP".
    """
    import re
    from urllib.parse import urlparse

    archive_patterns = [
        (r'https://web\.archive\.org/web/(\d+)/(https?://[^\s\)]+)', 'web.archive.org'),
        (r'https://wikiwix\.cache/([^/]+)/([^/]+)', 'wikiwix'),
        (r'https://arquivo\.pt/wayback/(\d+)/https?://([^\s\)]+)', 'arquivo.pt'),
    ]

    archive_matches = []
    original_archive_matches = []

    for pattern, provider in archive_patterns:
        for match in re.findall(pattern, corrected_content):
            # match est un tuple (timestamp, url) issu des 2 groupes de capture.
            # On aplati systématiquement en (timestamp, url, provider) pour que
            # la structure soit cohérente avec le déballage à 3 valeurs plus bas.
            timestamp, url = match
            archive_matches.append((timestamp, url, provider))

        for match in re.findall(pattern, original_content):
            timestamp, url = match
            original_archive_matches.append((timestamp, url, provider))

    archive_set = set(archive_matches)
    original_set = set(original_archive_matches)
    new_matches = archive_set - original_set

    dead_link_mapping: List[str] = []
    seen_original_urls: set = set()
    # Trier pour un ordre déterministe (par timestamp puis URL puis provider)
    for timestamp, original_url, provider in sorted(new_matches):
        # Déduplication par URL source : même URL avec plusieurs timestamps
        # (occurrences dupliquées de la même référence dans l'article) ne
        # compte qu'une seule fois.
        if original_url in seen_original_urls:
            continue
        seen_original_urls.add(original_url)

        parsed = urlparse(original_url)
        clean_domain = parsed.netloc.replace('www.', '')

        if provider == 'web.archive.org':
            archive_url_with_timestamp = f"web.archive.org/web/{timestamp}"
        elif provider == 'wikiwix':
            archive_url_with_timestamp = f"wikiwix.cache/{timestamp}"
        elif provider == 'arquivo.pt':
            archive_url_with_timestamp = f"arquivo.pt/wayback/{timestamp}"
        else:
            archive_url_with_timestamp = provider

        dead_link_mapping.append(f"{clean_domain} → {archive_url_with_timestamp}")

    total_count = len(dead_link_mapping)

    if len(dead_link_mapping) > MAX_DETAIL_ITEMS:
        dead_link_mapping = dead_link_mapping[:MAX_DETAIL_ITEMS]
        dead_link_mapping.append("...")

    logger.info(f"Dead link mapping detected: {dead_link_mapping}, total_count={total_count}")
    return dead_link_mapping, total_count


def get_summary_from_issues(
    issues: List[Any],
    original_content: Optional[str] = None,
    corrected_content: Optional[str] = None
) -> str:
    """
    Génère un résumé d'édition complet à partir d'une liste d'issues et du contenu.

    Cette fonction est utilisée pour générer le résumé à la fin de l'analyse,
    avant publication, pour affichage dans la page de détails article.
    Elle génère le même résumé que celui utilisé par publisher pour l'envoi sur Wikipédia.

    Args:
        issues: Liste d'objets Issue détectés par les analyseurs.
        original_content: Contenu original de l'article (optionnel).
        corrected_content: Contenu corrigé de l'article (optionnel).

    Returns:
        Un résumé d'édition au format OviX avec commentaires détaillés.
    """
    from collections import Counter

    # Compter les types d'issues (seulement celles avec suggested_text = corrections réelles)
    issue_types = Counter()
    for issue in issues:
        if hasattr(issue, 'issue_type') and hasattr(issue, 'suggested_text') and issue.suggested_text:
            issue_types[issue.issue_type] += 1
    
    logger.info(f"Issue types counted from issues: {dict(issue_types)}")

    dead_link_mapping: List[str] = []
    enrichment_mapping: List[str] = []
    brise_le_mapping: List[str] = []

    if original_content and corrected_content:
        enrichment_mapping, enrichment_total_count = _detect_enrichment_mapping(original_content, corrected_content)
        dead_link_mapping, dead_link_total_count = _detect_dead_link_mapping(original_content, corrected_content)
        brise_le_mapping = _detect_brise_le_mapping(corrected_content)

        # Mettre à jour les compteurs avec les détections réelles.
        #
        # IMPORTANT: la détection par regex (_detect_*_mapping) sert à extraire
        # un DÉTAIL textuel affichable, mais son rappel n'est pas garanti à 100%
        # (appariement par URL/domaine/titre qui peut échouer sur certains
        # templates). Le compteur issu des vraies `issues` analysées
        # (suggested_text non vide) est en revanche fiable : c'est le nombre
        # de corrections RÉELLEMENT appliquées.
        #
        # On ne doit donc jamais laisser la détection heuristique ÉCRASER ce
        # compteur vers le bas : on prend le maximum des deux sources plutôt
        # qu'un remplacement pur, pour ne jamais sous-compter une correction
        # réellement effectuée simplement parce que son détail textuel n'a
        # pas pu être extrait par regex.
        #
        # CORRECTION IMPORTANTE: On utilise TOUJOURS les compteurs des issues
        # analysées comme source de vérité, et on ne les remplace JAMAIS par
        # les détections heuristiques. Les détections ne servent qu'à générer
        # les détails textuels affichables.
        logger.info(f"Before heuristic update: issue_types={dict(issue_types)}, dead_link_total_count={dead_link_total_count}, enrichment_total_count={enrichment_total_count}")
        
        if 'dead_link' in issue_types:
            # On garde le compteur des issues, on ne le remplace pas
            logger.info(f"Keeping dead_link count from issues: {issue_types['dead_link']}")
        elif dead_link_mapping:
            # Seulement si aucune issue dead_link n'a été détectée, on utilise la détection
            issue_types['dead_link'] = dead_link_total_count
            logger.info(f"Using dead_link count from detection: {dead_link_total_count}")

        if 'reference_enrichment' in issue_types:
            # On garde le compteur des issues, on ne le remplace pas
            logger.info(f"Keeping reference_enrichment count from issues: {issue_types['reference_enrichment']}")
        elif enrichment_mapping:
            # Seulement si aucune issue reference_enrichment n'a été détectée, on utilise la détection
            issue_types['reference_enrichment'] = enrichment_total_count
            logger.info(f"Using reference_enrichment count from detection: {enrichment_total_count}")
        
        logger.info(f"After heuristic update: issue_types={dict(issue_types)}")

    # Générer le résumé de base avec un format spécial pour dead_link et reference_enrichment
    # dead_link utilise "(404/410)" fixe, reference_enrichment utilise "réf" ou "Complément de références (site, date de consultation)"
    if 'dead_link' in issue_types or 'reference_enrichment' in issue_types:
        # Construire manuellement le résumé pour éviter les compteurs parasites
        action_parts = []
        
        # Ajouter dead_link avec format spécial
        if 'dead_link' in issue_types:
            action_parts.append("Réparation de liens morts (404/410)")
        
        # Ajouter reference_enrichment avec format adapté
        if 'reference_enrichment' in issue_types:
            if 'dead_link' in issue_types:
                # Avec dead_link: version courte "réf"
                action_parts.append("réf")
            else:
                # Seul: version complète "Complément de références (site, date de consultation)"
                action_parts.append("Complément de références (site, date de consultation)")
        
        # Ajouter les autres corrections avec leurs compteurs
        other_issue_types = {k: v for k, v in issue_types.items() if k not in ['dead_link', 'reference_enrichment']}
        for correction_type, count in other_issue_types.items():
            if correction_type in SHORT_LABELS:
                action_parts.append(f"{SHORT_LABELS[correction_type]} ({count})")
        
        # Collecter les pages de référence
        seen = set()
        unique_references = []
        for correction_type in issue_types:
            for page in REFERENCE_PAGES.get(correction_type, []):
                if page not in seen:
                    seen.add(page)
                    unique_references.append(page)
        
        # Construire le résumé final
        action_str = ", ".join(action_parts)
        if unique_references:
            references_str = " - ".join(unique_references)
            base_summary = f"{action_str} - {references_str} - {TEST_SIGNATURE}"
        else:
            base_summary = f"{action_str} - {TEST_SIGNATURE}"
    else:
        base_summary = _build_ovix_summary(dict(issue_types), include_counts=True)

    # Construire le commentaire avec les compteurs pour chaque type
    comment_parts = []
    if 'dead_link' in issue_types:
        n = issue_types['dead_link']
        comment_parts.append(f"{n} lien{'s' if n > 1 else ''} mort{'s' if n > 1 else ''} réparé{'s' if n > 1 else ''}")
    if 'reference_enrichment' in issue_types:
        n = issue_types['reference_enrichment']
        comment_parts.append(f"{n} référence{'s' if n > 1 else ''} enrichie{'s' if n > 1 else ''}")
    if 'case_normalization' in issue_types:
        n = issue_types['case_normalization']
        comment_parts.append(f"casse ({n})")
    if 'http_link' in issue_types:
        n = issue_types['http_link']
        comment_parts.append(f"HTTPS ({n})")
    if 'bare_url' in issue_types:
        n = issue_types['bare_url']
        comment_parts.append(f"liens nus ({n})")
    if 'duplicate_refs' in issue_types:
        n = issue_types['duplicate_refs']
        comment_parts.append(f"doublons ({n})")
    if 'uppercase_parameter' in issue_types:
        n = issue_types['uppercase_parameter']
        comment_parts.append(f"majuscules ({n})")
    if 'invalid_isbn' in issue_types:
        n = issue_types['invalid_isbn']
        comment_parts.append(f"ISBN ({n})")
    if 'template_type' in issue_types:
        n = issue_types['template_type']
        comment_parts.append(f"modèles ({n})")
    if 'broken_link' in issue_types:
        n = issue_types['broken_link']
        comment_parts.append(f"liens brisés ({n})")
    if 'typo' in issue_types:
        n = issue_types['typo']
        comment_parts.append(f"typo ({n})")
    if 'correction' in issue_types:
        n = issue_types['correction']
        comment_parts.append(f"corrections ({n})")

    # Construire le commentaire final. Les détails de chaque catégorie
    # (liens morts, enrichissements) sont affichés avec des étiquettes claires
    # pour éviter toute confusion.
    #
    # NOTE IMPORTANTE: dead_link_mapping et enrichment_mapping sont déjà
    # triés (liens internes en tête) et tronqués à MAX_DETAIL_ITEMS (avec
    # "..." déjà ajouté si besoin) par _detect_dead_link_mapping /
    # _detect_enrichment_mapping. On les utilise donc ICI tels quels, sans
    # re-trancher ni rajouter un second "...", pour éviter un double "......"
    # dans le commentaire final.
    comment = ""
    if comment_parts:
        comment = " - ".join(comment_parts)

        detail_parts = []
        if dead_link_mapping:
            dead_link_details = ", ".join(dead_link_mapping)
            detail_parts.append(dead_link_details)

        if enrichment_mapping:
            enrichment_details = ", ".join(enrichment_mapping)
            detail_parts.append(enrichment_details)
            logger.info(f"Enrichment details added to comment: {enrichment_mapping}")
        else:
            logger.info("Enrichment mapping is empty, no details to add")

        if brise_le_mapping:
            brise_le_details = ", ".join(brise_le_mapping)
            detail_parts.append(brise_le_details)
            logger.info(f"Brise le details added to comment: {brise_le_mapping}")

        if detail_parts:
            comment += " : " + " - ".join(detail_parts)

    # Combiner le résumé de base avec le commentaire
    if comment:
        return f"{base_summary} : {comment}"
    else:
        return base_summary