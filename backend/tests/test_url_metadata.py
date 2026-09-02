"""
Tests for URL metadata extraction utilities.

Tests the pure functions in url_metadata.py which have no network dependencies.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from wikipedia_maintenance.utils.url_metadata import UrlMetadataExtractor


class TestUrlMetadataExtraction:
    """Test URL metadata extraction functionality."""
    
    def test_extract_site_name_basic(self):
        """Test basic site name extraction."""
        test_cases = [
            ("https://www.example.com", "example.com"),
            ("https://example.com", "example.com"),
            ("https://m.example.com", "example.com"),
            ("https://sub.example.com", "sub.example.com"),
            ("https://www.lemonde.fr/article", "lemonde.fr"),
        ]
        
        for url, expected in test_cases:
            result = UrlMetadataExtractor.extract_site_name(url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_extract_site_name_with_credentials(self):
        """Test site name extraction with URL credentials."""
        url = "https://user:pass@example.com"
        result = UrlMetadataExtractor.extract_site_name(url)
        assert result == "example.com", f"Should strip credentials, got {result}"
    
    def test_extract_site_name_with_port(self):
        """Test site name extraction with port number."""
        url = "https://example.com:8080"
        result = UrlMetadataExtractor.extract_site_name(url)
        assert result == "example.com", f"Should strip port, got {result}"
    
    def test_extract_site_name_invalid_url(self):
        """Test site name extraction from invalid URLs."""
        invalid_urls = [
            "not-a-url",
            "",
            "https://",  # No domain
        ]
        
        for url in invalid_urls:
            result = UrlMetadataExtractor.extract_site_name(url)
            assert result is None, f"Invalid URL should return None: {url}"
    
    def test_extract_title_basic(self):
        """Test basic title extraction from URL paths."""
        test_cases = [
            ("https://example.com/MyDocument", "MyDocument"),
            ("https://example.com/my-document", "My document"),
            ("https://example.com/my_document", "My document"),
            ("https://example.com/document.html", "Document"),
            ("https://example.com/document.pdf", "Document"),  # .pdf is now removed
        ]
        
        for url, expected in test_cases:
            result = UrlMetadataExtractor.extract_title(url)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_extract_title_with_query_params(self):
        """Test title extraction removes query parameters."""
        url = "https://example.com/document?param=value"
        result = UrlMetadataExtractor.extract_title(url)
        assert result == "Document", f"Should remove query params, got {result}"
    
    def test_extract_title_with_fragment(self):
        """Test title extraction removes fragments."""
        url = "https://example.com/document#section"
        result = UrlMetadataExtractor.extract_title(url)
        assert result == "Document", f"Should remove fragment, got {result}"
    
    def test_extract_title_url_encoded(self):
        """Test title extraction handles URL encoding."""
        url = "https://example.com/My%20Document"
        result = UrlMetadataExtractor.extract_title(url)
        assert result == "My Document", f"Should decode URL encoding, got {result}"
    
    def test_extract_title_invalid_cases(self):
        """Test title extraction from invalid cases."""
        invalid_cases = [
            "https://example.com/",  # No path
            "https://example.com",   # No path
            "https://example.com/ab",  # Too short
            "https://example.com/123",  # Numeric only
        ]
        
        for url in invalid_cases:
            result = UrlMetadataExtractor.extract_title(url)
            assert result is None, f"Invalid case should return None: {url}"
    
    def test_clean_filename(self):
        """Test filename cleaning functionality."""
        test_cases = [
            ("document.html", "Document"),
            ("report.pdf", "Report"),
            ("my_document", "My document"),
            ("my-document", "My document"),
            ("Document", "Document"),
        ]
        
        for filename, expected in test_cases:
            result = UrlMetadataExtractor.clean_filename(filename)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_clean_filename_invalid(self):
        """Test filename cleaning with invalid input."""
        invalid_cases = [
            "",
            "ab",  # Too short
            "12",  # Numeric only
        ]
        
        for filename in invalid_cases:
            result = UrlMetadataExtractor.clean_filename(filename)
            assert result is None, f"Invalid filename should return None: {filename}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
