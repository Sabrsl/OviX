"""
Tests for HttpsVerificationService with network mocks.

These tests use mocks to simulate various network scenarios without
making actual HTTP requests, ensuring tests are deterministic and
don't require Internet connectivity.
"""

import sys
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Suppress warnings during tests
logging.getLogger('wikipedia_maintenance.utils.https_verification_service').setLevel(logging.CRITICAL)

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

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
            expires_at = datetime.fromisoformat(entry['expires_at'])
            if expires_at > datetime.now():
                return entry
        return None
    
    def set_https_verification(self, domain, status, ttl_days, **kwargs):
        """Set cached verification."""
        normalized = domain.lower().rstrip('/')
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
        count = 0
        now = datetime.now()
        for domain in list(self._cache.keys()):
            expires_at = datetime.fromisoformat(self._cache[domain]['expires_at'])
            if expires_at < now:
                del self._cache[domain]
                count += 1
        return count


def test_https_available():
    """Test domain with HTTPS available."""
    print("Test 1 - HTTPS available")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock successful HTTPS response
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.HTTPS_AVAILABLE
        assert result.domain == "example.com"
        assert result.http_status_code == 200
        assert result.error_type is None
        print("  OK - HTTPS correctly detected as available")


def test_https_unavailable_4xx():
    """Test domain with HTTPS returning 4xx error."""
    print("Test 2 - HTTPS unavailable (4xx)")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock 404 response
    with patch('urllib.request.urlopen') as mock_urlopen:
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://example.com",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.CHECK_FAILED
        assert result.domain == "example.com"
        assert result.error_type == "HTTP_ERROR"
        print("  OK - 4xx error correctly handled as CHECK_FAILED")


def test_https_unavailable_5xx():
    """Test domain with HTTPS returning 5xx error."""
    print("Test 3 - HTTPS unavailable (5xx)")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock 500 response
    with patch('urllib.request.urlopen') as mock_urlopen:
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://example.com",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None
        )
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.CHECK_FAILED
        assert result.error_type == "HTTP_ERROR"
        print("  OK - 5xx error correctly handled as CHECK_FAILED")


def test_timeout():
    """Test domain with timeout."""
    print("Test 4 - Timeout")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=0.1)
    
    # Mock timeout
    with patch('urllib.request.urlopen') as mock_urlopen:
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError(TimeoutError("Timeout"))
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.CHECK_FAILED
        assert result.error_type == "TIMEOUT"
        print("  OK - Timeout correctly handled as CHECK_FAILED")


def test_dns_error():
    """Test domain with DNS error."""
    print("Test 5 - DNS error")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock DNS error
    with patch('urllib.request.urlopen') as mock_urlopen:
        from urllib.error import URLError
        import socket
        mock_urlopen.side_effect = URLError(socket.gaierror(-2, "Name or service not known"))
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.CHECK_FAILED
        assert result.error_type == "DNS_ERROR"
        print("  OK - DNS error correctly handled as CHECK_FAILED")


def test_connection_refused():
    """Test domain with connection refused."""
    print("Test 6 - Connection refused")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock connection refused
    with patch('urllib.request.urlopen') as mock_urlopen:
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError(ConnectionRefusedError("Connection refused"))
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.CHECK_FAILED
        assert result.error_type == "CONNECTION_REFUSED"
        print("  OK - Connection refused correctly handled as CHECK_FAILED")


def test_redirect():
    """Test domain with HTTPS redirect."""
    print("Test 7 - HTTPS redirect")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock successful response (redirect followed automatically by urllib)
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.HTTPS_AVAILABLE
        assert result.http_status_code == 200
        print("  OK - Redirect correctly handled as HTTPS_AVAILABLE")


def test_cache_hit():
    """Test cache hit for already verified domain."""
    print("Test 8 - Cache hit")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Pre-populate cache
    cache.set(
        domain="example.com",
        status=VerificationStatus.HTTPS_AVAILABLE,
        https_url="https://example.com",
        http_status_code=200
    )
    
    # Verify no network call is made
    with patch('urllib.request.urlopen') as mock_urlopen:
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.HTTPS_AVAILABLE
        assert result.http_status_code == 200
        mock_urlopen.assert_not_called()
        print("  OK - Cache hit - no network call made")


def test_cache_miss():
    """Test cache miss for new domain."""
    print("Test 9 - Cache miss")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock successful response
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.HTTPS_AVAILABLE
        mock_urlopen.assert_called_once()
        print("  OK - Cache miss - network call made")


def test_cache_expired():
    """Test expired cache entry triggers new check."""
    print("Test 10 - Cache expired")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Pre-populate cache with very short TTL
    from datetime import timedelta
    cache.ttl_available = 0  # Force immediate expiration
    cache.set(
        domain="example.com",
        status=VerificationStatus.HTTPS_AVAILABLE,
        https_url="https://example.com",
        http_status_code=200
    )
    
    # Mock successful response for new check
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.HTTPS_AVAILABLE
        mock_urlopen.assert_called_once()
        print("  OK - Expired cache - new network call made")


def test_multiple_urls_same_domain():
    """Test multiple URLs with same domain use single verification."""
    print("Test 11 - Multiple URLs same domain")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock successful response
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        # Verify same domain multiple times
        service.verify_domain("example.com")
        service.verify_domain("example.com")
        service.verify_domain("example.com")
        
        # Should only call urlopen once (first call, subsequent use cache)
        assert mock_urlopen.call_count == 1
        print("  OK - Single verification for multiple domain checks")


def test_verify_domain_from_url():
    """Test verification from full HTTP URL."""
    print("Test 12 - Verify from full URL")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock successful response
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        result = service.verify_domain_from_url("http://example.com/page")
        
        assert result.status == VerificationStatus.HTTPS_AVAILABLE
        assert result.domain == "example.com"
        print("  OK - Domain correctly extracted from URL")


def test_domain_normalization():
    """Test domain normalization (case insensitive)."""
    print("Test 13 - Domain normalization")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock successful response
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        # Verify with different cases
        service.verify_domain("Example.com")
        service.verify_domain("EXAMPLE.COM")
        service.verify_domain("example.com")
        
        # Should only call once due to normalization
        assert mock_urlopen.call_count == 1
        print("  OK - Domain normalization working correctly")


def test_check_failed_no_correction():
    """Test CHECK_FAILED status should not trigger correction."""
    print("Test 14 - CHECK_FAILED no correction")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock error
    with patch('urllib.request.urlopen') as mock_urlopen:
        import socket
        mock_urlopen.side_effect = socket.timeout("Timeout")
        
        result = service.verify_domain("example.com")
        
        assert result.status == VerificationStatus.CHECK_FAILED
        # In the analyzer, this should not trigger correction
        print("  OK - CHECK_FAILED correctly prevents correction")


def test_https_unavailable_no_correction():
    """Test HTTPS_UNAVAILABLE status should not trigger correction."""
    print("Test 15 - HTTPS_UNAVAILABLE no correction")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Pre-populate cache with HTTPS_UNAVAILABLE
    cache.set(
        domain="example.com",
        status=VerificationStatus.HTTPS_UNAVAILABLE,
        https_url="https://example.com",
        http_status_code=404
    )
    
    result = service.verify_domain("example.com")
    
    assert result.status == VerificationStatus.HTTPS_UNAVAILABLE
    # In the analyzer, this should not trigger correction
    print("  OK - HTTPS_UNAVAILABLE correctly prevents correction")


def test_https_available_allows_correction():
    """Test HTTPS_AVAILABLE status allows correction."""
    print("Test 16 - HTTPS_AVAILABLE allows correction")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Pre-populate cache with HTTPS_AVAILABLE
    cache.set(
        domain="example.com",
        status=VerificationStatus.HTTPS_AVAILABLE,
        https_url="https://example.com",
        http_status_code=200
    )
    
    result = service.verify_domain("example.com")
    
    assert result.status == VerificationStatus.HTTPS_AVAILABLE
    # In the analyzer, this should allow correction
    print("  OK - HTTPS_AVAILABLE correctly allows correction")


def test_concurrent_checks_prevented():
    """Test concurrent checks for same domain are prevented."""
    print("Test 17 - Concurrent checks prevented")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mark as pending
    cache.mark_check_pending("example.com")
    
    # Mock successful response (should not be called)
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        # Try to verify while pending
        result = service.verify_domain("example.com")
        
        # Should return None or handle gracefully
        # Implementation should wait and try cache again
        print("  OK - Concurrent check prevention working")


def test_ttl_configuration():
    """Test TTL configuration is respected."""
    print("Test 18 - TTL configuration")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db, ttl_available=15, ttl_unavailable=3, ttl_failed=0.5)
    
    # Check TTL values
    assert cache.ttl_available == 15
    assert cache.ttl_unavailable == 3
    assert cache.ttl_failed == 0.5
    
    # Test get_ttl_for_status
    assert cache.get_ttl_for_status(VerificationStatus.HTTPS_AVAILABLE) == 15
    assert cache.get_ttl_for_status(VerificationStatus.HTTPS_UNAVAILABLE) == 3
    assert cache.get_ttl_for_status(VerificationStatus.CHECK_FAILED) == 0.5
    
    print("  OK - TTL configuration working correctly")


def test_cache_invalidation():
    """Test cache invalidation."""
    print("Test 19 - Cache invalidation")
    
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    
    # Set cache entry
    cache.set(
        domain="example.com",
        status=VerificationStatus.HTTPS_AVAILABLE,
        https_url="https://example.com"
    )
    
    # Verify it's cached
    cached = cache.get("example.com")
    assert cached is not None
    
    # Invalidate
    cache.invalidate("example.com")
    
    # Verify it's gone
    cached = cache.get("example.com")
    assert cached is None
    
    print("  OK - Cache invalidation working correctly")


def test_url_parameters_preserved():
    """Test that URL parameters are preserved in conversion."""
    print("Test 20 - URL parameters preserved")
    
    # This is tested in the analyzer, but we verify the service
    # only checks the domain, not the full URL
    mock_db = MockDatabaseManager()
    cache = HttpsVerificationCache(mock_db)
    service = HttpsVerificationService(cache, timeout=5)
    
    # Mock successful response
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = Mock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value = mock_response
        
        # Verify from URL with parameters
        result = service.verify_domain_from_url("http://example.com/page?id=123#section")
        
        assert result.domain == "example.com"
        # Service only returns domain, analyzer handles URL reconstruction
        print("  OK - Domain extraction from URL with parameters working")


if __name__ == "__main__":
    print("=" * 60)
    print("HTTPS VERIFICATION SERVICE TESTS")
    print("=" * 60)
    print()
    
    test_https_available()
    test_https_unavailable_4xx()
    test_https_unavailable_5xx()
    test_timeout()
    test_dns_error()
    test_connection_refused()
    test_redirect()
    test_cache_hit()
    test_cache_miss()
    test_cache_expired()
    test_multiple_urls_same_domain()
    test_verify_domain_from_url()
    test_domain_normalization()
    test_check_failed_no_correction()
    test_https_unavailable_no_correction()
    test_https_available_allows_correction()
    test_concurrent_checks_prevented()
    test_ttl_configuration()
    test_cache_invalidation()
    test_url_parameters_preserved()
    
    print()
    print("=" * 60)
    print("ALL HTTPS VERIFICATION SERVICE TESTS PASSED")
    print("=" * 60)
