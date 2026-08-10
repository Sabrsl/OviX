"""
Test to verify the LinkChecker fixes for false DEAD classifications.

This test ensures that:
1. 403 is no longer classified as DEAD (moved to REVIEW_REQUIRED)
2. GET fallback is used when HEAD fails (405/403)
3. Valid URLs are not incorrectly classified as DEAD
"""

import pytest
import urllib.error
from unittest.mock import Mock, patch, MagicMock
from wikipedia_maintenance.utils.link_checker import LinkChecker, LinkStatus, LinkCheckResult


class TestLinkCheckerFixes:
    """Test cases for LinkChecker false positive fixes."""
    
    def test_403_not_classified_as_dead(self):
        """Test that 403 is classified as REVIEW_REQUIRED, not DEAD."""
        checker = LinkChecker(timeout=10, max_retries=1)
        
        # Mock response returning 403
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 403
            mock_response.url = "https://example.com/test"
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://example.com/test",
                code=403,
                msg="Forbidden",
                hdrs={},
                fp=None
            )
            
            result = checker.check_link("https://example.com/test")
            
            # Should be REVIEW_REQUIRED, not DEAD
            assert result.status == LinkStatus.REVIEW_REQUIRED
            assert result.http_status_code == 403
            assert result.status != LinkStatus.DEAD
    
    def test_get_fallback_on_405(self):
        """Test that GET is used as fallback when HEAD returns 405."""
        checker = LinkChecker(timeout=10, max_retries=1)
        
        call_count = [0]
        
        def mock_urlopen_side_effect(request, *args, **kwargs):
            call_count[0] += 1
            mock_response = MagicMock()
            
            if request.method == 'HEAD':
                # First call (HEAD) returns 405
                raise urllib.error.HTTPError(
                    url="https://example.com/test",
                    code=405,
                    msg="Method Not Allowed",
                    hdrs={},
                    fp=None
                )
            else:
                # Second call (GET) succeeds
                mock_response.getcode.return_value = 200
                mock_response.url = "https://example.com/test"
                return mock_response
        
        with patch('urllib.request.urlopen', side_effect=mock_urlopen_side_effect):
            result = checker.check_link("https://example.com/test")
            
            # Should use GET fallback and succeed
            assert result.status == LinkStatus.HEALTHY
            assert result.http_status_code == 200
            assert call_count[0] == 2  # HEAD failed, GET succeeded
    
    def test_get_fallback_on_403(self):
        """Test that GET is used as fallback when HEAD returns 403."""
        checker = LinkChecker(timeout=10, max_retries=1)
        
        call_count = [0]
        
        def mock_urlopen_side_effect(request, *args, **kwargs):
            call_count[0] += 1
            
            if request.method == 'HEAD':
                # First call (HEAD) returns 403
                raise urllib.error.HTTPError(
                    url="https://example.com/test",
                    code=403,
                    msg="Forbidden",
                    hdrs={},
                    fp=None
                )
            else:
                # Second call (GET) succeeds
                mock_response = MagicMock()
                mock_response.getcode.return_value = 200
                mock_response.url = "https://example.com/test"
                return mock_response
        
        with patch('urllib.request.urlopen', side_effect=mock_urlopen_side_effect):
            result = checker.check_link("https://example.com/test")
            
            # Should use GET fallback and succeed
            assert result.status == LinkStatus.HEALTHY
            assert result.http_status_code == 200
            assert call_count[0] == 2  # HEAD failed, GET succeeded
    
    def test_404_still_classified_as_dead(self):
        """Test that 404 is still correctly classified as DEAD."""
        checker = LinkChecker(timeout=10, max_retries=1)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://example.com/notfound",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=None
            )
            
            result = checker.check_link("https://example.com/notfound")
            
            # Should still be DEAD
            assert result.status == LinkStatus.DEAD
            assert result.http_status_code == 404
    
    def test_410_still_classified_as_dead(self):
        """Test that 410 is still correctly classified as DEAD."""
        checker = LinkChecker(timeout=10, max_retries=1)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://example.com/gone",
                code=410,
                msg="Gone",
                hdrs={},
                fp=None
            )
            
            result = checker.check_link("https://example.com/gone")
            
            # Should still be DEAD
            assert result.status == LinkStatus.DEAD
            assert result.http_status_code == 410


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
