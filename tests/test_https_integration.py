"""
Integration tests for HTTPS verification with HttpLinksAnalyzer.

Tests the complete flow:
1. HTTP link detection
2. Domain extraction
3. HTTPS verification (with cache)
4. Decision based on verification result
5. Correction only if HTTPS_AVAILABLE
"""

import sys
import logging
from pathlib import Path
from unittest.mock import Mock, patch

# Suppress warnings during tests
logging.getLogger('wikipedia_maintenance.utils.https_verification_service').setLevel(logging.CRITICAL)

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.analyzers.http_links import HttpLinksAnalyzer
from wikipedia_maintenance.utils.https_verification_service import (
    HttpsVerificationService,
    VerificationResult
)
from wikipedia_maintenance.utils.https_verification_cache import (
    HttpsVerificationCache,
    VerificationStatus
)


class MockDatabaseManager:
    """Mock database manager for testing."""
    
    def __init__(self):
        self._cache = {}
    
    def get_https_verification(self, domain):
        """Get cached verification."""
        normalized = domain.lower().rstrip('/')
        entry = self._cache.get(normalized)
        if entry:
            from datetime import datetime
            expires_at = datetime.fromisoformat(entry['expires_at'])
            if expires_at > datetime.now():
                return entry
        return None
    
    def set_https_verification(self, domain, status, ttl_days, **kwargs):
        """Set cached verification."""
        normalized = domain.lower().rstrip('/')
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(days=ttl_days)
        self._cache[normalized] = {
            'domain': normalized,
            'status': status,
            'expires_at': expires_at.isoformat(),
            **kwargs
        }
    
    def invalidate_https_verification(self, domain):
        """Invalidate cache entry."""
        normalized = domain.lower().rstrip('/')
        if normalized in self._cache:
            del self._cache[normalized]
    
    def cleanup_expired_https_verifications(self):
        """Cleanup expired entries."""
        return 0


def test_full_flow_https_available():
    """Test complete flow when HTTPS is available."""
    print("Test 1 - Full flow with HTTPS available")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=True,
        https_verification_service=service
    )
    
    # Mock successful HTTPS response
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        content = "Voir http://example.com/article pour plus d'informations."
        issues = analyzer.analyze(content)
        
        # Should detect HTTP link and suggest HTTPS correction
        assert len(issues) == 1
        assert issues[0].issue_type == "http_link"
        assert issues[0].original_text == "http://example.com/article"
        assert issues[0].suggested_text == "https://example.com/article"
        assert issues[0].severity == "medium"
        print("  OK - HTTPS available, correction suggested")


def test_full_flow_https_unavailable():
    """Test complete flow when HTTPS is unavailable."""
    print("Test 2 - Full flow with HTTPS unavailable")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=True,
        https_verification_service=service
    )
    
    # Pre-populate cache with HTTPS_UNAVAILABLE
    cache.set(
        domain="example.com",
        status=VerificationStatus.HTTPS_UNAVAILABLE,
        https_url="https://example.com",
        http_status_code=404
    )
    
    content = "Voir http://example.com/article pour plus d'informations."
    issues = analyzer.analyze(content)
    
    # Should detect HTTP link but NOT suggest correction
    assert len(issues) == 1
    assert issues[0].issue_type == "http_link"
    assert issues[0].original_text == "http://example.com/article"
    assert issues[0].suggested_text is None  # No correction suggested
    assert issues[0].severity == "low"  # Low severity since no correction
    print("  OK - HTTPS unavailable, no correction suggested")


def test_full_flow_check_failed():
    """Test complete flow when check fails."""
    print("Test 3 - Full flow with check failed")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=True,
        https_verification_service=service
    )
    
    # Mock timeout
    with patch('urllib.request.urlopen') as mock_urlopen:
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError(TimeoutError("Timeout"))
        
        content = "Voir http://example.com/article pour plus d'informations."
        issues = analyzer.analyze(content)
        
        # Should detect HTTP link but NOT suggest correction
        assert len(issues) == 1
        assert issues[0].issue_type == "http_link"
        assert issues[0].original_text == "http://example.com/article"
        assert issues[0].suggested_text is None  # No correction suggested
        assert issues[0].severity == "low"
        print("  OK - Check failed, no correction suggested")


def test_verification_disabled():
    """Test with HTTPS verification disabled."""
    print("Test 4 - Verification disabled")
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=False,
        https_verification_service=None
    )
    
    content = "Voir http://example.com/article pour plus d'informations."
    issues = analyzer.analyze(content)
    
    # Should detect HTTP link and suggest correction without verification
    assert len(issues) == 1
    assert issues[0].issue_type == "http_link"
    assert issues[0].original_text == "http://example.com/article"
    assert issues[0].suggested_text == "https://example.com/article"
    assert issues[0].severity == "medium"
    print("  OK - Verification disabled, correction suggested")


def test_multiple_links_same_domain():
    """Test multiple HTTP links to same domain."""
    print("Test 5 - Multiple links same domain")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=True,
        https_verification_service=service
    )
    
    # Mock successful HTTPS response
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        content = """
        Voir http://example.com/page1 pour info 1.
        Et http://example.com/page2 pour info 2.
        Aussi http://example.com/page3 pour info 3.
        """
        issues = analyzer.analyze(content)
        
        # Should detect all 3 links
        assert len(issues) == 3
        # All should suggest HTTPS correction
        for issue in issues:
            assert issue.suggested_text is not None
            assert issue.suggested_text.startswith("https://")
        # Should only call urlopen once (single domain verification)
        assert mock_urlopen.call_count == 1
        print("  OK - Multiple links, single verification")


def test_url_parameters_preserved():
    """Test that URL parameters and fragments are preserved."""
    print("Test 6 - URL parameters preserved")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=True,
        https_verification_service=service
    )
    
    # Mock successful HTTPS response
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        content = "Voir http://example.com/article?id=123&lang=en#section pour plus d'infos."
        issues = analyzer.analyze(content)
        
        assert len(issues) == 1
        assert issues[0].original_text == "http://example.com/article?id=123&lang=en#section"
        assert issues[0].suggested_text == "https://example.com/article?id=123&lang=en#section"
        print("  OK - URL parameters and fragments preserved")


def test_domain_extraction():
    """Test domain extraction from various URL formats."""
    print("Test 7 - Domain extraction")
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=False
    )
    
    # Test domain extraction
    assert analyzer.extract_domain_from_url("http://example.com") == "example.com"
    assert analyzer.extract_domain_from_url("http://www.example.com") == "www.example.com"
    assert analyzer.extract_domain_from_url("http://example.com/page") == "example.com"
    assert analyzer.extract_domain_from_url("http://example.com:8080/page") == "example.com:8080"
    assert analyzer.extract_domain_from_url("invalid-url") is None
    print("  OK - Domain extraction working correctly")


def test_protected_zones_ignored():
    """Test that protected zones are still ignored."""
    print("Test 8 - Protected zones ignored")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=True,
        https_verification_service=service
    )
    
    content = """
    <nowiki>http://example.com/protected</nowiki>
    <!-- http://example.com/comment -->
    Regular http://example.com/normal
    """
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        issues = analyzer.analyze(content)
        
        # Should only detect the normal link, not protected ones
        assert len(issues) == 1
        assert "normal" in issues[0].original_text
        print("  OK - Protected zones ignored")


def test_max_issues_limit():
    """Test max_issues limit is respected."""
    print("Test 9 - Max issues limit")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    analyzer = HttpLinksAnalyzer(
        max_issues=2,
        enable_https_verification=True,
        https_verification_service=service
    )
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        content = """
        http://example.com/1
        http://example.com/2
        http://example.com/3
        http://example.com/4
        """
        issues = analyzer.analyze(content)
        
        # Should only report max_issues
        assert len(issues) == 2
        print("  OK - Max issues limit respected")


def test_cache_reuse_across_analyses():
    """Test cache reuse across multiple analyses."""
    print("Test 10 - Cache reuse across analyses")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=True,
        https_verification_service=service
    )
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        # First analysis
        content1 = "Voir http://example.com/page1"
        issues1 = analyzer.analyze(content1)
        assert len(issues1) == 1
        call_count_1 = mock_urlopen.call_count
        
        # Second analysis with same domain
        content2 = "Voir http://example.com/page2"
        issues2 = analyzer.analyze(content2)
        assert len(issues2) == 1
        call_count_2 = mock_urlopen.call_count
        
        # Should not make additional network calls (cache hit)
        assert call_count_2 == call_count_1
        print("  OK - Cache reused across analyses")


def test_mixed_domains():
    """Test multiple domains with different HTTPS availability."""
    print("Test 11 - Mixed domains")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=True,
        https_verification_service=service
    )
    
    # Pre-populate cache with different statuses
    cache.set("https-available.com", VerificationStatus.HTTPS_AVAILABLE, 
              https_url="https://https-available.com", http_status_code=200)
    cache.set("https-unavailable.com", VerificationStatus.HTTPS_UNAVAILABLE,
              https_url="https://https-unavailable.com", http_status_code=404)
    
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        content = """
        http://https-available.com/page
        http://https-unavailable.com/page
        http://new-domain.com/page
        """
        issues = analyzer.analyze(content)
        
        assert len(issues) == 3
        
        # First should have correction (HTTPS_AVAILABLE)
        assert issues[0].suggested_text is not None
        
        # Second should NOT have correction (HTTPS_UNAVAILABLE)
        assert issues[1].suggested_text is None
        
        # Third should have correction (new domain, mock succeeds)
        assert issues[2].suggested_text is not None
        
        # Should only call urlopen once (for new-domain.com)
        assert mock_urlopen.call_count == 1
        print("  OK - Mixed domains handled correctly")


def test_https_links_ignored():
    """Test that HTTPS links are not detected."""
    print("Test 12 - HTTPS links ignored")
    
    analyzer = HttpLinksAnalyzer(
        max_issues=None,
        enable_https_verification=False
    )
    
    content = """
    http://example.com/http
    https://example.com/https
    http://example.com/another
    """
    
    issues = analyzer.analyze(content)
    
    # Should only detect HTTP links
    assert len(issues) == 2
    for issue in issues:
        assert issue.original_text.startswith("http://")
        assert not issue.original_text.startswith("https://")
    print("  OK - HTTPS links ignored")


if __name__ == "__main__":
    print("=" * 60)
    print("HTTPS INTEGRATION TESTS")
    print("=" * 60)
    print()
    
    test_full_flow_https_available()
    test_full_flow_https_unavailable()
    test_full_flow_check_failed()
    test_verification_disabled()
    test_multiple_links_same_domain()
    test_url_parameters_preserved()
    test_domain_extraction()
    test_protected_zones_ignored()
    test_max_issues_limit()
    test_cache_reuse_across_analyses()
    test_mixed_domains()
    test_https_links_ignored()
    
    print()
    print("=" * 60)
    print("ALL HTTPS INTEGRATION TESTS PASSED")
    print("=" * 60)
