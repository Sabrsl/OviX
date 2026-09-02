"""
Tests for {{Lien web}} template archive repair behavior.

These tests verify that when a dead link is repaired with an archive,
the {{Lien web}} template uses the archive URL as the main link,
following Wikipedia template behavior.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from wikipedia_maintenance.utils.lien_web_helper import LienWebHelper, LienWebTemplate


class TestLienWebArchiveRepair:
    """Test {{Lien web}} template archive repair behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.helper = LienWebHelper()

    def test_find_lien_web_template(self):
        """Test finding {{Lien web}} template containing a URL."""
        content = "{{Lien web |titre=Test |url=https://example.com |site=example.com }}"
        url = "https://example.com"
        position = content.find(url)

        template = self.helper.find_lien_web_template(content, url, position)

        assert template is not None
        assert template.template_name == "Lien web"
        assert "titre" in template.parameters
        assert template.parameters["titre"] == "Test"
        assert template.parameters["url"] == "https://example.com"

    def test_find_lien_web_template_not_found(self):
        """Test when URL is not in a {{Lien web}} template."""
        content = "See https://example.com for more info"
        url = "https://example.com"
        position = content.find(url)

        template = self.helper.find_lien_web_template(content, url, position)

        assert template is None

    def test_generate_archive_repair_template(self):
        """Test generating {{Lien web}} template with archive as main link (patched behavior)."""
        content = "{{Lien web |titre=Test Article |url=https://dead-link.com |site=dead-link.com }}"
        url = "https://dead-link.com"
        position = content.find(url)

        original_template = self.helper.find_lien_web_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead-link.com"
        archive_date = "20240101000000"
        original_url = "https://dead-link.com"

        new_template = self.helper.generate_archive_repair_template(
            original_template,
            archive_url,
            archive_date,
            original_url,
            assume_patch_deployed=True  # Patched behavior
        )

        # Verify archive URL is the main link (url parameter)
        assert "|url=" + archive_url in new_template
        # Verify archive-url is also present
        assert "|archive-url=" + archive_url in new_template
        # Verify archive-date is present and formatted
        assert "|archive-date=2024-01-01" in new_template
        # Verify brisé le is present
        assert "|brisé le=" in new_template
        # Verify original site is preserved
        assert "|site=dead-link.com" in new_template
        # Verify original title is preserved
        assert "|titre=Test Article" in new_template

    def test_generate_archive_repair_template_unpatched(self):
        """Test generating {{Lien web}} template with original URL as main link (unpatched behavior)."""
        content = "{{Lien web |titre=Test Article |url=https://dead-link.com |site=dead-link.com }}"
        url = "https://dead-link.com"
        position = content.find(url)

        original_template = self.helper.find_lien_web_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead-link.com"
        archive_date = "20240101000000"
        original_url = "https://dead-link.com"

        new_template = self.helper.generate_archive_repair_template(
            original_template,
            archive_url,
            archive_date,
            original_url,
            assume_patch_deployed=False  # Unpatched behavior
        )

        # Verify original URL is the main link (url parameter)
        assert "|url=" + original_url in new_template
        # Verify archive-url is present
        assert "|archive-url=" + archive_url in new_template
        # Verify archive-date is present and formatted
        assert "|archive-date=2024-01-01" in new_template
        # Verify brisé le is present
        assert "|brisé le=" in new_template
        # Verify original site is preserved
        assert "|site=dead-link.com" in new_template
        # Verify original title is preserved
        assert "|titre=Test Article" in new_template

    def test_generate_archive_repair_without_site(self):
        """Test generating template when site parameter is not present."""
        content = "{{Lien web |titre=Test Article |url=https://dead-link.com }}"
        url = "https://dead-link.com"
        position = content.find(url)

        original_template = self.helper.find_lien_web_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead-link.com"
        archive_date = "20240101000000"
        original_url = "https://dead-link.com"

        new_template = self.helper.generate_archive_repair_template(
            original_template,
            archive_url,
            archive_date,
            original_url,
            assume_patch_deployed=True
        )

        # Verify site is extracted from original URL
        assert "|site=dead-link.com" in new_template
        # Verify archive URL is main link
        assert "|url=" + archive_url in new_template

    def test_should_use_archive_template_with_lien_web(self):
        """Test that archive template format is used for {{Lien web}} templates."""
        content = "{{Lien web |titre=Test |url=https://example.com |site=example.com }}"
        url = "https://example.com"
        position = content.find(url)

        should_use = self.helper.should_use_archive_template(content, url, position)

        assert should_use is True

    def test_should_use_archive_template_without_lien_web(self):
        """Test that archive template format is not used for plain URLs."""
        content = "See https://example.com for more info"
        url = "https://example.com"
        position = content.find(url)

        should_use = self.helper.should_use_archive_template(content, url, position)

        assert should_use is False

    def test_format_archive_date_yyyymmdd(self):
        """Test formatting archive date from YYYYMMDD to YYYY-MM-DD."""
        formatted = self.helper._format_archive_date("20240101000000")
        assert formatted == "2024-01-01"

    def test_format_archive_date_already_formatted(self):
        """Test that already formatted date is returned as-is."""
        formatted = self.helper._format_archive_date("2024-01-01")
        assert formatted == "2024-01-01"

    def test_format_archive_date_empty(self):
        """Test formatting empty archive date."""
        formatted = self.helper._format_archive_date("")
        assert formatted == ""

    def test_generate_template_preserves_all_parameters(self):
        """Test that all original parameters are preserved."""
        content = "{{Lien web |titre=Test |url=https://dead-link.com |site=dead-link.com |auteur=John Doe |date=2023-01-01 }}"
        url = "https://dead-link.com"
        position = content.find(url)

        original_template = self.helper.find_lien_web_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead-link.com"
        archive_date = "20240101000000"
        original_url = "https://dead-link.com"

        new_template = self.helper.generate_archive_repair_template(
            original_template,
            archive_url,
            archive_date,
            original_url,
            assume_patch_deployed=True
        )

        # Verify all original parameters are preserved
        assert "|titre=Test" in new_template
        assert "|auteur=John Doe" in new_template
        assert "|date=2023-01-01" in new_template
        # Verify new archive parameters are added
        assert "|url=" + archive_url in new_template
        assert "|archive-url=" + archive_url in new_template
        assert "|archive-date=2024-01-01" in new_template
        assert "|brisé le=" in new_template

    def test_preserve_existing_brisé_le_date(self):
        """Test that existing 'brisé le' date is preserved."""
        content = "{{Lien web |titre=Test |url=https://dead-link.com |brisé le=2023-06-15 }}"
        url = "https://dead-link.com"
        position = content.find(url)

        original_template = self.helper.find_lien_web_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead-link.com"
        archive_date = "20240101000000"
        original_url = "https://dead-link.com"

        new_template = self.helper.generate_archive_repair_template(
            original_template,
            archive_url,
            archive_date,
            original_url,
            assume_patch_deployed=True
        )

        # Verify existing 'brisé le' is preserved (not overwritten with current date)
        assert "|brisé le=2023-06-15" in new_template
        # Verify archive parameters are added
        assert "|archive-url=" + archive_url in new_template
        assert "|archive-date=2024-01-01" in new_template

    def test_add_brisé_le_when_missing(self):
        """Test that 'brisé le' is added when not present."""
        content = "{{Lien web |titre=Test |url=https://dead-link.com }}"
        url = "https://dead-link.com"
        position = content.find(url)

        original_template = self.helper.find_lien_web_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead-link.com"
        archive_date = "20240101000000"
        original_url = "https://dead-link.com"

        new_template = self.helper.generate_archive_repair_template(
            original_template,
            archive_url,
            archive_date,
            original_url,
            assume_patch_deployed=True
        )

        # Verify 'brisé le' is added with current date
        assert "|brisé le=" in new_template
        # Verify archive parameters are added
        assert "|archive-url=" + archive_url in new_template
        assert "|archive-date=2024-01-01" in new_template

    def test_complex_template_with_special_characters(self):
        """Test parsing template with special characters in values."""
        content = "{{Lien web|langue=ko|auteur=Lee|prénom=Moon Jae|titre='분강나루'서 건져낸 백정 恨|url=http://www.sisapress.com/journal/articlePrint/108966|série=sisapress.com|date=8 août 1991}}"
        url = "http://www.sisapress.com/journal/articlePrint/108966"
        position = content.find(url)

        template = self.helper.find_lien_web_template(content, url, position)

        assert template is not None
        assert template.parameters['langue'] == 'ko'
        assert template.parameters['auteur'] == 'Lee'
        assert template.parameters['prénom'] == 'Moon Jae'
        assert template.parameters['titre'] == "'분강나루'서 건져낸 백정 恨"
        assert template.parameters['url'] == 'http://www.sisapress.com/journal/articlePrint/108966'
        assert template.parameters['série'] == 'sisapress.com'
        assert template.parameters['date'] == '8 août 1991'

    def test_no_duplicate_parameters(self):
        """Test that parameters are not duplicated in generated template."""
        content = "{{Lien web |titre=Test |url=https://dead-link.com |site=example.com }}"
        url = "https://dead-link.com"
        position = content.find(url)

        original_template = self.helper.find_lien_web_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead-link.com"
        archive_date = "20240101000000"
        original_url = "https://dead-link.com"

        new_template = self.helper.generate_archive_repair_template(
            original_template,
            archive_url,
            archive_date,
            original_url,
            assume_patch_deployed=True
        )

        # Count occurrences of each parameter
        url_count = new_template.count('|url=')
        site_count = new_template.count('|site=')
        titre_count = new_template.count('|titre=')

        # Each parameter should appear exactly once
        assert url_count == 1, f"url parameter appears {url_count} times"
        assert site_count == 1, f"site parameter appears {site_count} times"
        assert titre_count == 1, f"titre parameter appears {titre_count} times"

    def test_build_minimal_template_distinct_dates(self):
        """Test that minimal template uses distinct dates for archive-date and brisé le."""
        from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
        from wikipedia_maintenance.utils.link_checker import LinkChecker
        from wikipedia_maintenance.utils.archive_provider import ArchiveProvider
        import re
        
        # Create minimal dependencies
        link_checker = LinkChecker()
        archive_provider = ArchiveProvider()
        analyzer = DeadLinkAnalyzer(link_checker, archive_provider)
        
        original_url = "https://dead-link.com"
        archive_url = "https://web.archive.org/web/20240101000000/https://dead-link.com"
        archive_date = "20240101000000"  # Archive date from 2024-01-01
        
        minimal_template = analyzer._build_minimal_lien_web_template(
            original_url, archive_url, archive_date, "WaybackMachine"
        )
        
        assert minimal_template is not None
        # Verify archive-date uses the archive date
        assert "archive-date=2024-01-01" in minimal_template
        # Verify brisé le uses current date (not archive date)
        assert "brisé le=" in minimal_template
        # Extract the brisé le date
        brise_match = re.search(r'brisé le=(\d{4}-\d{2}-\d{2})', minimal_template)
        assert brise_match is not None
        brise_date = brise_match.group(1)
        # The brisé le date should not be the archive date (2024-01-01)
        # since we're testing in 2026, the current date will be different
        assert brise_date != "2024-01-01", f"brisé le should be current date, not archive date. Got: {brise_date}"

    def test_healthy_links_not_processed(self):
        """Test that healthy (non-dead) links are not processed or modified."""
        from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
        from unittest.mock import patch
        
        # Create analyzer - it creates its own dependencies
        analyzer = DeadLinkAnalyzer()
        
        # Disable auto-repair to ensure we only test detection, not repair
        analyzer.enable_auto_repair = False
        
        # Content with a healthy link
        content = "Voici un lien sain : https://example.com"
        
        # Mock the link checker to return a healthy status for example.com
        from wikipedia_maintenance.utils.link_checker import LinkCheckResult, LinkStatus
        healthy_result = LinkCheckResult(
            url="https://example.com",
            status=LinkStatus.HEALTHY,
            http_status_code=200,
            retry_count=0,
            check_duration=0.1,
            confidence=1.0
        )
        
        with patch.object(analyzer.link_checker, 'check_link', return_value=healthy_result):
            # Analyze the content
            issues = analyzer.analyze(content)
        
        # Verify that no issues were reported for the healthy link
        # (if the link is healthy, it should not appear in issues)
        dead_link_issues = [issue for issue in issues if issue.issue_type == "dead_link"]
        
        # Filter out any issues that might be for other URLs
        example_com_issues = [issue for issue in dead_link_issues if "example.com" in issue.extra.get('url', '')]
        
        # There should be no dead link issues for example.com since it's a healthy link
        assert len(example_com_issues) == 0, f"Healthy link should not be processed. Found {len(example_com_issues)} issues"

    def test_dead_links_not_normalized(self):
        """Test that dead links are not subject to case normalization."""
        from wikipedia_maintenance.utils.case_normalizer import CaseNormalizer
        
        # Create a template with a dead link that has case variations
        content = "{{Lien web |titre=TEST TITLE |site=EXAMPLE.COM |url=https://dead-link.com }}"
        
        # Create normalizer
        normalizer = CaseNormalizer(enabled=True)
        
        # Normalize the content
        result = normalizer.normalize_text(content)
        
        # The normalizer should preserve URLs even if they are in the template
        # According to the PROTECTED_PARAMETERS, 'url' should never be modified
        assert "url=https://dead-link.com" in result.normalized_text, "URL parameter should be protected from normalization"
        
        # The normalizer might normalize titre and site parameters, but not url
        # This is expected behavior - only URL parameters are protected
