"""
Tests for Archive Content Checker.

Tests the soft-404 detection functionality with mocked network calls.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from wikipedia_maintenance.utils.archive_content_checker import ArchiveSoftDeadChecker


class TestArchiveSoftDeadChecker:
    """Test archive content soft-404 detection."""
    
    def test_initialization(self):
        """Test checker initialization."""
        checker = ArchiveSoftDeadChecker(timeout=15)
        assert checker.timeout == 15
        assert len(checker.get_markers()) > 0
    
    def test_default_timeout(self):
        """Test default timeout value."""
        checker = ArchiveSoftDeadChecker()
        assert checker.timeout == 10
    
    def test_get_markers(self):
        """Test that markers are returned correctly."""
        checker = ArchiveSoftDeadChecker()
        markers = checker.get_markers()
        
        assert isinstance(markers, list)
        assert len(markers) > 0
        assert 'page not found' in markers
        assert 'page non trouvée' in markers
    
    @patch('urllib.request.urlopen')
    def test_looks_dead_with_soft_404(self, mock_urlopen):
        """Test detection of soft-404 content."""
        # Mock response with soft-404 content
        mock_response = MagicMock()
        mock_response.read.return_value = b"This is a page not found page with 404 not found"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        checker = ArchiveSoftDeadChecker()
        result = checker.looks_dead("https://web.archive.org/example")
        
        assert result is True, "Should detect soft-404 content"
        mock_urlopen.assert_called_once()
    
    @patch('urllib.request.urlopen')
    def test_looks_dead_with_valid_content(self, mock_urlopen):
        """Test that valid content is not flagged as dead."""
        # Mock response with valid content
        mock_response = MagicMock()
        mock_response.read.return_value = b"This is a valid page with actual content"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        checker = ArchiveSoftDeadChecker()
        result = checker.looks_dead("https://web.archive.org/example")
        
        assert result is False, "Should not flag valid content as dead"
    
    @patch('urllib.request.urlopen')
    def test_looks_dead_with_network_error(self, mock_urlopen):
        """Test that network errors return False (conservative)."""
        # Mock network error
        mock_urlopen.side_effect = Exception("Network error")
        
        checker = ArchiveSoftDeadChecker()
        result = checker.looks_dead("https://web.archive.org/example")
        
        assert result is False, "Should return False on network error (conservative)"
    
    @patch('urllib.request.urlopen')
    def test_looks_dead_unicode_handling(self, mock_urlopen):
        """Test that unicode content is handled correctly."""
        # Mock response with unicode content
        mock_response = MagicMock()
        mock_response.read.return_value = "Page non trouvée — contenu introuvable".encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        checker = ArchiveSoftDeadChecker()
        result = checker.looks_dead("https://web.archive.org/example")
        
        assert result is True, "Should detect French not-found markers"
    
    @patch('urllib.request.urlopen')
    def test_looks_dead_case_insensitive(self, mock_urlopen):
        """Test that marker matching is case-insensitive."""
        # Mock response with uppercase markers
        mock_response = MagicMock()
        mock_response.read.return_value = b"PAGE NOT FOUND - THIS PAGE DOES NOT EXIST"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        checker = ArchiveSoftDeadChecker()
        result = checker.looks_dead("https://web.archive.org/example")
        
        assert result is True, "Should detect markers case-insensitively"
    
    @patch('urllib.request.urlopen')
    def test_looks_dead_timeout(self, mock_urlopen):
        """Test that timeout errors are handled gracefully."""
        # Mock timeout error
        mock_urlopen.side_effect = TimeoutError("Request timeout")
        
        checker = ArchiveSoftDeadChecker(timeout=5)
        result = checker.looks_dead("https://web.archive.org/example")
        
        assert result is False, "Should return False on timeout (conservative)"
    
    @patch('urllib.request.urlopen')
    def test_looks_dead_content_size_limit(self, mock_urlopen):
        """Test that only first 20KB of content is checked."""
        # Mock response with large content
        large_content = b"Valid content " * 30000  # > 20KB
        mock_response = MagicMock()
        mock_response.read.return_value = large_content[:20000]  # Simulate 20KB limit
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        checker = ArchiveSoftDeadChecker()
        result = checker.looks_dead("https://web.archive.org/example")
        
        # Should only check first 20KB
        mock_response.read.assert_called_with(20000)
        assert result is False, "Should not flag valid content as dead"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
