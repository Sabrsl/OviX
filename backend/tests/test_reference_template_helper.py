"""
Tests for generic Reference Template Helper.

These tests verify that the helper can detect and repair multiple
reference template types (Lien web, article, ouvrage, Lien brisé).
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from wikipedia_maintenance.utils.reference_template_helper import ReferenceTemplateHelper, ReferenceTemplate


class TestReferenceTemplateHelper:
    """Test generic reference template helper."""

    def setup_method(self):
        """Set up test fixtures."""
        self.helper = ReferenceTemplateHelper()

    def test_find_lien_web_template(self):
        """Test finding {{Lien web}} template."""
        content = "{{Lien web |titre=Test |url=https://example.com |site=example.com }}"
        url = "https://example.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is not None
        assert template.template_name == "Lien web"
        assert template.parameters['titre'] == 'Test'
        assert template.parameters['url'] == 'https://example.com'

    def test_find_article_template(self):
        """Test finding {{article}} template."""
        content = "{{article|auteur=Park|titre=Test Article|périodique=OSEN|date=2022}}"
        url = "http://www.osen.co.kr/article/G1111748424"
        position = content.find(url) if url in content else 0

        # Test with URL in template
        content_with_url = "{{article|auteur=Park|titre=Test Article|url=http://www.osen.co.kr/article/G1111748424|périodique=OSEN|date=2022}}"
        position = content_with_url.find(url)

        template = self.helper.find_reference_template(content_with_url, url, position)

        assert template is not None
        assert template.template_name == "article"
        assert template.parameters['auteur'] == 'Park'
        assert template.parameters['url'] == url

    def test_find_ouvrage_template(self):
        """Test finding {{ouvrage}} template."""
        content = "{{ouvrage|auteur=John Doe|titre=Test Book|éditeur=Publisher|lieu=Paris|date=2020|url=http://example.com}}"
        url = "http://example.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is not None
        assert template.template_name == "ouvrage"
        assert template.parameters['auteur'] == 'John Doe'
        assert template.parameters['titre'] == 'Test Book'

    def test_find_lien_brisé_template(self):
        """Test finding {{Lien brisé}} template."""
        content = "{{Lien brisé |titre=Test |url=https://example.com |date=2023}}"
        url = "https://example.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is not None
        assert template.template_name == "Lien brisé"
        assert template.parameters['titre'] == 'Test'
        assert template.parameters['url'] == 'https://example.com'

    def test_no_template_found(self):
        """Test when no template is found."""
        content = "See https://example.com for more info"
        url = "https://example.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is None

    def test_generate_archive_repair_lien_web(self):
        """Test generating archive repair for {{Lien web}}."""
        content = "{{Lien web |titre=Test |url=https://dead.com |site=dead.com }}"
        url = "https://dead.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead.com"
        archive_date = "20240101000000"

        new_template = self.helper.generate_archive_repair_template(
            template,
            archive_url,
            archive_date,
            url,
            assume_patch_deployed=False
        )

        assert "|archive-url=" + archive_url in new_template
        assert "|archive-date=2024-01-01" in new_template
        assert "|brisé le=" in new_template

    def test_generate_archive_repair_article(self):
        """Test generating archive repair for {{article}}."""
        content = "{{article|auteur=Park|titre=Test|url=http://dead.com|périodique=OSEN}}"
        url = "http://dead.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/http://dead.com"
        archive_date = "20240101000000"

        new_template = self.helper.generate_archive_repair_template(
            template,
            archive_url,
            archive_date,
            url,
            assume_patch_deployed=False
        )

        assert "|archive-url=" + archive_url in new_template
        assert "|archive-date=2024-01-01" in new_template
        assert "|brisé le=" in new_template
        # Original URL should be preserved for article template
        assert "|url=http://dead.com" in new_template

    def test_generate_archive_repair_ouvrage(self):
        """Test generating archive repair for {{ouvrage}}."""
        content = "{{ouvrage|auteur=John|titre=Test|url=http://dead.com}}"
        url = "http://dead.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/http://dead.com"
        archive_date = "20240101000000"

        new_template = self.helper.generate_archive_repair_template(
            template,
            archive_url,
            archive_date,
            url,
            assume_patch_deployed=False
        )

        assert "|archive-url=" + archive_url in new_template
        assert "|archive-date=2024-01-01" in new_template

    def test_preserve_existing_brisé_le(self):
        """Test that existing 'brisé le' is preserved."""
        content = "{{Lien web |titre=Test |url=https://dead.com |brisé le=2023-06-15 }}"
        url = "https://dead.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead.com"
        archive_date = "20240101000000"

        new_template = self.helper.generate_archive_repair_template(
            template,
            archive_url,
            archive_date,
            url,
            assume_patch_deployed=False
        )

        assert "|brisé le=2023-06-15" in new_template

    def test_complex_korean_template(self):
        """Test parsing complex Korean template."""
        content = "{{article|langue=ko|auteur=Park|prénom=Moon Jae|titre='분강나루'서 건져낸 백정 恨|url=http://www.sisapress.com/journal/articlePrint/108966|série=sisapress.com|date=8 août 1991}}"
        url = "http://www.sisapress.com/journal/articlePrint/108966"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is not None
        assert template.template_name == "article"
        assert template.parameters['langue'] == 'ko'
        assert template.parameters['auteur'] == 'Park'
        assert template.parameters['titre'] == "'분강나루'서 건져낸 백정 恨"

    def test_no_duplicate_parameters(self):
        """Test that parameters are not duplicated."""
        content = "{{Lien web |titre=Test |url=https://dead.com |site=example.com }}"
        url = "https://dead.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead.com"
        archive_date = "20240101000000"

        new_template = self.helper.generate_archive_repair_template(
            template,
            archive_url,
            archive_date,
            url,
            assume_patch_deployed=False
        )

        url_count = new_template.count('|url=')
        assert url_count == 1, f"url parameter appears {url_count} times"

    def test_find_cite_web_template(self):
        """Test finding {{cite web}} template (English)."""
        content = "{{cite web |title=Test |url=https://example.com |website=example.com }}"
        url = "https://example.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is not None
        assert template.template_name == "Lien web"  # Mapped to French equivalent
        assert template.parameters['title'] == 'Test'
        assert template.parameters['url'] == 'https://example.com'

    def test_find_cite_news_template(self):
        """Test finding {{cite news}} template (English)."""
        content = "{{cite news |title=News Article |url=https://news.example.com |newspaper=Example News }}"
        url = "https://news.example.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is not None
        assert template.template_name == "Lien web"  # Mapped to French equivalent
        assert template.parameters['title'] == 'News Article'
        assert template.parameters['url'] == 'https://news.example.com'

    def test_find_cite_report_template(self):
        """Test finding {{cite report}} template (English)."""
        content = "{{cite report |title=Annual Report |url=https://report.example.gov |publisher=Government }}"
        url = "https://report.example.gov"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is not None
        assert template.template_name == "Lien web"  # Mapped to French equivalent
        assert template.parameters['title'] == 'Annual Report'
        assert template.parameters['url'] == 'https://report.example.gov'

    def test_find_cite_journal_template(self):
        """Test finding {{cite journal}} template (English)."""
        content = "{{cite journal |title=Research Paper |url=https://journal.example.com/article/123 |journal=Example Journal }}"
        url = "https://journal.example.com/article/123"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is not None
        assert template.template_name == "article"  # Mapped to French equivalent
        assert template.parameters['title'] == 'Research Paper'
        assert template.parameters['url'] == 'https://journal.example.com/article/123'

    def test_find_cite_book_template(self):
        """Test finding {{cite book}} template (English)."""
        content = "{{cite book |title=Book Title |url=https://book.example.com |publisher=Example Publisher }}"
        url = "https://book.example.com"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)

        assert template is not None
        assert template.template_name == "ouvrage"  # Mapped to French equivalent
        assert template.parameters['title'] == 'Book Title'
        assert template.parameters['url'] == 'https://book.example.com'

    def test_generate_archive_repair_cite_report(self):
        """Test generating archive repair for {{cite report}} (mapped to Lien web)."""
        content = "{{cite report |title=Annual Report |url=https://dead.gov/report |publisher=Government }}"
        url = "https://dead.gov/report"
        position = content.find(url)

        template = self.helper.find_reference_template(content, url, position)
        archive_url = "https://web.archive.org/web/20240101000000/https://dead.gov/report"
        archive_date = "20240101000000"

        new_template = self.helper.generate_archive_repair_template(
            template,
            archive_url,
            archive_date,
            url,
            assume_patch_deployed=False
        )

        assert "|archive-url=" + archive_url in new_template
        assert "|archive-date=2024-01-01" in new_template
        assert "|brisé le=" in new_template
        # Should be mapped to Lien web format
        assert "{{Lien web" in new_template or "{{Lien web" in new_template.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
