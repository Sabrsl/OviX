"""
Tests for URL extraction and validation utilities.

Tests the pure functions in url_extraction.py which have no network dependencies.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from wikipedia_maintenance.utils.url_extraction import UrlExtractor


class TestUrlExtraction:
    """Test URL extraction and validation functionality."""
    
    def test_is_syntactically_valid_valid_urls(self):
        """Test that valid URLs pass syntactic validation."""
        valid_urls = [
            "https://example.com",
            "http://example.com/page",
            "https://example.com/page?param=value",
            "https://example.com/page#section",
            "https://example.com/page%20with%20spaces",
        ]
        
        for url in valid_urls:
            assert UrlExtractor.is_syntactically_valid(url), f"URL should be valid: {url}"
    
    def test_is_syntactically_valid_invalid_urls(self):
        """Test that invalid URLs fail syntactic validation."""
        invalid_urls = [
            "https://example.com|param=value",  # Contains template delimiter
            "https://example.com{param}",       # Contains template delimiter
            "https://example.com[param]",       # Contains template delimiter
            "https://example.com|",             # Ends with delimiter
            "https://example.com=",             # Ends with delimiter
            "https://example.com%",             # Ends with percent (incomplete encoding)
            "https://example.com%XX",           # Invalid percent encoding
            "ftp://example.com",               # Invalid scheme
            "example.com",                      # Missing scheme
        ]
        
        for url in invalid_urls:
            assert not UrlExtractor.is_syntactically_valid(url), f"URL should be invalid: {url}"
    
    def test_is_syntactically_valid_with_excluded_domains(self):
        """Test domain exclusion functionality."""
        url = "https://gallica.bnf.fr/document"
        excluded_domains = {"gallica.bnf.fr"}
        
        assert not UrlExtractor.is_syntactically_valid(url, excluded_domains), \
            "URL with excluded domain should be invalid"
        
        # Without exclusion, should be valid
        assert UrlExtractor.is_syntactically_valid(url), \
            "URL should be valid without domain exclusion"
    
    def test_is_archive_url(self):
        """Test archive URL detection."""
        archive_urls = [
            "https://web.archive.org/web/20200101/https://example.com",
            "https://archive.org/details/example",
            "https://webcache.googleusercontent.com/search?q=cache:example.com",
            "https://arquivo.pt/wayback/20200101/https://example.com",
        ]
        
        for url in archive_urls:
            assert UrlExtractor.is_archive_url(url), f"Should be archive URL: {url}"
        
        non_archive_urls = [
            "https://example.com",
            "https://example.org/page",
            "http://example.net",
        ]
        
        for url in non_archive_urls:
            assert not UrlExtractor.is_archive_url(url), f"Should not be archive URL: {url}"
    
    def test_extract_original_from_archive(self):
        """Test original URL extraction from archive URLs."""
        test_cases = [
            (
                "https://web.archive.org/web/20200101120000/https://example.com/page",
                "https://example.com/page"
            ),
            (
                "https://web.archive.org/web/20200101/https://example.com/page?param=value",
                "https://example.com/page?param=value"
            ),
            (
                "https://web.archive.org/web/20200101/https://example.com/page#section",
                "https://example.com/page#section"
            ),
        ]
        
        for archive_url, expected_original in test_cases:
            result = UrlExtractor.extract_original_from_archive(archive_url)
            assert result == expected_original, f"Expected {expected_original}, got {result}"
    
    def test_extract_original_from_archive_non_archive(self):
        """Test that non-archive URLs return None."""
        non_archive_urls = [
            "https://example.com",
            "https://example.org/page",
        ]
        
        for url in non_archive_urls:
            result = UrlExtractor.extract_original_from_archive(url)
            assert result is None, f"Non-archive URL should return None: {url}"
    
    def test_find_urls_in_content(self):
        """Test URL finding in wikitext content."""
        content = "See https://example.com and http://example.org for more info"
        urls = UrlExtractor.find_urls_in_content(content)
        
        assert len(urls) == 2, f"Should find 2 URLs, found {len(urls)}"
        assert urls[0][0] == "https://example.com"
        assert urls[1][0] == "http://example.org"
    
    def test_find_urls_in_content_no_urls(self):
        """Test content with no URLs."""
        content = "This is just text with no URLs"
        urls = UrlExtractor.find_urls_in_content(content)
        
        assert len(urls) == 0, "Should find no URLs"
    
    def test_extract_domain(self):
        """Test domain extraction from URLs."""
        test_cases = [
            ("https://www.example.com", "example.com"),
            ("https://example.com", "example.com"),
            ("https://m.example.com", "example.com"),
            ("https://sub.example.com", "sub.example.com"),
            ("http://user:pass@example.com:8080", "example.com"),
        ]
        
        for url, expected_domain in test_cases:
            result = UrlExtractor.extract_domain(url)
            assert result == expected_domain, f"Expected {expected_domain}, got {result}"
    
    def test_extract_domain_invalid_url(self):
        """Test domain extraction from invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "",
            "https://",  # No domain
        ]
        
        for url in invalid_urls:
            result = UrlExtractor.extract_domain(url)
            assert result is None, f"Invalid URL should return None: {url}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])