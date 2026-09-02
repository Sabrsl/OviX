"""
Tests for ReferenceEnricherAnalyzer.

Tests the enrichment functionality for healthy reference templates.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from wikipedia_maintenance.analyzers.reference_enricher_analyzer import ReferenceEnricherAnalyzer
from wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplate


class TestReferenceEnricherAnalyzer:
    """Test reference enrichment functionality."""

    def test_analyzer_initialization(self):
        """Test that analyzer initializes with correct defaults."""
        analyzer = ReferenceEnricherAnalyzer()
        
        assert analyzer.get_analyzer_name() == "ReferenceEnricherAnalyzer"
        assert analyzer.enable_site_fill is True
        assert analyzer.enable_consulte_le_fill is True

    def test_analyzer_initialization_with_config(self):
        """Test that analyzer can be initialized with custom config."""
        analyzer = ReferenceEnricherAnalyzer(
            timeout=15,
            max_retries=5,
            max_checks_per_article=100,
            enable_site_fill=False,
            enable_consulte_le_fill=False
        )
        
        assert analyzer.timeout == 15
        assert analyzer.max_retries == 5
        assert analyzer.max_checks_per_article == 100
        assert analyzer.enable_site_fill is False
        assert analyzer.enable_consulte_le_fill is False

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_healthy_link_without_site_or_consulte_le(self, mock_link_checker_class):
        """Test that both site and consulté le are added to healthy link."""
        # Mock the LinkChecker to return HEALTHY status
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test}}</ref>"
        issues = analyzer.analyze(content)
        
        # Should create one enrichment issue
        assert len(issues) == 1
        assert issues[0].issue_type == "reference_enrichment"
        assert issues[0].extra['repair_status'] == "ENRICHMENT_APPLIED"
        assert "site" in issues[0].extra['fields_added']
        # consulté le is added because site is being added (policy: consulté le depends on site)
        assert "consulté le" in issues[0].extra['fields_added']
        assert issues[0].extra['site_value'] is not None
        assert issues[0].extra['consulte_le_value'] is not None

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_healthy_link_with_site_already_present(self, mock_link_checker_class):
        """Test that no enrichment is applied when site is already present (consulté le depends on site being added)."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test|site=Example}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - consulté le depends on site being added, not already present
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_healthy_link_with_both_params_present(self, mock_link_checker_class):
        """Test that no enrichment is applied when both params are already present."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        content = f"<ref>{{Lien web|url=https://example.com/article|titre=Test|site=Example|consulté le={today}}}</ref>"
        issues = analyzer.analyze(content)
        
        # Should create no enrichment issue
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_ouvrage_template_no_site_or_consulte_le_added(self, mock_link_checker_class):
        """Test that neither site nor consulté le are added to ouvrage template (physical/digital publication)."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/book",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{ouvrage|url=https://example.com/book|titre=Book Title}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - ouvrage templates don't get site or consulté le
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_same_url_in_two_references(self, mock_link_checker_class):
        """Test that same URL in two different references is enriched in both occurrences."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = """
        <ref>{{Lien web|url=https://example.com/article|titre=Test}}</ref>
        <ref>{{Lien web|url=https://example.com/article|titre=Test}}</ref>
        """
        issues = analyzer.analyze(content)

        # Should create enrichment issues for both occurrences
        assert len(issues) == 2
        # Both should have the same URL
        assert issues[0].extra['url'] == "https://example.com/article"
        assert issues[1].extra['url'] == "https://example.com/article"

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_site_already_present_capitalized(self, mock_link_checker_class):
        """Test that when |Site= is already present (capitalized), no enrichment is applied."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test|Site=Example}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - Site already present
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_consulte_le_already_present_capitalized(self, mock_link_checker_class):
        """Test that when |Consulté le= is already present (capitalized), no enrichment is applied."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test|site=Example|Consulté le=2026-01-01}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - both parameters already present
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_chapitre_template_no_site_or_consulte_le_added(self, mock_link_checker_class):
        """Test that neither site nor consulté le are added to chapitre template (physical/digital publication)."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/chapter",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>{{chapitre|url=https://example.com/chapter|titre=Chapter Title}}</ref>"
        issues = analyzer.analyze(content)
        
        # Should create no enrichment issue - chapitre templates don't get site or consulté le
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_lien_web_template_gets_both_params(self, mock_link_checker_class):
        """Test that Lien web template (in whitelist) gets both site and consulté le (when site is added)."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test}}</ref>"
        issues = analyzer.analyze(content)

        # Should create enrichment issue with both site and consulté le
        assert len(issues) == 1
        assert issues[0].issue_type == "reference_enrichment"
        assert "site" in issues[0].extra['fields_added']
        # consulté le is added because site is being added (policy: consulté le depends on site)
        assert "consulté le" in issues[0].extra['fields_added']

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_article_template_with_url_gets_consulte_le(self, mock_link_checker_class):
        """Test that article template with url parameter gets consulté le."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>{{article|url=https://example.com/article|titre=Test}}</ref>"
        issues = analyzer.analyze(content)
        
        # Should create enrichment issue with consulté le (article with url is online)
        assert len(issues) == 1
        assert issues[0].issue_type == "reference_enrichment"
        assert "consulté le" in issues[0].extra['fields_added']

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_article_template_with_lire_enligne_gets_consulte_le(self, mock_link_checker_class):
        """Test that article template with lire en ligne parameter gets consulté le."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>{{article|lire en ligne=https://example.com/article|titre=Test}}</ref>"
        issues = analyzer.analyze(content)
        
        # Should create enrichment issue with consulté le (article with lire en ligne is online)
        assert len(issues) == 1
        assert issues[0].issue_type == "reference_enrichment"
        assert "consulté le" in issues[0].extra['fields_added']

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_article_template_without_url_no_consulte_le(self, mock_link_checker_class):
        """Test that article template without url/lire en ligne does NOT get consulté le."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        # Article with url in content but not in template parameters (edge case)
        # This tests that consulté le is only added when url/lire en ligne is a template parameter
        content = "<ref>{{article|titre=Test|périodique=Journal}} https://example.com/article</ref>"
        issues = analyzer.analyze(content)
        
        # Should not add consulté le because url is not a template parameter
        # The URL is just text in the ref, not a template parameter
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_serie_present_no_site_added(self, mock_link_checker_class):
        """Test that neither site nor consulté le is added when série parameter is present (conservative blocking)."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test|série=Test Series}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - série prevents site addition (conservative policy)
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_serie_capitalized_no_site_added(self, mock_link_checker_class):
        """Test that neither site nor consulté le is added when Série (capitalized) parameter is present."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test|Série=Test Series}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - capitalized Série prevents site addition
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_editeur_present_no_site_added(self, mock_link_checker_class):
        """Test that neither site nor consulté le is added when éditeur parameter is present."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test|éditeur=Test Publisher}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - éditeur prevents site addition
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_editeur_capitalized_no_site_added(self, mock_link_checker_class):
        """Test that neither site nor consulté le is added when Éditeur (capitalized) parameter is present."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test|Éditeur=Test Publisher}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - capitalized Éditeur prevents site addition
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_titre_contains_site_name_no_site_added(self, mock_link_checker_class):
        """Test that site is not added when titre already contains the site name."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://historicmarkers.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://historicmarkers.com/article|titre=historicmarkers.com}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - titre contains site name
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_site_with_www_prefix_corrected(self, mock_link_checker_class):
        """Test that www. prefix is removed from existing site parameter only (not from titre)."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://www.franceinter.fr/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://www.franceinter.fr/article|titre=Test|site=www.franceinter.fr}}</ref>"
        issues = analyzer.analyze(content)

        # Should create enrichment issue with corrected site (www. removed)
        assert len(issues) == 1
        assert issues[0].issue_type == "reference_enrichment"
        assert issues[0].extra['site_value'] is not None
        assert 'www.' not in issues[0].extra['site_value']  # www. should be removed from site
        # Verify that titre is NOT modified (www. correction only applies to site parameter)
        assert 'Test' in issues[0].suggested_text  # titre remains unchanged

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_dead_link_no_enrichment(self, mock_link_checker_class):
        """Test that dead links are never enriched (that's DeadLinkAnalyzer's job)."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/dead",
            status=LinkStatus.DEAD,
            http_status_code=404,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>{{Lien web|url=https://example.com/dead|titre=Dead}}</ref>"
        issues = analyzer.analyze(content)
        
        # Should create no enrichment issue
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_review_required_no_enrichment(self, mock_link_checker_class):
        """Test that REVIEW_REQUIRED links are not enriched."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/review",
            status=LinkStatus.REVIEW_REQUIRED,
            http_status_code=403,
            confidence=0.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>{{Lien web|url=https://example.com/review|titre=Review}}</ref>"
        issues = analyzer.analyze(content)
        
        # Should create no enrichment issue
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_temporary_error_no_enrichment(self, mock_link_checker_class):
        """Test that TEMPORARY_ERROR links are not enriched."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/temp",
            status=LinkStatus.TEMPORARY_ERROR,
            http_status_code=503,
            confidence=0.8
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>{{Lien web|url=https://example.com/temp|titre=Temp}}</ref>"
        issues = analyzer.analyze(content)
        
        # Should create no enrichment issue
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_bare_url_no_enrichment(self, mock_link_checker_class):
        """Test that bare URLs (no template) are not enriched."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/bare",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>https://example.com/bare</ref>"
        issues = analyzer.analyze(content)
        
        # Should create no enrichment issue (no template found)
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_site_extraction_fails(self, mock_link_checker_class):
        """Test that when site extraction fails, it may still add a fallback site value."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://invalid-url-that-cannot-be-parsed",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()

        content = "<ref>{{Lien web|url=https://invalid-url-that-cannot-be-parsed|titre=Test}}</ref>"
        issues = analyzer.analyze(content)

        # May create enrichment issue with fallback site value (depends on extraction logic)
        # consulté le depends on site being added
        if len(issues) == 1:
            assert "site" in issues[0].extra['fields_added']
            # consulté le should be added if site is added
            assert "consulté le" in issues[0].extra['fields_added']

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.TemplateReplacementValidator')
    def test_template_validation_failure(self, mock_validator_class, mock_link_checker_class):
        """Test that when template validation fails, no enrichment is applied."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        mock_validator = Mock()
        mock_validator_class.return_value = mock_validator
        mock_validator.validate.return_value = (False, "Simulated validation failure")

        analyzer = ReferenceEnricherAnalyzer()
        
        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test}}</ref>"
        issues = analyzer.analyze(content)
        
        # Should create no enrichment issue due to validation failure
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_site_fill_disabled(self, mock_link_checker_class):
        """Test that when enable_site_fill is False, neither site nor consulté le is added."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer(enable_site_fill=False)

        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test}}</ref>"
        issues = analyzer.analyze(content)

        # Should create no enrichment issue - consulté le depends on site being added
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_consulte_le_fill_disabled(self, mock_link_checker_class):
        """Test that when enable_consulte_le_fill is False, consulté le is not added."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/article",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer(enable_consulte_le_fill=False)

        content = "<ref>{{Lien web|url=https://example.com/article|titre=Test}}</ref>"
        issues = analyzer.analyze(content)

        # Should create enrichment issue with site but without consulté le
        assert len(issues) == 1
        assert "site" in issues[0].extra['fields_added']
        assert "consulté le" not in issues[0].extra['fields_added']
        assert "consulté le" not in issues[0].extra['fields_added']
        assert issues[0].extra['consulte_le_value'] is None

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_empty_content(self, mock_link_checker_class):
        """Test that empty content is handled gracefully."""
        analyzer = ReferenceEnricherAnalyzer()
        
        issues = analyzer.analyze("")
        
        assert len(issues) == 0

    @patch('wikipedia_maintenance.analyzers.reference_enricher_analyzer.LinkChecker')
    def test_url_out_of_scope(self, mock_link_checker_class):
        """Test that URLs outside reference scope are not enriched."""
        mock_checker = Mock()
        mock_link_checker_class.return_value = mock_checker
        mock_checker.check_link.return_value = LinkCheckResult(
            url="https://example.com/external",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            confidence=1.0
        )

        analyzer = ReferenceEnricherAnalyzer()
        
        # URL in "Liens externes" section, not in a reference
        content = "== Liens externes ==\n* https://example.com/external"
        issues = analyzer.analyze(content)
        
        # Should create no enrichment issue (out of scope)
        assert len(issues) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
