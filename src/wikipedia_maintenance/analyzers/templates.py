"""
Analyzer for template-related issues in Wikipedia articles (wikicode).

Detects:
    - Obsolete / deprecated templates (via a pluggable, optionally live,
      provider — no hardcoded, possibly-wrong static list)
    - Empty template parameters (|param= with no value)
    - Duplicate parameters within the same template call
    - Unbalanced / unterminated templates ({{ without a matching }})
    - English parameter names used in French citation templates
      (a very common copy-paste artefact when importing sources from
      en.wikipedia into {{Lien web}}, {{Article}}, {{Ouvrage}}...)
    - Empty template names ({{}})
    - Trailing pipe with no parameter ({{tpl|param=value| }})
    - Positional parameters with empty value
    - Equal sign with no key (|=value)
    - Unnecessary spaces around '=' in parameters
    - English template names (e.g., {{cite web}} → {{lien web}})
    - Excessive template length (potential readability issue)

Templates are parsed with a lightweight brace-depth scanner instead of
a single flat regex, so nested templates, wikilinks used as parameter
values, and {{{parameter}}} references don't produce false positives
or broken splits.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Protocol, Set, Tuple

from .base import BaseAnalyzer, Issue

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Structures internes
# --------------------------------------------------------------------------- #

@dataclass
class TemplateParam:
    key: Optional[str]      # None pour un paramètre positionnel
    value: str
    key_start: int
    value_start: int
    value_end: int


@dataclass
class TemplateCall:
    raw_name: str            # tel qu'écrit, ex. " lien Web "
    name: str                # normalisé pour comparaison, ex. "lien web"
    start: int                # position du "{{" d'ouverture
    end: int                  # position juste après le "}}" fermant
    depth: int                 # 0 = appel de premier niveau
    params: List[TemplateParam]


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

@dataclass
class TemplateAnalyzerConfig:
    check_obsolete_templates: bool = True
    check_empty_parameters: bool = True
    check_duplicate_parameters: bool = True
    check_unbalanced_templates: bool = True
    check_foreign_parameters: bool = True
    check_empty_template_name: bool = True
    check_trailing_pipe: bool = True
    check_english_template_names: bool = False   # désactivé par défaut
    check_excessive_length: bool = True
    max_template_length: int = 2000              # caractères
    check_infobox_fields: bool = True            # Infobox-specific checks

    # Modèles de citation français où l'on vérifie la présence de noms
    # de paramètres anglais collés par erreur (copier-coller depuis
    # en.wikipedia). Noms en minuscules, sans le préfixe "Modèle:".
    citation_templates: frozenset = field(
        default_factory=lambda: frozenset(
            {"lien web", "article", "ouvrage", "chapitre"}
        )
    )


# Paramètres anglais couramment collés par erreur dans un modèle de
# citation francophone -> équivalent français attendu. Les paramètres
# identiques dans les deux langues (date, url, isbn, pages...) ne sont
# volontairement pas listés : les signaler serait un faux positif.
ENGLISH_TO_FRENCH_PARAMS: Dict[str, str] = {
    "title": "titre",
    "author": "auteur",
    "last": "nom",
    "first": "prénom",
    "publisher": "éditeur",
    "accessdate": "consulté le",
    "access-date": "consulté le",
    "website": "site",
    "work": "site",
    "language": "langue",
    "location": "lieu",
    "year": "année",
    "editor": "directeur",
    "quote": "citation",
    "journal": "périodique",
    "publication-date": "date de publication",
    "archive-url": "url archive",
    "archive-date": "date archive",
    "dead-url": "url morte",
}


# Modèles anglais courants et leur équivalent français (optionnel)
ENGLISH_TEMPLATE_NAMES: Dict[str, str] = {
    "cite web": "lien web",
    "cite book": "ouvrage",
    "cite journal": "article",
    "cite news": "article",
    "cite article": "article",
}


class ObsoleteTemplateProvider(Protocol):
    """Fournit la liste des modèles dépréciés à un instant donné.

    Une liste statique de modèles "obsolètes" écrite en dur se périme
    et se trompe facilement (par exemple {{Ébauche}} ou {{À sourcer}}
    ne sont PAS obsolètes : ce sont des modèles de maintenance
    toujours utilisés). Passer par cette interface permet d'injecter
    soit une liste statique assumée par l'appelant, soit un
    fournisseur qui interroge Wikipédia en direct.
    """

    def obsolete_templates(self) -> Dict[str, Optional[str]]:
        """{nom de modèle sans le préfixe 'Modèle:' : modèle de remplacement ou None}"""
        ...


class StaticObsoleteTemplateProvider:
    """Fournisseur trivial basé sur un dictionnaire fourni par l'appelant."""

    def __init__(self, mapping: Optional[Dict[str, Optional[str]]] = None) -> None:
        self._mapping = {k.strip().lower(): v for k, v in (mapping or {}).items()}

    def obsolete_templates(self) -> Dict[str, Optional[str]]:
        return self._mapping


class MediaWikiObsoleteTemplateProvider:
    """Récupère la vraie liste des modèles dépréciés depuis Wikipédia
    (catégorie de maintenance dédiée) au lieu de deviner une liste
    statique. Dépendance optionnelle : nécessite ``requests``.

    Exemple :
        >>> provider = MediaWikiObsoleteTemplateProvider()
        >>> analyzer = TemplateAnalyzer(obsolete_template_provider=provider)
    """

    def __init__(
        self,
        api_url: str = "https://fr.wikipedia.org/w/api.php",
        category: str = "Catégorie:Modèle déprécié",
        session=None,
        timeout: float = 10.0,
    ) -> None:
        self.api_url = api_url
        self.category = category
        self.timeout = timeout
        self._cache: Optional[Dict[str, Optional[str]]] = None

        try:
            import requests
        except ImportError as exc:
            raise ImportError(
                "MediaWikiObsoleteTemplateProvider nécessite le paquet 'requests'. "
                "Installez-le avec : pip install requests"
            ) from exc

        self._session = session or requests.Session()

    def obsolete_templates(self) -> Dict[str, Optional[str]]:
        if self._cache is not None:
            return self._cache
        try:
            members = self._fetch_category_members()
            mapping = self._resolve_replacements(members)
        except Exception as exc:
            logger.warning("Impossible de récupérer les modèles dépréciés, ignoré : %s", exc)
            mapping = {}
        self._cache = mapping
        return mapping

    def _fetch_category_members(self) -> List[str]:
        members: List[str] = []
        cmcontinue = None
        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": self.category,
                "cmnamespace": 10,  # espace de noms "Modèle"
                "cmlimit": 500,
                "format": "json",
                "formatversion": 2,
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            resp = self._session.get(self.api_url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            for member in data.get("query", {}).get("categorymembers", []):
                title = member.get("title", "")
                if title.startswith("Modèle:"):
                    members.append(title[len("Modèle:"):])
            cmcontinue = data.get("continue", {}).get("cmcontinue")
            if not cmcontinue:
                break
        return members

    def _resolve_replacements(self, names: List[str]) -> Dict[str, Optional[str]]:
        """Pour les modèles dépréciés qui sont de simples redirections,
        résout la cible afin de proposer un remplacement automatique."""
        mapping: Dict[str, Optional[str]] = {name.lower(): None for name in names}
        if not names:
            return mapping

        batch_size = 50
        for i in range(0, len(names), batch_size):
            batch = [f"Modèle:{n}" for n in names[i:i + batch_size]]
            resp = self._session.get(
                self.api_url,
                params={
                    "action": "query",
                    "titles": "|".join(batch),
                    "redirects": 1,
                    "format": "json",
                    "formatversion": 2,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json().get("query", {})
            for redirect in data.get("redirects", []):
                origin, target = redirect.get("from", ""), redirect.get("to", "")
                if origin.startswith("Modèle:") and target.startswith("Modèle:"):
                    mapping[origin[len("Modèle:"):].lower()] = target[len("Modèle:"):]
        return mapping


# --------------------------------------------------------------------------- #
# Analyzer
# --------------------------------------------------------------------------- #

class TemplateAnalyzer(BaseAnalyzer):
    """Analyse le wikicode à la recherche de problèmes liés aux modèles."""

    _PROTECTED_BLOCK_RE = re.compile(
        r"<nowiki>.*?</nowiki>"
        r"|<pre>.*?</pre>"
        r"|<syntaxhighlight[^>]*>.*?</syntaxhighlight>"
        r"|<source[^>]*>.*?</source>"
        r"|<math[^>]*>.*?</math>"
        r"|<!--.*?-->",
        re.IGNORECASE | re.DOTALL,
    )

    _TRIPLE_BRACE_RE = re.compile(r"\{\{\{[^{}]*\}\}\}")
    _BRACE_RUN_RE = re.compile(r"\{{2,}|\}{2,}")
    _WIKILINK_RE = re.compile(r"\[\[[^\[\]]*\]\]")
    _EMPTY_TEMPLATE_NAME_RE = re.compile(r"\{\{\s*\}\}")

    def __init__(
        self,
        config: Optional[TemplateAnalyzerConfig] = None,
        obsolete_template_provider: Optional[ObsoleteTemplateProvider] = None,
    ) -> None:
        """
        Args:
            config: Options d'activation / listes de modèles surveillés.
            obsolete_template_provider: Source de vérité pour les modèles
                dépréciés (voir :class:`ObsoleteTemplateProvider`). Si
                omis, cette vérification est simplement ignorée plutôt
                que basée sur une liste statique potentiellement fausse.
        """
        super().__init__()
        self.config = config or TemplateAnalyzerConfig()
        self.obsolete_template_provider = obsolete_template_provider

    # ------------------------------------------------------------------ #
    # API publique
    # ------------------------------------------------------------------ #

    def analyze(self, content: str) -> List[Issue]:
        """Analyse le contenu à la recherche de problèmes de modèles.

        Args:
            content: Contenu wikicode de l'article.

        Returns:
            Liste des problèmes détectés, triée par position dans le texte.
        """
        self.clear_issues()

        if not content:
            return self.issues

        mask = self._build_protected_mask(content)
        self._mask_param_references(content, mask)

        calls, unclosed_starts = self._find_templates(content, mask)

        # Détection des modèles non refermés
        if self.config.check_unbalanced_templates:
            for pos in unclosed_starts:
                self.issues.append(Issue(
                    issue_type="unbalanced_template",
                    description="Modèle non refermé (« {{ » sans « }} » correspondant)",
                    position=pos,
                    original_text=content[pos:min(pos + 40, len(content))],
                    suggested_text=None,
                    severity="high",
                ))

        # Modèles vides (nom absent) – détection directe, car le scanner ne les capture pas
        if self.config.check_empty_template_name:
            for match in self._EMPTY_TEMPLATE_NAME_RE.finditer(content):
                self.issues.append(Issue(
                    issue_type="empty_template_name",
                    description="Modèle sans nom ({{ }})",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text="",
                    severity="high",
                ))

        # Vérifications sur les appels capturés
        if self.config.check_obsolete_templates and self.obsolete_template_provider is not None:
            self._detect_obsolete_templates(calls)

        if self.config.check_empty_parameters:
            self._detect_empty_parameters(calls)

        if self.config.check_duplicate_parameters:
            self._detect_duplicate_parameters(calls)

        if self.config.check_foreign_parameters:
            self._detect_foreign_parameters(calls)

        if self.config.check_trailing_pipe:
            self._detect_trailing_pipe(calls)

        if self.config.check_english_template_names:
            self._detect_english_template_names(calls)

        if self.config.check_excessive_length:
            self._detect_excessive_length(calls)

        # ---- Infobox-specific checks ----
        if self.config.check_infobox_fields:
            self._detect_empty_infobox_fields(calls)
            self._detect_infobox_text_mismatch(content, calls)
            self._detect_broken_infobox_syntax(calls)
            self._detect_infobox_wrong_parameters(calls)

        # Tri final par position
        self.issues.sort(key=lambda issue: issue.position)
        return self.issues

    def get_analyzer_name(self) -> str:
        """Get analyzer name."""
        return "TemplateAnalyzer"

    # ------------------------------------------------------------------ #
    # Masquage des zones protégées
    # ------------------------------------------------------------------ #

    def _build_protected_mask(self, content: str) -> List[bool]:
        mask = [False] * len(content)
        for match in self._PROTECTED_BLOCK_RE.finditer(content):
            for i in range(match.start(), match.end()):
                mask[i] = True
        return mask

    def _mask_param_references(self, content: str, mask: List[bool]) -> None:
        """Marque les zones ``{{{...}}}`` comme protégées, en traitant
        les niveaux d'imbrication un par un (rare au-delà de 2 niveaux
        dans du wikicode d'article réel)."""
        working = list(content)
        for _ in range(6):
            changed = False
            text = "".join(working)
            for m in self._TRIPLE_BRACE_RE.finditer(text):
                if mask[m.start()]:
                    continue
                for i in range(m.start(), m.end()):
                    mask[i] = True
                    working[i] = "#"
                changed = True
            if not changed:
                break

    # ------------------------------------------------------------------ #
    # Analyse structurelle des modèles (scanner à profondeur d'accolades)
    # ------------------------------------------------------------------ #

    def _find_templates(
        self, content: str, mask: List[bool]
    ) -> Tuple[List[TemplateCall], List[int]]:
        """Repère tous les appels de modèles ``{{...}}``, y compris
        imbriqués, sans se laisser perturber par le contenu des zones
        protégées ni par les références ``{{{...}}}``.

        Returns:
            (liste des appels détectés en ordre de fermeture,
             positions des « {{ » jamais refermés)
        """
        working = list(content)
        for i, is_masked in enumerate(mask):
            if is_masked and working[i] in "{}":
                working[i] = "#"
        scan_text = "".join(working)

        stack: List[int] = []
        calls: List[TemplateCall] = []
        n = len(scan_text)
        i = 0
        while i < n:
            ch = scan_text[i]
            if ch == "{":
                j = i
                while j < n and scan_text[j] == "{":
                    j += 1
                remaining = j - i
                pos = i
                while remaining >= 2:
                    stack.append(pos)
                    pos += 2
                    remaining -= 2
                i = j
            elif ch == "}":
                j = i
                while j < n and scan_text[j] == "}":
                    j += 1
                remaining = j - i
                pos = i
                while remaining >= 2 and stack:
                    open_pos = stack.pop()
                    depth = len(stack)
                    calls.append(self._build_template_call(content, open_pos, pos + 2, depth, calls))
                    remaining -= 2
                    pos += 2
                i = j
            else:
                i += 1

        return calls, list(stack)

    def _build_template_call(
        self,
        content: str,
        start: int,
        end: int,
        depth: int,
        existing_calls: List[TemplateCall],
    ) -> TemplateCall:
        body_start, body_end = start + 2, end - 2

        # Enfants directs : appels déjà construits (post-ordre) et
        # entièrement contenus dans ce corps.
        children = [
            c for c in existing_calls
            if c.start >= body_start and c.end <= body_end and c.depth == depth + 1
        ]
        exclude_ranges = [(c.start, c.end) for c in children]
        exclude_ranges += [
            (m.start(), m.end())
            for m in self._WIKILINK_RE.finditer(content, body_start, body_end)
            if not any(cs <= m.start() < ce for cs, ce in exclude_ranges)
        ]

        segments = self._split_top_level(content, body_start, body_end, exclude_ranges)

        raw_name = content[segments[0][0]:segments[0][1]] if segments else ""
        name = self._normalize_template_name(raw_name)

        params: List[TemplateParam] = []
        for seg_start, seg_end in segments[1:]:
            eq_pos = self._find_top_level_equals(content, seg_start, seg_end, exclude_ranges)
            if eq_pos != -1:
                key = content[seg_start:eq_pos].strip()
                value = content[eq_pos + 1:seg_end]
                params.append(TemplateParam(key, value, seg_start, eq_pos + 1, seg_end))
            else:
                params.append(TemplateParam(None, content[seg_start:seg_end], seg_start, seg_start, seg_end))

        return TemplateCall(raw_name=raw_name, name=name, start=start, end=end, depth=depth, params=params)

    @staticmethod
    def _split_top_level(
        content: str, start: int, end: int, exclude_ranges: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """Découpe ``content[start:end]`` sur les « | » de premier
        niveau, en sautant entièrement les plages de ``exclude_ranges``
        (modèles imbriqués, liens wiki) pour ne jamais couper à
        l'intérieur d'un lien ou d'un sous-modèle."""
        ranges = sorted(r for r in exclude_ranges if r[0] < r[1])
        segments: List[Tuple[int, int]] = []
        seg_start = start
        i = start
        ridx = 0
        while i < end:
            while ridx < len(ranges) and ranges[ridx][1] <= i:
                ridx += 1
            if ridx < len(ranges) and ranges[ridx][0] <= i < ranges[ridx][1]:
                i = ranges[ridx][1]
                continue
            if content[i] == "|":
                segments.append((seg_start, i))
                seg_start = i + 1
                i += 1
                continue
            i += 1
        segments.append((seg_start, end))
        return segments

    @staticmethod
    def _find_top_level_equals(
        content: str, start: int, end: int, exclude_ranges: List[Tuple[int, int]]
    ) -> int:
        """Retourne la position du premier « = » de premier niveau dans
        ``content[start:end]`` (en sautant les plages exclues, comme
        pour le découpage sur « | »), ou -1 s'il n'y en a pas. Empêche
        un « = » présent à l'intérieur d'un sous-modèle ou d'un lien
        d'être pris pour le séparateur clé=valeur du segment courant."""
        ranges = sorted(r for r in exclude_ranges if r[0] < r[1])
        i = start
        ridx = 0
        while i < end:
            while ridx < len(ranges) and ranges[ridx][1] <= i:
                ridx += 1
            if ridx < len(ranges) and ranges[ridx][0] <= i < ranges[ridx][1]:
                i = ranges[ridx][1]
                continue
            if content[i] == "=":
                return i
            i += 1
        return -1

    @staticmethod
    def _normalize_template_name(raw_name: str) -> str:
        name = raw_name.strip()
        for prefix in ("subst:", "safesubst:", "msg:", "raw:", ":"):
            if name.lower().startswith(prefix):
                name = name[len(prefix):].strip()
        name = name.replace("_", " ")
        name = re.sub(r"\s+", " ", name)
        return name.lower()

    # ------------------------------------------------------------------ #
    # Vérifications (existantes + nouvelles)
    # ------------------------------------------------------------------ #

    def _detect_obsolete_templates(self, calls: List[TemplateCall]) -> None:
        try:
            obsolete = self.obsolete_template_provider.obsolete_templates()
        except Exception as exc:
            logger.warning("Fournisseur de modèles dépréciés indisponible, ignoré : %s", exc)
            return

        if not obsolete:
            return

        for call in calls:
            if call.name not in obsolete:
                continue
            replacement = obsolete.get(call.name)
            suggestion = ("{{" + replacement + "}}") if replacement else None
            description = "Modèle déprécié : {{" + call.raw_name.strip() + "}}"
            if replacement:
                description += " — remplacer par {{" + replacement + "}}"
            self.issues.append(Issue(
                issue_type="obsolete_template",
                description=description,
                position=call.start,
                original_text=("{{" + call.raw_name)[:60],
                suggested_text=suggestion,
                severity="medium",
            ))

    def _detect_empty_parameters(self, calls: List[TemplateCall]) -> None:
        for call in calls:
            for param in call.params:
                # Paramètre nommé vide
                if param.key is not None and not param.value.strip():
                    self.issues.append(Issue(
                        issue_type="empty_parameter",
                        description=(
                            f"Paramètre « {param.key} » vide dans "
                            "{{" + call.raw_name.strip() + "}}"
                        ),
                        position=param.key_start,
                        original_text=f"|{param.key}={param.value}",
                        suggested_text="",
                        severity="low",
                    ))
                # Paramètre positionnel vide
                elif param.key is None and not param.value.strip():
                    self.issues.append(Issue(
                        issue_type="empty_positional_parameter",
                        description=(
                            "Paramètre positionnel vide dans "
                            "{{" + call.raw_name.strip() + "}}"
                        ),
                        position=param.value_start,
                        original_text="|" + param.value,
                        suggested_text="",
                        severity="low",
                    ))
                # Clé vide avec valeur (|=valeur)
                elif param.key is not None and not param.key.strip():
                    self.issues.append(Issue(
                        issue_type="empty_parameter_key",
                        description=(
                            "Clé de paramètre vide (|=valeur) dans "
                            "{{" + call.raw_name.strip() + "}}"
                        ),
                        position=param.key_start,
                        original_text=f"|{param.key}={param.value}",
                        suggested_text="|" + param.value,
                        severity="medium",
                    ))

    def _detect_duplicate_parameters(self, calls: List[TemplateCall]) -> None:
        for call in calls:
            seen: Dict[str, TemplateParam] = {}
            for param in call.params:
                if param.key is None:
                    continue
                key_norm = param.key.strip().lower()
                if not key_norm:
                    continue
                if key_norm in seen:
                    self.issues.append(Issue(
                        issue_type="duplicate_parameter",
                        description=(
                            f"Paramètre « {param.key} » dupliqué dans "
                            "{{" + call.raw_name.strip() + "}} "
                            "(seule la dernière valeur est retenue par MediaWiki)"
                        ),
                        position=param.key_start,
                        original_text=f"|{param.key}={param.value}",
                        suggested_text=None,
                        severity="medium",
                    ))
                else:
                    seen[key_norm] = param

    def _detect_foreign_parameters(self, calls: List[TemplateCall]) -> None:
        citation_templates = self.config.citation_templates
        for call in calls:
            if call.name not in citation_templates:
                continue
            for param in call.params:
                if param.key is None:
                    continue
                key_norm = param.key.strip().lower()
                french_equivalent = ENGLISH_TO_FRENCH_PARAMS.get(key_norm)
                if not french_equivalent:
                    continue
                self.issues.append(Issue(
                    issue_type="english_parameter_name",
                    description=(
                        f"Paramètre anglais « {param.key} » dans "
                        "{{" + call.raw_name.strip() + "}} "
                        f"— utiliser « {french_equivalent} »"
                    ),
                    position=param.key_start,
                    original_text=param.key,
                    suggested_text=french_equivalent,
                    severity="low",
                ))

    # ---------- NOUVELLES DÉTECTIONS ----------

    def _detect_trailing_pipe(self, calls: List[TemplateCall]) -> None:
        """Détecte une barre verticale finale sans paramètre (ex. {{tpl|param=value| }})."""
        for call in calls:
            # Vérifier si le dernier paramètre est vide et que le texte se termine par |
            if not call.params:
                continue
            last_param = call.params[-1]
            # Si le dernier paramètre est positionnel et vide, et qu'il y a un pipe juste avant
            if last_param.key is None and not last_param.value.strip():
                # Vérifier si le caractère avant la position de début du paramètre est '|'
                if last_param.value_start > call.start + 2:
                    before = call.raw_name[last_param.value_start - call.start - 2]
                    if before == '|':
                        self.issues.append(Issue(
                            issue_type="trailing_pipe",
                            description=(
                                "Barre verticale finale inutile dans "
                                "{{" + call.raw_name.strip() + "}}"
                            ),
                            position=last_param.value_start - 1,
                            original_text="|",
                            suggested_text="",
                            severity="low",
                        ))

    def _detect_english_template_names(self, calls: List[TemplateCall]) -> None:
        """Détecte les appels à des modèles anglais connus et suggère l'équivalent français."""
        for call in calls:
            if call.name in ENGLISH_TEMPLATE_NAMES:
                french_name = ENGLISH_TEMPLATE_NAMES[call.name]
                self.issues.append(Issue(
                    issue_type="english_template_name",
                    description=(
                        f"Modèle anglais « {{ {call.raw_name.strip()} }} » — "
                        f"utiliser plutôt « {{ {french_name} }} »"
                    ),
                    position=call.start,
                    original_text=call.raw_name,
                    suggested_text=french_name,
                    severity="low",
                ))

    def _detect_excessive_length(self, calls: List[TemplateCall]) -> None:
        """Alerte sur les modèles très longs (problème de lisibilité)."""
        max_len = self.config.max_template_length
        for call in calls:
            length = call.end - call.start
            if length > max_len:
                self.issues.append(Issue(
                    issue_type="excessive_template_length",
                    description=(
                        f"Modèle très long ({length} caractères) — "
                        "envisager une simplification ou un découpage"
                    ),
                    position=call.start,
                    original_text=("{{" + call.raw_name)[:30] + "...",
                    suggested_text=None,
                    severity="low",
                ))

    # ------------------------------------------------------------------ #
    # Infobox-specific detection methods
    # ------------------------------------------------------------------ #

    def _detect_empty_infobox_fields(self, calls: List[TemplateCall]) -> None:
        """Détecte les champs vides dans les infoboxes qui pourraient être renseignés."""
        for call in calls:
            # Check if it's an infobox
            if not call.name.lower().startswith('infobox'):
                continue
            
            empty_params = []
            for param in call.params:
                if param.key and not param.value.strip():
                    empty_params.append(param.key)
            
            if empty_params:
                self.issues.append(Issue(
                    issue_type="empty_infobox_field",
                    description=(
                        f"Champs vides dans l'infobox {call.name} : {', '.join(empty_params[:5])}"
                        + (f" ({len(empty_params)} total)" if len(empty_params) > 5 else "")
                    ),
                    position=call.start,
                    original_text=("{{" + call.raw_name)[:50],
                    suggested_text=None,  # Manual review required
                    severity="medium"
                ))

    def _detect_infobox_text_mismatch(self, content: str, calls: List[TemplateCall]) -> None:
        """
        Détecte les incohérences entre le texte de l'article et l'infobox.
        C'est une vérification heuristique simplifiée.
        """
        for call in calls:
            if not call.name.lower().startswith('infobox'):
                continue
            
            # Extract key parameters from infobox
            param_values = {}
            for param in call.params:
                if param.key and param.value.strip():
                    param_values[param.key.lower().strip()] = param.value.strip()
            
            # Check for common mismatches (simplified)
            # For example: if infobox has a birth date but article text doesn't mention it
            # This is a placeholder - real implementation would be more sophisticated
            if 'naissance' in param_values or 'birth_date' in param_values:
                # Check if the birth date appears in the text
                birth_value = param_values.get('naissance', param_values.get('birth_date', ''))
                if birth_value and birth_value not in content[:1000]:  # Check lead section
                    self.issues.append(Issue(
                        issue_type="infobox_text_mismatch",
                        description=(
                            f"Date de naissance dans l'infobox ({birth_value}) "
                            "non trouvée dans le texte de l'introduction"
                        ),
                        position=call.start,
                        original_text=("{{" + call.raw_name)[:50],
                        suggested_text=None,
                        severity="low"
                    ))

    def _detect_broken_infobox_syntax(self, calls: List[TemplateCall]) -> None:
        """Détecte les erreurs de syntaxe dans les infoboxes."""
        for call in calls:
            if not call.name.lower().startswith('infobox'):
                continue
            
            # Check for unbalanced brackets in parameters
            for param in call.params:
                if param.value:
                    # Count opening and closing brackets
                    open_brackets = param.value.count('[')
                    close_brackets = param.value.count(']')
                    if open_brackets != close_brackets:
                        self.issues.append(Issue(
                            issue_type="broken_infobox_syntax",
                            description=(
                                f"Crochets déséquilibrés dans le paramètre {param.key} "
                                f"de l'infobox {call.name}"
                            ),
                            position=param.value_start,
                            original_text=f"|{param.key}={param.value[:30]}...",
                            suggested_text=None,
                            severity="medium"
                        ))
                    
                    # Check for unbalanced braces
                    open_braces = param.value.count('{')
                    close_braces = param.value.count('}')
                    if open_braces != close_braces:
                        self.issues.append(Issue(
                            issue_type="broken_infobox_syntax",
                            description=(
                                f"Accolades déséquilibrées dans le paramètre {param.key} "
                                f"de l'infobox {call.name}"
                            ),
                            position=param.value_start,
                            original_text=f"|{param.key}={param.value[:30]}...",
                            suggested_text=None,
                            severity="medium"
                        ))

    def _detect_infobox_wrong_parameters(self, calls: List[TemplateCall]) -> None:
        """
        Détecte les paramètres qui n'existent pas dans le modèle d'infobox.
        C'est une vérification simplifiée - une vraie vérification nécessiterait
        de consulter la documentation du modèle.
        """
        # Common infobox parameters (simplified list)
        common_infobox_params = {
            'nom', 'nom', 'image', 'légende', 'caption',
            'naissance', 'birth_date', 'décès', 'death_date',
            'nationalité', 'nationality', 'profession', 'occupation',
            'lieu de naissance', 'birth_place', 'lieu de décès', 'death_place',
        }
        
        for call in calls:
            if not call.name.lower().startswith('infobox'):
                continue
            
            unknown_params = []
            for param in call.params:
                if param.key:
                    key_lower = param.key.lower().strip()
                    # Check if it looks like a typo (e.g., similar to known param)
                    is_similar = any(
                        self._is_similar(key_lower, known)
                        for known in common_infobox_params
                    )
                    if not is_similar and key_lower not in common_infobox_params:
                        unknown_params.append(param.key)
            
            if unknown_params:
                self.issues.append(Issue(
                    issue_type="infobox_wrong_parameter",
                    description=(
                        f"Paramètres potentiellement incorrects dans l'infobox {call.name} : "
                        f"{', '.join(unknown_params[:3])}"
                        + (f" ({len(unknown_params)} total)" if len(unknown_params) > 3 else "")
                    ),
                    position=call.start,
                    original_text=("{{" + call.raw_name)[:50],
                    suggested_text=None,
                    severity="low"
                ))

    @staticmethod
    def _is_similar(s1: str, s2: str, threshold: float = 0.7) -> bool:
        """
        Check if two strings are similar using simple Levenshtein distance approximation.
        """
        if not s1 or not s2:
            return False
        
        # Simple similarity check based on common prefix/suffix
        if s1 in s2 or s2 in s1:
            return True
        
        # Check if they share a significant portion
        common_chars = sum(1 for c in s1 if c in s2)
        similarity = common_chars / max(len(s1), len(s2))
        
        return similarity >= threshold