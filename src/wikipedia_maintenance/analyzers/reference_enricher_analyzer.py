"""
Reference Enricher Analyzer

SINGLE OBJECTIVE:
Enrich healthy reference templates by adding missing |site= and |consulté le= parameters.

ONLY IF:
- Link is HEALTHY (not DEAD, not REVIEW_REQUIRED, not TEMPORARY_ERROR)
- URL is syntactically valid
- URL is in reference scope (<ref> or citation template)
- Template is recognized and supported
- Parameters are missing or empty (or, for |site=, present as plain text and
  upgradeable to a mapped internal link — see _get_site_parameter_if_missing)
- Template supports the parameter (e.g., ouvrage doesn't get |site=)
- série/collection not present (for |site= auto-fill)

STATUS CLASSIFICATION:
- ENRICHMENT_APPLIED: Enrichment successfully applied (site/consulté le added or upgraded)
- NO_ENRICHMENT_NEEDED: Template already has required parameters or no eligible upgrade
- NO_ENRICHMENT: Reference not eligible for enrichment (unhealthy link, unsupported template,
  no template found, technical error, etc.)

POLICY DECISIONS:
- consulté le dependency: |consulté le= is ONLY added when |site= is also being added or upgraded.
  This avoids polluting Wikipedia with trivial consulté le-only additions and maintains the
  "FEW ENRICHMENTS" philosophy. If |site= cannot be determined or is already present, |consulté le=
  will not be added even if missing.

Philosophy: FEW ENRICHMENTS + VERY HIGH CERTAINTY + ZERO UNRELATED CHANGES
"""

import re
import logging
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from .base import BaseAnalyzer, Issue
from wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult, LinkChecker
from wikipedia_maintenance.utils.url_extraction import UrlExtractor
from wikipedia_maintenance.utils.url_metadata import UrlMetadataExtractor
from wikipedia_maintenance.utils.reference_enricher_analyzer_config import ReferenceEnricherConfig
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplate, ReferenceTemplateHelper
from wikipedia_maintenance.utils.template_replacement_validator import TemplateReplacementValidator

logger = logging.getLogger(__name__)

# Parameter name variants Wikipedia templates use interchangeably for the
# same semantic slot. Centralized so every lookup site stays consistent
# instead of drifting (this was the root cause of bug #6: only 'site' had
# both variants checked, while 'consulté le' silently missed 'Consulté le').
SITE_PARAM_VARIANTS = ('site', 'Site')
CONSULTE_LE_PARAM_VARIANTS = ('consulté le', 'Consulté le', 'consulte le')
SERIE_PARAM_VARIANTS = ('série', 'Série')
COLLECTION_PARAM_VARIANTS = ('collection', 'Collection')
EDITEUR_PARAM_VARIANTS = ('éditeur', 'Éditeur')
ALTERNATIVE_SITE_PARAM_VARIANTS = ('website', 'Website', 'périodique', 'Périodique', 'work', 'Work')


def _get_param_any(parameters: Dict[str, str], variants: tuple) -> Optional[str]:
    """Return the first non-None value found among the given parameter
    name variants, or None if none of them are present."""
    for name in variants:
        value = parameters.get(name)
        if value is not None:
            return value
    return None


class ReferenceEnricherAnalyzer(BaseAnalyzer):
    """
    Reference Enricher Analyzer - Single-Objective Version.

    Enriches healthy reference templates by adding missing |site= and |consulté le= parameters.
    """

    # Backward compatibility constants - actual values managed by ReferenceEnricherConfig
    DEFAULT_TIMEOUT = 10
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_MAX_CHECKS_PER_ARTICLE = 50

    def __init__(self, name: str = None,
                 timeout: int = None,
                 max_retries: int = None,
                 max_checks_per_article: int = None,
                 enable_site_fill: bool = None,
                 enable_consulte_le_fill: bool = None):
        super().__init__(name)

        # _load_config() may set self.timeout / self.max_retries /
        # self.max_checks_per_article / self.enable_site_fill / self.enable_consulte_le_fill
        # from config.yaml. It must run before the getattr(...) fallbacks
        # below so a loaded config value is visible to them.
        self._load_config()

        # Priority: explicit constructor arg > value loaded from config.yaml > hardcoded default
        self.timeout = (
            timeout if timeout is not None
            else getattr(self, 'timeout', ReferenceEnricherConfig.DEFAULT_TIMEOUT)
        )
        self.max_retries = (
            max_retries if max_retries is not None
            else getattr(self, 'max_retries', ReferenceEnricherConfig.DEFAULT_MAX_RETRIES)
        )
        self.max_checks_per_article = (
            max_checks_per_article if max_checks_per_article is not None
            else getattr(self, 'max_checks_per_article', ReferenceEnricherConfig.DEFAULT_MAX_CHECKS_PER_ARTICLE)
        )
        self.enable_site_fill = (
            enable_site_fill if enable_site_fill is not None
            else getattr(self, 'enable_site_fill', ReferenceEnricherConfig.DEFAULT_ENABLE_SITE_FILL)
        )
        self.enable_consulte_le_fill = (
            enable_consulte_le_fill if enable_consulte_le_fill is not None
            else getattr(self, 'enable_consulte_le_fill', ReferenceEnricherConfig.DEFAULT_ENABLE_CONSULTE_LE_FILL)
        )

        self.link_checker = LinkChecker(timeout=self.timeout, max_retries=self.max_retries)
        self.reference_template_helper = ReferenceTemplateHelper()
        self.template_validator = TemplateReplacementValidator()

        # Caches specific to this analyzer (not shared with DeadLinkAnalyzer)
        self._check_cache: Dict[str, LinkCheckResult] = {}
        self._template_cache: Dict[str, Any] = {}
        self._checks_count = 0

    def _load_config(self) -> None:
        try:
            config = ReferenceEnricherConfig.load()

            if config.validate():
                self.timeout = config.timeout
                self.max_retries = config.max_retries
                self.max_checks_per_article = config.max_checks_per_article
                self.enable_site_fill = config.enable_site_fill
                self.enable_consulte_le_fill = config.enable_consulte_le_fill
            else:
                logger.warning("Invalid configuration loaded, using defaults")
        except Exception as e:
            logger.warning(f"Failed to load config: {type(e).__name__}: {e}. Using defaults.")

    def get_analyzer_name(self) -> str:
        return "ReferenceEnricherAnalyzer"

    def _is_url_syntactically_valid(self, url: str) -> bool:
        """
        Check if URL is syntactically valid before attempting network requests.
        """
        from wikipedia_maintenance.utils.link_checker import _load_academic_publisher_domains
        excluded_domains = _load_academic_publisher_domains()
        return UrlExtractor.is_syntactically_valid(url, excluded_domains)

    def _is_url_in_reference_scope(self, content: str, url: str, url_position: int) -> bool:
        """
        Vérifie si l'URL est dans le périmètre d'une référence (balise <ref> ou template de citation).
        """
        for ref_match in re.finditer(r'<ref[^>]*>(.*?)</ref>', content, re.DOTALL):
            if ref_match.start() <= url_position < ref_match.end():
                return True

        template = self._get_cached_reference_template(content, url, url_position)
        return template is not None

    def _get_cached_reference_template(self, content: str, url: str, url_position: int):
        """
        Get reference template with caching to avoid redundant lookups.
        """
        cache_key = f"{url}:{url_position}"
        if cache_key not in self._template_cache:
            try:
                self._template_cache[cache_key] = self.reference_template_helper.find_reference_template(
                    content, url, url_position
                )
            except Exception as e:
                logger.warning(
                    f"TEMPLATE_LOOKUP_FAILED | url={url} | position={url_position} | "
                    f"error={type(e).__name__}: {e}"
                )
                self._template_cache[cache_key] = None
        return self._template_cache[cache_key]

    def _resolve_site_value(self, url: str) -> Optional[str]:
        """
        Derive the display value for |site= from a URL's domain, resolving
        archive URLs to their original domain first. Returns None if no
        reliable value can be derived (never invent a value).
        """
        original_url = url
        if UrlExtractor.is_archive_url(url):
            extracted_original = UrlExtractor.extract_original_from_archive(url)
            if extracted_original:
                original_url = extracted_original
                logger.info(f"Extracted original URL from archive for site extraction: {extracted_original}")

        domain = UrlMetadataExtractor.extract_site_name(original_url)
        if not domain:
            return None

        try:
            return self.reference_template_helper._resolve_site_display_name(domain)
        except Exception as e:
            logger.warning(
                f"SITE_DISPLAY_NAME_RESOLUTION_FAILED | url={url} | domain={domain} | "
                f"error={type(e).__name__}: {e}"
            )
            return None

    def _get_site_parameter_if_missing(self, template: ReferenceTemplate, url: str) -> Optional[str]:
        """
        Decide the value (if any) that should be written to |site= for this
        template/URL pair. Three possible outcomes:
          - None: nothing to do (already has a good value, template opts
            out of |site=, or no reliable value could be derived).
          - A value: either filling an empty/absent |site=, or upgrading an
            existing plain-text |site= to a mapped internal-link form.

        STRICT POLICY:
        - Check BOTH 'site' and 'Site' parameter variants.
        - Never touch a value that is already an internal link [[...]].
        - Never fill if an alternative native parameter (website/périodique/work)
          already carries the same semantic role, to avoid duplicated info.
        - Never auto-fill if série/collection present (manually curated context).
        """
        # Normalize template name for comparison to handle case/spacing variations
        normalized_template_name = template.template_name.lower().replace('_', ' ')
        if normalized_template_name in self.reference_template_helper.TEMPLATES_WITHOUT_SITE_PARAM:
            return None

        has_alternative = any(
            template.parameters.get(param) for param in ALTERNATIVE_SITE_PARAM_VARIANTS
        )
        if has_alternative:
            logger.info(
                f"SITE_PARAMETER_SKIP | url={url} | template={template.template_name} | "
                f"reason=alternative_param_present"
            )
            return None

        current_site = _get_param_any(template.parameters, SITE_PARAM_VARIANTS)

        if current_site and current_site.strip() != "":
            if current_site.strip().startswith('[['):
                logger.info(
                    f"SITE_PARAMETER_SKIP | url={url} | template={template.template_name} | "
                    f"existing_site={current_site} | reason=already_internal_link"
                )
                return None

            # Existing plain-text value: consider upgrading to an internal link,
            # or correcting www. prefix
            potential_internal_link = self._resolve_site_value(url)
            if potential_internal_link and potential_internal_link.startswith('[['):
                logger.info(
                    f"SITE_PARAMETER_UPGRADE | url={url} | template={template.template_name} | "
                    f"existing_site={current_site} | new_site={potential_internal_link} | "
                    f"reason=upgrade_to_internal_link"
                )
                return potential_internal_link

            # Check if current_site has www. prefix that should be removed
            if current_site.strip().startswith('www.'):
                # Try to get the corrected version without www.
                from urllib.parse import urlparse
                if '://' in current_site:
                    # It's a full URL, extract domain
                    parsed = urlparse(current_site)
                    domain = parsed.netloc.replace('www.', '')
                else:
                    # It's just a domain
                    domain = current_site.strip().replace('www.', '')
                
                # Try to get the mapped site name for the corrected domain
                corrected_site = self.reference_template_helper._resolve_site_display_name(domain)
                
                # If mapping found and it's different, use it
                if corrected_site and corrected_site != current_site.strip():
                    logger.info(
                        f"SITE_PARAMETER_CORRECTION | url={url} | template={template.template_name} | "
                        f"existing_site={current_site} | new_site={corrected_site} | "
                        f"reason=remove_www_prefix_with_mapping"
                    )
                    return corrected_site
                
                # If no mapping found, still remove www. prefix (plain domain)
                if domain != current_site.strip():
                    logger.info(
                        f"SITE_PARAMETER_CORRECTION | url={url} | template={template.template_name} | "
                        f"existing_site={current_site} | new_site={domain} | "
                        f"reason=remove_www_prefix_no_mapping"
                    )
                    return domain

            # Check if current_site is a plain text that matches a mapped internal link
            # e.g., "Apple Podcasts" should become "[[Apple Podcasts]]" when URL is podcasts.apple.com
            if potential_internal_link and potential_internal_link.startswith('[['):
                # Extract the text part from the internal link (remove [[ and ]])
                mapped_text = potential_internal_link.replace('[[', '').replace(']]', '').strip()
                # Compare case-insensitively
                if current_site.strip().lower() == mapped_text.lower():
                    logger.info(
                        f"SITE_PARAMETER_UPGRADE | url={url} | template={template.template_name} | "
                        f"existing_site={current_site} | new_site={potential_internal_link} | "
                        f"reason=plain_text_to_internal_link"
                    )
                    return potential_internal_link

            logger.info(
                f"SITE_PARAMETER_SKIP | url={url} | template={template.template_name} | "
                f"existing_site={current_site} | reason=plain_text_no_upgrade_available"
            )
            return None

        # site is missing/empty on this template
        # First, get the potential site value
        potential_site = self._resolve_site_value(url)
        if not potential_site:
            return None

        # Check if manually curated parameters are present (série, collection, éditeur)
        # If so, skip adding site to avoid duplication regardless of name match
        # Policy: FEW ENRICHMENTS + ZERO UNRELATED CHANGES - conservative blocking
        série = _get_param_any(template.parameters, SERIE_PARAM_VARIANTS)
        collection = _get_param_any(template.parameters, COLLECTION_PARAM_VARIANTS)
        editeur = _get_param_any(template.parameters, EDITEUR_PARAM_VARIANTS)

        if série:
            logger.info(f"SITE_PARAMETER_SKIP_AUTO_FILL | url={url} | série={série} | reason=serie_present")
            return None
        if collection:
            logger.info(f"SITE_PARAMETER_SKIP_AUTO_FILL | url={url} | collection={collection} | reason=collection_present")
            return None
        if editeur:
            logger.info(f"SITE_PARAMETER_SKIP_AUTO_FILL | url={url} | éditeur={editeur} | reason=editeur_present")
            return None

        # Check if titre already contains the site name to avoid duplication
        # Normalize for comparison (case-insensitive, remove brackets and www)
        site_clean = potential_site.strip().lower().replace('www.', '').replace('[[', '').replace(']]', '')
        titre = template.parameters.get('titre')
        if titre:
            titre_clean = titre.strip().lower().replace('www.', '').replace('[[', '').replace(']]', '')
            if site_clean == titre_clean or site_clean in titre_clean or titre_clean in site_clean:
                logger.info(f"SITE_PARAMETER_SKIP_AUTO_FILL | url={url} | titre={titre} | reason=titre_contains_site_name")
                return None

        site_value = potential_site
        if not site_value:
            return None

        logger.info(
            f"SITE_PARAMETER_AUTO_FILLED | url={url} | site={site_value} | "
            f"type={'internal_link' if site_value.startswith('[[') else 'plain_domain'}"
        )
        return site_value

    def _should_add_consulte_le(self, template: ReferenceTemplate) -> bool:
        """
        Check if |consulté le= parameter should be added to a template.
        Whitelist approach: default-deny unless the template is explicitly
        known to support it, with a special case for {{article}} when an
        online-access parameter is present.
        """
        # Normalize template name for comparison to handle case/spacing variations
        normalized_template_name = template.template_name.lower().replace('_', ' ')
        if normalized_template_name in self.reference_template_helper.TEMPLATES_SUPPORTING_CONSULTE_LE:
            return True

        if normalized_template_name == 'article':
            if template.parameters.get('lire en ligne') or template.parameters.get('url'):
                logger.info(f"CONSULTE_LE_ALLOW | template={template.template_name} | reason=article_with_online_access")
                return True
            logger.info(f"CONSULTE_LE_SKIP | template={template.template_name} | reason=article_without_online_access")
            return False

        logger.info(f"CONSULTE_LE_SKIP | template={template.template_name} | reason=template_not_in_whitelist")
        return False

    def _get_consulte_le_value(self) -> str:
        """Current date in YYYY-MM-DD format (UTC) for |consulté le=."""
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')

    def _validate_template_replacement(self, old_content: str, new_content: str,
                                       old_template_start: int, old_template_end: int,
                                       new_template: str) -> bool:
        """Validate that template replacement is safe and minimal."""
        try:
            is_valid, error_msg = self.template_validator.validate(
                old_content, new_content, old_template_start, old_template_end, new_template
            )
        except Exception as e:
            logger.warning(
                f"TEMPLATE_VALIDATION_EXCEPTION | error={type(e).__name__}: {e}"
            )
            return False
        if not is_valid:
            logger.warning(f"TEMPLATE_VALIDATION_FAILED | error={error_msg}")
        return is_valid

    def analyze(self, content: str) -> List[Issue]:
        self.clear_issues()

        if not content:
            logger.warning("ReferenceEnricherAnalyzer: empty content provided")
            return self.issues

        # Clear caches to ensure fresh analysis per article
        self._check_cache.clear()
        self._template_cache.clear()
        self._checks_count = 0

        logger.info(
            f"ReferenceEnricherAnalyzer started - content_length: {len(content)}, "
            f"max_checks: {self.max_checks_per_article} (unique URLs), site_fill: {self.enable_site_fill}, "
            f"consulte_le_fill: {self.enable_consulte_le_fill}"
        )

        protected_mask = self.build_protected_mask(content)
        all_matches = list(UrlExtractor.URL_PATTERN.finditer(content))
        protected_matches = [m for m in all_matches if not self.is_protected(protected_mask, m.start())]

        # Filter URLs in reference scope
        scoped_matches = [
            m for m in protected_matches
            if self._is_url_in_reference_scope(content, m.group(0), m.start())
        ]
        out_of_scope_count = len(protected_matches) - len(scoped_matches)
        if out_of_scope_count:
            logger.info(
                f"URLS_OUT_OF_SCOPE_SKIPPED | count={out_of_scope_count} | "
                f"reason=not_in_reference_or_citation_template"
            )
        filtered_matches = scoped_matches
        total_occurrences = len(filtered_matches)

        # Position order does not matter here (content is never mutated in
        # place — Issues carry positions/suggested_text for the Corrector to
        # apply). We keep a stable ascending sort for deterministic logs.
        filtered_matches.sort(key=lambda m: m.start())

        # ---- PASSE 1 : vérification parallèle des liens ----
        # Extract unique URLs for HTTP checking (deduplicate requests, not occurrences)
        unique_urls = {}
        for match in filtered_matches:
            url = match.group(0)
            if url not in unique_urls:
                unique_urls[url] = []
            unique_urls[url].append(match)

        unique_url_list = list(unique_urls.keys())
        logger.info(f"Found {total_occurrences} URL occurrences, {len(unique_url_list)} unique URLs")

        # Apply max_checks_per_article to unique URLs (HTTP requests), not occurrences
        urls_to_check = unique_url_list[:self.max_checks_per_article]
        if len(unique_url_list) > self.max_checks_per_article:
            logger.info(f"Reached max checks limit ({self.max_checks_per_article}), stopping")

        valid_urls = []
        for url in urls_to_check:
            if not self._is_url_syntactically_valid(url):
                logger.warning(f"URL_REJECTED | url={url} | reason=SYNTAX_INVALID")
                continue
            valid_urls.append(url)

        if valid_urls:
            logger.info(f"Starting parallel link check for {len(valid_urls)} unique URLs with max_workers=5")
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_url = {
                    executor.submit(self.link_checker.check_link, url): url
                    for url in valid_urls
                }
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        result = future.result()
                        self._check_cache[url] = result
                        self._checks_count += 1

                        logger.info(
                            f"URL_CHECK | url={url} | http_status={result.http_status_code} | "
                            f"classification={result.status.value} | error={result.error_type} | "
                            f"attempts={result.retry_count}"
                        )
                    except Exception as e:
                        logger.error(f"URL_CHECK_FAILED | url={url} | error={type(e).__name__}: {e}")
                        self._check_cache[url] = LinkCheckResult(
                            url=url,
                            status=LinkStatus.UNKNOWN,
                            error_type="CHECK_EXCEPTION",
                            retry_count=0,
                            check_duration=0.0,
                            confidence=0.0
                        )
                        self._checks_count += 1

        logger.info(f"Parallel link check completed - checked {self._checks_count}/{len(valid_urls)} unique URLs")

        # ---- PASSE 2 : enrichissement séquentiel (en utilisant le cache) ----
        # Process ALL occurrences (not just unique URLs) using the cache
        enrichment_applied_count = 0
        not_needed_both_present_count = 0
        not_needed_no_params_count = 0
        not_needed_unchanged_count = 0
        skipped_count = 0

        for match in filtered_matches:
            url = match.group(0)
            url_position = match.start()

            if url not in self._check_cache:
                logger.warning(f"URL_NOT_IN_CACHE | url={url} | skipping")
                continue

            result = self._check_cache[url]

            # ONLY enrich HEALTHY links - all other statuses are DeadLinkAnalyzer's job
            if result.status != LinkStatus.HEALTHY:
                logger.info(f"NO_ENRICHMENT | url={url} | status={result.status.value} | reason=unhealthy_link")
                skipped_count += 1
                continue

            template = self._get_cached_reference_template(content, url, url_position)
            if not template:
                logger.info(f"NO_ENRICHMENT | url={url} | reason=no_template_found")
                skipped_count += 1
                continue

            if not template.is_supported:
                logger.info(
                    f"NO_ENRICHMENT | url={url} | template={template.template_name} | "
                    f"reason=unsupported_template"
                )
                skipped_count += 1
                continue

            # Sanity check: the template's recorded span must actually match
            # its own full_match in the current content. If it doesn't, the
            # cached lookup is stale or wrong — refuse to build a slice-based
            # replacement on unreliable coordinates.
            if content[template.start_position:template.end_position] != template.full_match:
                logger.warning(
                    f"NO_ENRICHMENT | url={url} | template={template.template_name} | "
                    f"reason=template_span_mismatch_stale_lookup"
                )
                skipped_count += 1
                continue

            current_site = _get_param_any(template.parameters, SITE_PARAM_VARIANTS)
            current_consulte_le = _get_param_any(template.parameters, CONSULTE_LE_PARAM_VARIANTS)

            site_is_empty = not current_site or current_site.strip() == ""
            consulte_le_is_empty = not current_consulte_le or current_consulte_le.strip() == ""

            site_is_plain_upgradeable = (not site_is_empty) and (not current_site.strip().startswith('[['))

            # Nothing at all to evaluate: both present/non-empty and site
            # isn't a plain-text value eligible for upgrade.
            if not site_is_empty and not site_is_plain_upgradeable and not consulte_le_is_empty:
                logger.info(
                    f"ENRICHMENT_NOT_NEEDED | url={url} | template={template.template_name} | "
                    f"reason=both_params_present"
                )
                not_needed_both_present_count += 1
                continue

            site_value = None
            site_is_upgrade = False
            if self.enable_site_fill and (site_is_empty or site_is_plain_upgradeable):
                site_value = self._get_site_parameter_if_missing(template, url)
                site_is_upgrade = bool(site_value) and not site_is_empty
            elif not site_is_empty:
                logger.info(
                    f"SITE_ALREADY_PRESENT | url={url} | template={template.template_name} | "
                    f"existing_site={current_site} | reason=no_redundancy"
                )

            consulte_le_value = None
            # Only add consulté le if site is being added (not if already present)
            # This avoids polluting Wikipedia with trivial consulté le-only additions
            if self.enable_consulte_le_fill and consulte_le_is_empty:
                supports_consulte_le = self._should_add_consulte_le(template)
                if site_value is not None and supports_consulte_le:
                    consulte_le_value = self._get_consulte_le_value()
                    logger.info(
                        f"CONSULTE_LE_WILL_BE_ADDED | url={url} | template={template.template_name} | "
                        f"site_value={site_value} | consulte_le_value={consulte_le_value}"
                    )
                else:
                    logger.info(
                        f"CONSULTE_LE_SKIPPED | url={url} | template={template.template_name} | "
                        f"site_value={site_value} | supports_consulte_le={supports_consulte_le} | "
                        f"reason={'template_type_not_supported' if not supports_consulte_le else 'site_not_being_added'}"
                    )
            elif not consulte_le_is_empty:
                logger.info(
                    f"CONSULTE_LE_ALREADY_PRESENT | url={url} | template={template.template_name} | "
                    f"existing_consulte_le={current_consulte_le} | reason=no_redundancy"
                )

            if not site_value and not consulte_le_value:
                logger.info(
                    f"ENRICHMENT_NOT_NEEDED | url={url} | template={template.template_name} | "
                    f"reason=no_params_to_add"
                )
                not_needed_no_params_count += 1
                continue

            try:
                new_template = self.reference_template_helper.generate_enriched_template(
                    template, site_value, consulte_le_value
                )
            except Exception as e:
                logger.warning(
                    f"NO_ENRICHMENT | url={url} | template={template.template_name} | "
                    f"reason=technical_error | error={type(e).__name__}: {e}"
                )
                skipped_count += 1
                continue

            if not new_template or new_template == template.full_match:
                logger.info(
                    f"ENRICHMENT_NOT_APPLIED | url={url} | template={template.template_name} | "
                    f"reason=template_unchanged"
                )
                not_needed_unchanged_count += 1
                continue

            new_content = content[:template.start_position] + new_template + content[template.end_position:]

            if not self._validate_template_replacement(
                content, new_content, template.start_position, template.end_position, new_template
            ):
                logger.warning(
                    f"ENRICHMENT_VALIDATION_FAILED | url={url} | template={template.template_name}"
                )
                skipped_count += 1
                continue

            fields_added = []
            if site_value:
                fields_added.append('site' + (' (upgrade)' if site_is_upgrade else ''))
            if consulte_le_value:
                fields_added.append('consulté le')

            self.issues.append(Issue(
                issue_type="reference_enrichment",
                description=f"Référence enrichie (site/consulté le) : {url}",
                position=template.start_position,
                original_text=template.full_match,
                suggested_text=new_template,
                severity="low",
                confidence=1.0,
                extra={
                    'url': url,
                    'http_status_code': result.http_status_code,
                    'fields_added': fields_added,
                    'site_value': site_value,
                    'site_is_upgrade': site_is_upgrade,
                    'consulte_le_value': consulte_le_value,
                    'template_name': template.template_name,
                    'repair_status': 'ENRICHMENT_APPLIED'
                }
            ))

            enrichment_applied_count += 1
            logger.info(
                f"ENRICHMENT_APPLIED | url={url} | template={template.template_name} | "
                f"fields_added={fields_added}"
            )

        self.issues.sort(key=lambda i: i.position if i.position is not None else 0)

        no_enrichment_needed_count = (
            not_needed_both_present_count + not_needed_no_params_count + not_needed_unchanged_count
        )

        logger.info(
            f"ReferenceEnricherAnalyzer completed - "
            f"ENRICHMENT_APPLIED={enrichment_applied_count} | "
            f"NO_ENRICHMENT_NEEDED={no_enrichment_needed_count} "
            f"(both_present={not_needed_both_present_count}, "
            f"no_params_to_add={not_needed_no_params_count}, "
            f"unchanged={not_needed_unchanged_count}) | "
            f"NO_ENRICHMENT={skipped_count} | "
            f"total_issues={len(self.issues)} | "
            f"checked={self._checks_count}/{len(unique_url_list)} unique URLs "
            f"({total_occurrences} occurrences)"
        )

        return self.issues