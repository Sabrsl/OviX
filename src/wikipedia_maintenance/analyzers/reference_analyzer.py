"""
Analyzer for reference and source-related issues in Wikipedia articles.

Detects (conforme aux règles §8.1 / §8.2) :
    - Références <ref> cassées (non fermées, orphelines, mal imbriquées)
    - Références brutes (URL nue, [url], [url Libellé]) sans modèle bibliographique
    - Références en doublon (à fusionner via <ref name="x">)
    - Références en majuscules (à normaliser, en préservant sigles/acronymes)
    - ISBN en texte brut (devrait utiliser le paramètre isbn=)
    - Modèle bibliographique inadapté (ex. {{Lien web}} pour un ouvrage)
    - Références mal placées (ex. dans un titre de section)
    - Point final manquant avant </ref>
    - Liens morts / brisés (détection 404, optionnelle)
    - URLs de réseaux sociaux en référence (devraient aller en liens externes)
    - Références incomplètes (titre/site/date manquants)

Tous les checks sont non destructifs : ils préservent le contenu sourcé et
ne déplacent/suppriment jamais un appel de note. Les suggestions de correction
automatique ne sont produites que lorsqu'elles peuvent être générées de façon
sûre et réversible ; en cas d'ambiguïté (ex. sigle vs emphase typographique),
le check est levé en sévérité basse avec suggested_text=None, à valider
manuellement plutôt que corrigé à l'aveugle.
"""

from __future__ import annotations

import re
import logging
from typing import List, Optional, Dict, Set, Tuple
from urllib.parse import urlparse

from .base import BaseAnalyzer, Issue

logger = logging.getLogger(__name__)


class ReferenceAnalyzer(BaseAnalyzer):
    """Analyzes articles for reference and source-related issues."""

    # ---- Précompilation des patterns ----

    # Référence brute : <ref>https://...</ref>, avec ou sans name=, avec ou sans espace
    _BARE_REF_RE = re.compile(
        r'<ref(?P<name>\s+name=["\'][^"\']*["\'])?\s*>\s*(?P<url>https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+)\s*</ref>',
        re.IGNORECASE
    )

    # Lien nu en crochets : [url] ou [url Libellé] (hors <ref>...</ref>, traité séparément)
    _BRACKET_LINK_RE = re.compile(
        r'\[(https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+)(?:\s+([^\]]*))?\]'
    )

    # Toute balise <ref ...> ou </ref> ou <ref .../>, pour l'analyse de bonne formation
    _REF_TAG_RE = re.compile(r'<(/?ref)(\s+[^>]*)?(/?)>', re.IGNORECASE)

    # Référence nommée : <ref name="x"> ou <ref name="x" />
    _NAMED_REF_RE = re.compile(r'<ref\s+name=["\']([^"\']+)["\']\s*/?>', re.IGNORECASE)

    # Référence avec contenu complet : <ref ...>...</ref> (non autofermante)
    _REF_CONTENT_RE = re.compile(r'<ref(?P<attrs>[^>/]*)>(?P<content>.*?)</ref>', re.IGNORECASE | re.DOTALL)

    # Référence autofermante : <ref name="x" />
    _SELFCLOSING_REF_RE = re.compile(r'<ref\s+name=["\']([^"\']+)["\']\s*/>', re.IGNORECASE)

    # ISBN (ISBN-10 et ISBN-13, avec ou sans tirets)
    _ISBN_RE = re.compile(
        r'\b(?:ISBN\s*(?:-1[03])?\s*:?\s*)((?:\d[\ -]?){9}[\dXx]|(?:\d[\ -]?){13})\b',
        re.IGNORECASE
    )

    # Domaines de réseaux sociaux
    _SOCIAL_MEDIA_DOMAINS = {
        'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
        'tiktok.com', 'linkedin.com', 'youtube.com', 'threads.net',
        'www.twitter.com', 'www.x.com', 'www.facebook.com', 'www.instagram.com',
        'www.tiktok.com', 'www.linkedin.com', 'www.youtube.com', 'www.threads.net',
    }

    # Modèles de citation français
    _CITATION_TEMPLATES = {
        'lien web', 'article', 'ouvrage', 'chapitre', 'thèse',
        'périodique', 'site web', 'vidéo', 'podcast'
    }

    # Sigles/acronymes/exceptions à préserver tels quels lors de la normalisation de casse.
    # Liste non exhaustive : à compléter selon le domaine des articles traités.
    _ACRONYM_WHITELIST = {
        # Agences de presse internationales
        'AFP', 'AP', 'DPA', 'EFE', 'ANSA', 'REUTERS', 'UPI', 'TASS', 'XINHUA',

        # Médias / chaînes TV / radio (France + international)
        'RFI', 'BBC', 'CNN', 'FRANCE24', 'TV5MONDE', 'TV5', 'RTS', 'RTBF',
        'TF1', 'M6', 'BFM', 'BFMTV', 'LCI', 'RTL', 'RMC', 'NRJ', 'C8', 'W9',
        'FRANCE2', 'FRANCE3', 'FRANCE5', 'ARTE', 'CANAL+', 'NBC', 'ABC',
        'CBS', 'FOX', 'PBS', 'NPR', 'ITV', 'SKY', 'ARD', 'ZDF', 'RAI',
        'RTVE', 'ORTM', 'RTI', 'RTG', 'GRTV', 'SRC', 'CBC', 'ALJAZEERA',

        # Organisations internationales / institutions
        'ONU', 'UNESCO', 'OMS', 'FMI', 'UE', 'UA', 'OTAN', 'URSS', 'USA',
        'UK', 'UNICEF', 'HCR', 'OIF', 'OCI', 'BM', 'PNUD', 'OMC', 'OCDE',
        'UNRWA', 'PAM', 'FAO', 'AIEA', 'CPI', 'CIJ', 'CICR',

        # Organisations régionales (non limité à l'Afrique)
        'CEDEAO', 'CEEAC', 'UEMOA', 'CEMAC', 'BAD', 'UA', 'ASEAN', 'MERCOSUR',
        'ALENA', 'UNASUR', 'CARICOM', 'GCC', 'BRICS', 'G7', 'G8', 'G20',

        # Identifiants bibliographiques / techniques / web
        'ISBN', 'ISSN', 'DOI', 'PDF', 'URL', 'HTML', 'XML', 'JSON', 'API',
        'ID', 'IP', 'FAQ', 'CD', 'DVD', 'USB',

        # Politique / administration (France, générique)
        'PDG', 'DG', 'DRH', 'RH', 'SA', 'SARL', 'SAS', 'ONG', 'ASBL', 'ASBL',
        'CV', 'RGPD', 'RSE', 'PME', 'ETI', 'CAC40', 'INSEE', 'CNRS', 'CNIL',
        'ARCOM', 'CSA', 'HADOPI', 'SNCF', 'RATP', 'EDF', 'ENA', 'HEC',

        # Diplômes / titres académiques
        'PHD', 'MBA', 'BTS', 'DUT', 'DEA', 'DESS', 'LLM', 'MSC', 'BA', 'MA',

        # Sport
        'FIFA', 'UEFA', 'CAF', 'CONCACAF', 'CONMEBOL', 'CIO', 'NBA', 'NFL',
        'FFF', 'PSG', 'OM',

        # Économie / finance
        'PIB', 'TVA', 'BCE', 'FED', 'SEC', 'CAC', 'NASDAQ', 'NYSE',

        # Pays (codes usuels utilisés tels quels dans le texte)
        'USA', 'UK', 'RDC', 'RCA', 'EAU', 'RFA', 'RDA',
    }

    # Détection de template générique {{...}}, avec prise en charge de
    # l'imbrication (jusqu'à 2 niveaux) : {{Chapitre|titre=Le {{15e|régiment}}
    # de ...}} est fréquent (ordinaux, {{lang}}, {{nombre}}, etc. imbriqués
    # dans une référence bibliographique). L'ancienne regex ([^\{\}]+) ne
    # matchait jamais le template englobant dans ce cas — elle attrapait le
    # sous-template imbriqué à sa place, faussant tous les checks qui en
    # dépendent (type de modèle, point final, champs manquants).
    _TEMPLATE_RE = re.compile(
        r'\{\{((?:[^{}]|\{\{(?:[^{}]|\{\{[^{}]*\}\})*\}\})*)\}\}'
    )

    def __init__(
        self,
        language: str = 'fr',
        check_bare_refs: bool = False,  # DANGEREUX : génère {{Lien web|url=...|titre=}} avec titre vide
        check_broken_ref_tags: bool = False,  # suggested_text=None partout, détection pure
        check_duplicate_refs: bool = True,  # ✅ SÛR : transformation structurelle réversible
        check_uppercase_refs: bool = True,  # ✅ SÛR : refuse de corriger si ambiguous=True
        check_isbn_format: bool = False,  # DANGEREUX : fragment incomplet, pas d'instruction d'édition complète
        check_template_type: bool = False,  # suggested_text=None toujours, jugement éditorial requis
        check_missing_period: bool = True,  # ✅ SÛR : transformation triviale et déterministe
        check_period_before_ref_close: bool = False,  # Convention non universelle sur WP:FR
        check_broken_links: bool = False,  # Requires HTTP requests - viole contrainte "100% local"
        use_wayback_api: bool = False,  # Requires HTTP requests - viole contrainte "100% local"
        check_social_media_in_refs: bool = False,  # suggested_text=None, déplacement manuel requis
        check_incomplete_refs: bool = False,  # suggested_text=None, jugement éditorial requis
        api_session=None,
    ):
        """
        Args:
            language: Language code for template names.
            check_bare_refs: Detect bare URL / bracket-link references. DANGEREUX par défaut.
            check_broken_ref_tags: Detect malformed/unclosed/orphan <ref> tags. Désactivé par défaut.
            check_duplicate_refs: Detect duplicate references. ✅ Activé par défaut.
            check_uppercase_refs: Detect uppercase in references. ✅ Activé par défaut.
            check_isbn_format: Detect ISBN in plain text. DANGEREUX par défaut.
            check_template_type: Detect wrong template types. Désactivé par défaut.
            check_missing_period: Detect missing trailing period before </ref>. ✅ Activé par défaut.
            check_period_before_ref_close: Detect }}.</ref> pattern. Désactivé par défaut (convention non universelle).
            check_broken_links: Check for 404 links (requires API). Désactivé par défaut.
            use_wayback_api: Use Wayback Machine for broken links. Désactivé par défaut.
            check_social_media_in_refs: Detect social media URLs in refs. Désactivé par défaut.
            check_incomplete_refs: Detect incomplete references. Désactivé par défaut.
            api_session: Optional requests.Session for API calls.
        """
        super().__init__()
        self.language = language.lower()
        self.check_bare_refs = check_bare_refs
        self.check_broken_ref_tags = check_broken_ref_tags
        self.check_duplicate_refs = check_duplicate_refs
        self.check_uppercase_refs = check_uppercase_refs
        self.check_isbn_format = check_isbn_format
        self.check_template_type = check_template_type
        self.check_missing_period = check_missing_period
        self.check_period_before_ref_close = check_period_before_ref_close
        self.check_broken_links = check_broken_links
        self.use_wayback_api = use_wayback_api
        self.check_social_media_in_refs = check_social_media_in_refs
        self.check_incomplete_refs = check_incomplete_refs
        self._session = api_session

        # Cache for link status
        self._link_status_cache: Dict[str, bool] = {}

        if self.check_broken_links or self.use_wayback_api:
            try:
                import requests
                if self._session is None:
                    self._session = requests.Session()
            except ImportError:
                logger.warning("requests not installed; link checking disabled.")
                self.check_broken_links = False
                self.use_wayback_api = False

    def analyze(self, content: str) -> List[Issue]:
        """
        Analyze content for reference issues.

        Args:
            content: Article wikicode content

        Returns:
            List of detected issues (sorted by position)
        """
        self.clear_issues()
        if not content:
            return self.issues

        # ---- Intégrité structurelle des balises (prioritaire : tout le reste
        # peut être bruité si les balises sont cassées) ----
        if self.check_broken_ref_tags:
            self._detect_broken_ref_tags(content)

        # ---- Core checks ----
        if self.check_bare_refs:
            self._detect_bare_refs(content)

        if self.check_duplicate_refs:
            self._detect_duplicate_refs(content)

        if self.check_uppercase_refs:
            self._detect_uppercase_refs(content)

        if self.check_isbn_format:
            self._detect_isbn_in_text(content)

        if self.check_template_type:
            self._detect_wrong_template_type(content)

        if self.check_missing_period:
            self._detect_missing_period(content)

        if self.check_period_before_ref_close:
            self._detect_period_before_ref_close(content)

        # ---- Position-based checks ----
        self._detect_moved_refs(content)

        # ---- External link checks ----
        if self.check_broken_links:
            self._detect_broken_links(content)

        if self.check_social_media_in_refs:
            self._detect_social_media_in_refs(content)

        if self.check_incomplete_refs:
            self._detect_incomplete_refs(content)

        # Sort issues by position
        self.issues.sort(key=lambda i: i.position)
        return self.issues

    def get_analyzer_name(self) -> str:
        return "ReferenceAnalyzer"

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _detect_broken_ref_tags(self, content: str) -> None:
        """
        Détecte les balises <ref> mal formées : non fermées, orphelines
        (</ref> sans ouverture), ou mal imbriquées (<ref> imbriquée dans
        une autre <ref> avant fermeture).

        Règle §8.1 : "Vérifier ... la syntaxe des <ref> existantes :
        fermeture correcte ... absence de balise orpheline ou mal imbriquée."
        Ces checks sont purement structurels et ne touchent jamais au contenu
        de la référence — seule la balise elle-même est en cause.
        """
        stack: List[Tuple[int, str]] = []  # (position, raw_tag)

        for match in self._REF_TAG_RE.finditer(content):
            tag_name = match.group(1).lower()          # "ref" ou "/ref"
            attrs = match.group(2) or ""
            self_closing = bool(match.group(3))          # "/" avant ">"
            raw = match.group(0)
            pos = match.start()

            if tag_name == 'ref':
                if self_closing:
                    # <ref name="x" /> : doit obligatoirement avoir un name=
                    if 'name=' not in attrs.lower():
                        self.issues.append(Issue(
                            issue_type="broken_ref_tag",
                            description="Balise <ref /> autofermante sans attribut name= (référence non identifiable)",
                            position=pos,
                            original_text=raw,
                            suggested_text=None,
                            severity="critical"
                        ))
                    continue
                # Ouverture non autofermante : empile, en attente de </ref>
                if stack:
                    # Imbrication : une <ref> ouverte avant que la précédente soit fermée
                    self.issues.append(Issue(
                        issue_type="broken_ref_tag",
                        description="Balise <ref> imbriquée dans une <ref> non fermée (imbrication invalide)",
                        position=pos,
                        original_text=raw,
                        suggested_text=None,
                        severity="critical"
                    ))
                stack.append((pos, raw))
            else:  # "/ref"
                if not stack:
                    # Fermeture orpheline, aucune ouverture correspondante
                    self.issues.append(Issue(
                        issue_type="broken_ref_tag",
                        description="Balise </ref> orpheline (aucune <ref> ouvrante correspondante)",
                        position=pos,
                        original_text=raw,
                        suggested_text=None,
                        severity="critical"
                    ))
                else:
                    stack.pop()

        # Toute <ref> restée sur la pile n'a jamais été fermée
        for pos, raw in stack:
            self.issues.append(Issue(
                issue_type="broken_ref_tag",
                description="Balise <ref> jamais fermée (</ref> manquante)",
                position=pos,
                original_text=raw,
                suggested_text=None,
                severity="critical"
            ))

        # Balises <ref name="x" /> orphelines : name= qui ne correspond à aucune
        # définition complète <ref name="x">...</ref> ailleurs dans l'article.
        # Extraction propre des noms définis (avec contenu complet)
        defined_names = set()
        for m in self._REF_CONTENT_RE.finditer(content):
            name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', m.group('attrs') or '')
            if name_match:
                defined_names.add(name_match.group(1))

        for match in self._SELFCLOSING_REF_RE.finditer(content):
            name = match.group(1)
            if name not in defined_names:
                self.issues.append(Issue(
                    issue_type="broken_ref_tag",
                    description=f'Référence orpheline <ref name="{name}" /> : aucune définition complète correspondante dans l\'article',
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=None,
                    severity="critical"
                ))

    def _detect_bare_refs(self, content: str) -> None:
        """
        Détecte les références brutes : <ref>https://...</ref> (nommée ou non),
        ainsi que les liens nus en crochets [url] / [url Libellé], comme prévu
        au §8.2. La correction proposée conserve l'URL à l'identique (correction
        de forme uniquement, jamais un ajout de source).
        """
        for match in self._BARE_REF_RE.finditer(content):
            url = match.group('url')
            name_attr = match.group('name') or ""
            suggestion = f'<ref{name_attr}>{{{{Lien web|url={url}|titre=}}}}</ref>'
            self.issues.append(Issue(
                issue_type="bare_ref",
                description="Référence brute URL (utiliser {{Lien web}} ou modèle approprié)",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=suggestion,
                severity="high"
            ))

        # Liens nus en crochets, seulement s'ils sont à l'intérieur d'un <ref>...</ref>
        # (un [url] en dehors d'un <ref> est un lien externe classique, pas une référence)
        for ref_match in self._REF_CONTENT_RE.finditer(content):
            ref_content = ref_match.group('content')
            for bl in self._BRACKET_LINK_RE.finditer(ref_content):
                bracket_content = bl.group(0)
                
                # CRITICAL: If the bracket content already contains {{ or }}, it's malformed
                # (e.g., [url...{{Autorité|...}}]) - attempting auto-conversion will corrupt
                # the wikicode. Flag for manual review instead.
                if '{{' in bracket_content or '}}' in bracket_content:
                    self.issues.append(Issue(
                        issue_type="bare_ref_malformed",
                        description="Lien nu en crochets avec template intégré (à vérifier manuellement) : risque de corruption",
                        position=ref_match.start('content') + bl.start(),
                        original_text=bl.group(0),
                        suggested_text=None,  # Manual review required
                        severity="high"
                    ))
                    continue
                
                url = bl.group(1)
                label = (bl.group(2) or "").strip()
                abs_pos = ref_match.start('content') + bl.start()
                titre_part = f'|titre={label}' if label else '|titre='
                self.issues.append(Issue(
                    issue_type="bare_ref",
                    description="Lien nu en crochets dans une référence (utiliser {{Lien web}} ou modèle approprié)",
                    position=abs_pos,
                    original_text=bl.group(0),
                    suggested_text=f'{{{{Lien web|url={url}{titre_part}}}}}',
                    severity="high"
                ))

    def _detect_duplicate_refs(self, content: str) -> None:
        """
        Détecte les références en doublon (même contenu complet) et propose
        une fusion via <ref name="x">, conforme au §8.1 :
        - la première occurrence garde la définition complète, avec un name= ajouté
        - les occurrences suivantes deviennent <ref name="x" />
        - la position et l'appel de chaque occurrence restent inchangés,
          seule la FORME de l'appel est modifiée (jamais son emplacement).
        Le nom généré est dérivé du contenu (slug court) pour rester stable et
        lisible ; en cas de collision avec un name= déjà présent dans l'article,
        un suffixe numérique est ajouté.
        """
        ref_contents: Dict[str, List[Tuple[int, re.Match]]] = {}

        existing_names: Set[str] = set(
            m.group(1) for m in self._NAMED_REF_RE.finditer(content)
        )

        for match in self._REF_CONTENT_RE.finditer(content):
            # Ignore les références déjà nommées : elles sont déjà réutilisables
            # via <ref name="x" /> et ne doivent pas être re-fusionnées.
            if re.search(r'name\s*=', match.group('attrs') or '', re.IGNORECASE):
                continue

            ref_content = match.group('content').strip()
            normalized = re.sub(r'\s+', ' ', ref_content)

            ref_contents.setdefault(normalized, []).append((match.start(), match))

        used_names: Set[str] = set(existing_names)

        for normalized, occurrences in ref_contents.items():
            if len(occurrences) <= 1:
                continue

            base_name = self._generate_ref_name(normalized)
            ref_name = base_name
            suffix = 2
            while ref_name in used_names:
                ref_name = f"{base_name}{suffix}"
                suffix += 1
            used_names.add(ref_name)

            first_pos, first_match = occurrences[0]
            self.issues.append(Issue(
                issue_type="duplicate_ref",
                description=f'Première occurrence d\'une référence en doublon : ajouter name="{ref_name}" (ne pas déplacer)',
                position=first_pos,
                original_text=first_match.group(0),
                suggested_text=f'<ref name="{ref_name}">{first_match.group("content")}</ref>',
                severity="medium"
            ))

            for pos, m in occurrences[1:]:
                self.issues.append(Issue(
                    issue_type="duplicate_ref",
                    description=f'Référence en doublon : remplacer par <ref name="{ref_name}" /> (position et appel inchangés)',
                    position=pos,
                    original_text=m.group(0),
                    suggested_text=f'<ref name="{ref_name}" />',
                    severity="medium"
                ))

    @staticmethod
    def _generate_ref_name(normalized_content: str) -> str:
        """
        Génère un nom de référence court et stable à partir du contenu,
        pour utilisation dans <ref name="x">. Purement dérivé du texte
        existant (ex. domaine de l'URL ou premiers mots), jamais inventé.
        """
        url_match = re.search(r'https?://(?:www\.)?([a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+)', normalized_content)
        if url_match:
            domain = re.sub(r'[^a-zA-Z0-9]', '', url_match.group(1).split('.')[0])
            if domain:
                return domain.lower()[:20]

        words = re.findall(r'[A-Za-zÀ-ÿ0-9]+', normalized_content)
        slug = ''.join(w.capitalize() for w in words[:3])
        return (slug or "ref")[:20]

    def _detect_uppercase_refs(self, content: str) -> None:
        """
        Détecte les références dont le contenu est entièrement ou majoritairement
        en capitales et propose une normalisation qui PRÉSERVE les sigles,
        acronymes et initiales de noms propres (§8.1), au lieu d'un simple
        .lower() qui écraserait tout.

        Stratégie de correction, mot par mot :
        - mot dans la liste blanche d'acronymes -> inchangé
        - mot entièrement en majuscules et <= 4 lettres, hors liste blanche
          -> ambigu (peut être un sigle non répertorié) : pas de correction
          automatique, signalé en sévérité basse pour vérification manuelle
        - mot entièrement en majuscules et > 4 lettres -> traité comme de
          l'emphase typographique, remis en Capitale-initiale + minuscules
        - reste du texte -> inchangé
        """
        for match in self._REF_CONTENT_RE.finditer(content):
            ref_content = match.group('content')
            if not ref_content:
                continue

            letters = [c for c in ref_content if c.isalpha()]
            if not letters:
                continue

            uppercase_count = sum(1 for c in letters if c.isupper())
            uppercase_ratio = uppercase_count / len(letters)

            if uppercase_ratio <= 0.5 or len(letters) <= 5:
                continue

            normalized_text, ambiguous = self._normalize_case_preserving_acronyms(ref_content)

            # Toujours proposer la correction (sigles préservés)
            suggestion = content[match.start():match.start('content')] + normalized_text + '</ref>'
            self.issues.append(Issue(
                issue_type="uppercase_ref",
                description="Référence en majuscules (normalisée en préservant sigles/acronymes)",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=suggestion,
                severity="low"
            ))

    def _normalize_case_preserving_acronyms(self, text: str) -> Tuple[str, bool]:
        """
        Normalise la casse d'un texte en majuscules en préservant les sigles
        connus (liste blanche) et en préservant la casse des mots courts
        tout-en-capitales (potentiels sigles) pour éviter de les casser.

        Returns:
            (texte_normalisé, ambiguous) — ambiguous=False car on corrige
            automatiquement en préservant les sigles (connus ou non).
        """
        ambiguous = False

        def repl(m: re.Match) -> str:
            word = m.group(0)
            if not word.isalpha() or not word.isupper():
                return word
            upper_word = word.upper()
            if upper_word in self._ACRONYM_WHITELIST:
                return word
            # Mots courts tout-en-capitales : on préserve leur casse (sigles potentiels)
            if len(word) <= 4:
                return word
            # Mot long tout-en-capitales : emphase typographique probable
            return word[0].upper() + word[1:].lower()

        result = re.sub(r'[A-ZÀ-Ý]+', repl, text)
        return result, False

    def _detect_isbn_in_text(self, content: str) -> None:
        """
        Détecte les ISBN en texte brut qui devraient utiliser le paramètre
        isbn= dans un modèle de citation.
        """
        for match in self._ISBN_RE.finditer(content):
            isbn_raw = match.group(1)
            isbn = re.sub(r'[\ -]', '', isbn_raw)
            start = match.start()

            before = content[max(0, start - 100):start]
            if '{{' in before and '}}' not in before:
                continue

            if '<ref' in before:
                after_last_ref_open = before[before.rfind('<ref'):]
                if 'isbn=' in after_last_ref_open.lower():
                    continue

            self.issues.append(Issue(
                issue_type="isbn_in_text",
                description="ISBN en texte brut (utiliser paramètre isbn= dans modèle de citation)",
                position=start,
                original_text=match.group(0),
                suggested_text=f'|isbn={isbn}',
                severity="medium"
            ))

    def _detect_wrong_template_type(self, content: str) -> None:
        """
        Détecte les modèles bibliographiques inadaptés à la nature de la
        source. Heuristique renforcée : exige plusieurs indices combinés
        pour limiter les faux positifs (un {{Lien web}} avec un simple
        éditeur= n'est pas forcément un livre).
        """
        for match in self._TEMPLATE_RE.finditer(content):
            template_content = match.group(1).strip()
            template_name = template_content.split('|')[0].strip().lower()

            if template_name not in self._CITATION_TEMPLATES:
                continue

            if template_name == 'lien web':
                book_indicators = sum(1 for pat in (
                    r'\béditeur\s*=', r'\bisbn\s*=', r'\bpages\s*=', r'\blieu\s*='
                ) if re.search(pat, template_content, re.IGNORECASE))
                has_url = re.search(r'\burl\s*=\s*\S', template_content, re.IGNORECASE)

                # isbn= seul est un indicateur fort et suffisant (un lien web n'a
                # normalement jamais d'ISBN) ; sinon exiger >= 2 indices ET
                # l'absence d'url renseignée.
                strong_signal = re.search(r'\bisbn\s*=\s*\S', template_content, re.IGNORECASE)
                if strong_signal or (book_indicators >= 2 and not has_url):
                    self.issues.append(Issue(
                        issue_type="wrong_template_type",
                        description="{{Lien web}} probablement utilisé pour un livre (vérifier / utiliser {{Ouvrage}})",
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="low"
                    ))

            elif template_name == 'ouvrage':
                if re.search(r'\b(?:url|site web|consulté le)\s*=\s*\S', template_content, re.IGNORECASE):
                    self.issues.append(Issue(
                        issue_type="wrong_template_type",
                        description="{{Ouvrage}} utilisé pour une source web (vérifier / utiliser {{Lien web}})",
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="low"
                    ))

    def _detect_missing_period(self, content: str) -> None:
        """
        Détecte l'absence de point final avant </ref> pour les références
        utilisant un modèle bibliographique reconnu (§8.1 : "Toute référence
        utilisant un de ces modèles se termine par un point avant </ref>.").
        
        NOTE : Exclut les ref dont le contenu est uniquement des modèles
        sans texte libre (ex. {{Lien web|...}} seul), car l'ajout de point
        n'est pas une convention standard pour les modèles structurés.
        """
        for match in self._REF_CONTENT_RE.finditer(content):
            ref_content = match.group('content')
            template_match = self._TEMPLATE_RE.search(ref_content)
            if not template_match:
                continue
            template_name = template_match.group(1).split('|')[0].strip().lower()
            if template_name not in self._CITATION_TEMPLATES:
                continue

            trimmed = ref_content.rstrip()
            if not trimmed:
                continue
            if trimmed.endswith('.'):
                continue

            # Vérifier si le contenu est uniquement des modèles sans texte libre
            # Supprimer tous les modèles pour voir s'il reste du texte
            without_templates = self._TEMPLATE_RE.sub('', trimmed).strip()
            # S'il ne reste que du whitespace, c'est uniquement des modèles
            if not without_templates or without_templates.isspace():
                continue

            self.issues.append(Issue(
                issue_type="missing_period",
                description="Point final manquant avant </ref>",
                position=match.start(),
                original_text=match.group(0),
                suggested_text=content[match.start():match.start('content')] + trimmed + '.</ref>',
                severity="low"
            ))

    def _detect_moved_refs(self, content: str) -> None:
        """
        Détecte les références mal placées (ex. dans un titre de section).
        """
        lines = content.split('\n')
        search_offset = 0
        for line in lines:
            pos = content.find(line, search_offset)
            if line.strip().startswith('=') and '<ref>' in line:
                self.issues.append(Issue(
                    issue_type="moved_ref",
                    description="Référence dans un titre de section (déplacer dans le texte)",
                    position=pos,
                    original_text=line.strip(),
                    suggested_text=None,
                    severity="critical"
                ))
            search_offset = pos + len(line) if pos != -1 else search_offset + len(line) + 1

    def _detect_period_before_ref_close(self, content: str) -> None:
        """
        Détecte le motif }}.</ref> où le point se trouve
        entre la fin d'un modèle et la fermeture de la référence.
        """
        pattern = r'\}\}\.\s*</ref>'

        for match in re.finditer(pattern, content):
            self.issues.append(
                Issue(
                    issue_type="period_before_ref_close",
                    description="Point placé entre la fin du modèle et </ref>",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text="}}</ref>.",
                    severity="low"
                )
            )

    def _detect_broken_links(self, content: str) -> None:
        """
        Détecte les liens morts/brisés (HTTP 404) dans les références.
        Nécessite des requêtes HTTP, désactivé par défaut.
        """
        url_pattern = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+', re.IGNORECASE)

        for match in url_pattern.finditer(content):
            url = match.group()

            if url in self._link_status_cache:
                if not self._link_status_cache[url]:
                    self.issues.append(Issue(
                        issue_type="broken_link",
                        description=f"Lien mort (404) : {url}",
                        position=match.start(),
                        original_text=url,
                        suggested_text=None,
                        severity="medium"
                    ))
                continue

            if self._check_link_status(url):
                self._link_status_cache[url] = True
            else:
                self._link_status_cache[url] = False
                self.issues.append(Issue(
                    issue_type="broken_link",
                    description=f"Lien mort (404) : {url}",
                    position=match.start(),
                    original_text=url,
                    suggested_text=None,
                    severity="medium"
                ))

    def _detect_social_media_in_refs(self, content: str) -> None:
        """
        Détecte les URLs de réseaux sociaux à l'intérieur d'une référence,
        qui devraient être déplacées vers la section Liens externes.
        """
        url_pattern = re.compile(r'https?://[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=%]+', re.IGNORECASE)

        for match in url_pattern.finditer(content):
            url = match.group()
            parsed = urlparse(url)

            if parsed.netloc.lower() in self._SOCIAL_MEDIA_DOMAINS:
                start = match.start()
                before = content[max(0, start - 10):start]
                if '<ref>' in before:
                    self.issues.append(Issue(
                        issue_type="social_media_in_ref",
                        description=f"URL de réseau social dans référence (déplacer vers Liens externes) : {parsed.netloc}",
                        position=start,
                        original_text=url,
                        suggested_text=None,
                        severity="medium"
                    ))

    def _detect_incomplete_refs(self, content: str) -> None:
        """
        Détecte les références utilisant un modèle bibliographique reconnu
        mais auxquelles il manque titre/site/date.
        """
        for match in self._REF_CONTENT_RE.finditer(content):
            ref_content = match.group('content')

            template_match = self._TEMPLATE_RE.search(ref_content)
            if not template_match:
                continue

            template_full = template_match.group(1)
            template_name = template_full.split('|')[0].strip().lower()
            if template_name not in self._CITATION_TEMPLATES:
                continue

            if not re.search(r'\b(?:titre|title)\s*=\s*\S', template_full, re.IGNORECASE):
                self.issues.append(Issue(
                    issue_type="incomplete_ref",
                    description="Référence sans titre (paramètre titre= manquant ou vide)",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=None,
                    severity="low"
                ))

            # {{Ouvrage}} utilise éditeur=, pas systématiquement site= : on ne
            # réclame "site" que pour les modèles web-oriented.
            if template_name in ('lien web', 'site web', 'vidéo', 'podcast'):
                if not re.search(r'\b(?:site|website|éditeur|publisher)\s*=\s*\S', template_full, re.IGNORECASE):
                    self.issues.append(Issue(
                        issue_type="incomplete_ref",
                        description="Référence sans site (paramètre site= manquant ou vide)",
                        position=match.start(),
                        original_text=match.group(0),
                        suggested_text=None,
                        severity="low"
                    ))

            if not re.search(r'\b(?:date|année|year)\s*=\s*\S', template_full, re.IGNORECASE):
                self.issues.append(Issue(
                    issue_type="incomplete_ref",
                    description="Référence sans date (paramètre date= manquant ou vide)",
                    position=match.start(),
                    original_text=match.group(0),
                    suggested_text=None,
                    severity="low"
                ))

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _check_link_status(self, url: str) -> bool:
        """
        Vérifie si une URL est accessible (True si OK, False si 404/erreur).
        Utilise une requête HEAD pour éviter de télécharger le contenu complet ;
        certains serveurs rejettent HEAD, on retente alors en GET léger.
        """
        if not self._session:
            return True

        try:
            response = self._session.head(url, timeout=5, allow_redirects=True)
            if response.status_code == 405:  # Method Not Allowed -> retry GET
                response = self._session.get(url, timeout=5, allow_redirects=True, stream=True)
            return response.status_code < 400
        except Exception as e:
            logger.debug(f"Error checking link {url}: {e}")
            return False