"""
Tests for HTTPS verification cache persistence across sessions.

Tests that:
1. Cache entries persist across program restarts
2. Expired entries are handled correctly
3. Multiple sessions can reuse the same cache
"""

import sys
import logging
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Suppress warnings during tests
logging.getLogger('wikipedia_maintenance.utils.https_verification_service').setLevel(logging.CRITICAL)

# Ajouter src au chemin
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from wikipedia_maintenance.utils.database import DatabaseManager
from wikipedia_maintenance.utils.https_verification_cache import (
    HttpsVerificationCache,
    VerificationStatus
)
from wikipedia_maintenance.utils.https_verification_service import HttpsVerificationService
from wikipedia_maintenance.analyzers.http_links import HttpLinksAnalyzer


def test_cache_persistence_across_sessions():
    """Test that cache persists across different sessions."""
    print("Test 1 - Cache persistence across sessions")
    
    # Create temporary directory for test database
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_cache.db"
    
    try:
        # Session 1: Verify a domain and cache result
        db1 = DatabaseManager(str(db_path))
        cache1 = HttpsVerificationCache(db1)
        service1 = HttpsVerificationService(cache1, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            result1 = service1.verify_domain("example.com")
            assert result1.status == VerificationStatus.HTTPS_AVAILABLE
            call_count_1 = mock_urlopen.call_count
        
        # Close first session
        db1.conn.close()
        
        # Session 2: Reopen database and check cache
        db2 = DatabaseManager(str(db_path))
        cache2 = HttpsVerificationCache(db2)
        service2 = HttpsVerificationService(cache2, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            result2 = service2.verify_domain("example.com")
            assert result2.status == VerificationStatus.HTTPS_AVAILABLE
            call_count_2 = mock_urlopen.call_count
        
        # Should not make network call (cache hit)
        assert call_count_2 == 0
        
        db2.conn.close()
        
        print("  OK - Cache persists across sessions")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_cache_entry_expiration():
    """Test that expired cache entries trigger new verification."""
    print("Test 2 - Cache entry expiration")
    
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_expiration.db"
    
    try:
        # Session 1: Cache with very short TTL
        db1 = DatabaseManager(str(db_path))
        cache1 = HttpsVerificationCache(db1, ttl_available=0)  # Immediate expiration
        service1 = HttpsVerificationService(cache1, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            result1 = service1.verify_domain("example.com")
            assert result1.status == VerificationStatus.HTTPS_AVAILABLE
            call_count_1 = mock_urlopen.call_count
        
        db1.conn.close()
        
        # Manually invalidate to force expiration
        db2 = DatabaseManager(str(db_path))
        cache2 = HttpsVerificationCache(db2, ttl_available=0)
        cache2.invalidate("example.com")
        
        service2 = HttpsVerificationService(cache2, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            result2 = service2.verify_domain("example.com")
            assert result2.status == VerificationStatus.HTTPS_AVAILABLE
            call_count_2 = mock_urlopen.call_count
        
        # Should make network call (cache invalidated)
        assert call_count_2 == 1
        
        db2.conn.close()
        
        print("  OK - Expired entries trigger new verification")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_multiple_sessions_same_domain():
    """Test multiple concurrent sessions reusing same cache."""
    print("Test 3 - Multiple sessions same domain")
    
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_concurrent.db"
    
    try:
        # Session 1: Verify domain
        db1 = DatabaseManager(str(db_path))
        cache1 = HttpsVerificationCache(db1)
        service1 = HttpsVerificationService(cache1, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            result1 = service1.verify_domain("example.com")
            assert result1.status == VerificationStatus.HTTPS_AVAILABLE
            call_count_1 = mock_urlopen.call_count
        
        db1.conn.close()
        
        # Session 2: Check same domain (should use cache)
        db2 = DatabaseManager(str(db_path))
        cache2 = HttpsVerificationCache(db2)
        service2 = HttpsVerificationService(cache2, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            result2 = service2.verify_domain("example.com")
            assert result2.status == VerificationStatus.HTTPS_AVAILABLE
            call_count_2 = mock_urlopen.call_count
        
        db2.conn.close()
        
        # Session 3: Check same domain again (should use cache)
        db3 = DatabaseManager(str(db_path))
        cache3 = HttpsVerificationCache(db3)
        service3 = HttpsVerificationService(cache3, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            result3 = service3.verify_domain("example.com")
            assert result3.status == VerificationStatus.HTTPS_AVAILABLE
            call_count_3 = mock_urlopen.call_count
        
        db3.conn.close()
        
        # Only session 1 should have made network call
        assert call_count_1 == 1
        assert call_count_2 == 0
        assert call_count_3 == 0
        
        print("  OK - Multiple sessions reuse cache")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_different_domains_separate_cache():
    """Test that different domains have separate cache entries."""
    print("Test 4 - Different domains separate cache")
    
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_separate.db"
    
    try:
        # Session 1: Verify multiple domains
        db1 = DatabaseManager(str(db_path))
        cache1 = HttpsVerificationCache(db1)
        service1 = HttpsVerificationService(cache1, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            service1.verify_domain("example.com")
            service1.verify_domain("test.com")
            service1.verify_domain("demo.com")
            
            call_count_1 = mock_urlopen.call_count
        
        db1.conn.close()
        
        # Session 2: Check each domain (should all use cache)
        db2 = DatabaseManager(str(db_path))
        cache2 = HttpsVerificationCache(db2)
        service2 = HttpsVerificationService(cache2, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            service2.verify_domain("example.com")
            service2.verify_domain("test.com")
            service2.verify_domain("demo.com")
            
            call_count_2 = mock_urlopen.call_count
        
        db2.conn.close()
        
        # Session 2 should not make any network calls
        assert call_count_2 == 0
        
        print("  OK - Different domains have separate cache entries")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_cache_invalidation_persists():
    """Test that cache invalidation persists across sessions."""
    print("Test 5 - Cache invalidation persists")
    
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_invalidation.db"
    
    try:
        # Session 1: Cache domain then invalidate
        db1 = DatabaseManager(str(db_path))
        cache1 = HttpsVerificationCache(db1)
        service1 = HttpsVerificationService(cache1, timeout=5)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            result1 = service1.verify_domain("example.com")
            assert result1.status == VerificationStatus.HTTPS_AVAILABLE
        
        # Invalidate
        cache1.invalidate("example.com")
        
        # Verify it's gone
        cached = cache1.get("example.com")
        assert cached is None
        
        db1.conn.close()
        
        # Session 2: Should still be invalidated
        db2 = DatabaseManager(str(db_path))
        cache2 = HttpsVerificationCache(db2)
        
        cached = cache2.get("example.com")
        assert cached is None
        
        db2.conn.close()
        
        print("  OK - Cache invalidation persists")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_database_cleanup_expired():
    """Test that expired entries can be cleaned up."""
    print("Test 6 - Database cleanup expired")
    
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_cleanup.db"
    
    try:
        # Session 1: Add entry with normal TTL
        db1 = DatabaseManager(str(db_path))
        cache1 = HttpsVerificationCache(db1)
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            service1 = HttpsVerificationService(cache1, timeout=5)
            service1.verify_domain("example.com")
        
        db1.conn.close()
        
        # Manually expire the entry by setting expires_at to past
        db2 = DatabaseManager(str(db_path))
        past_time = datetime.now() - timedelta(days=1)
        cursor = db2.conn.cursor()
        cursor.execute(
            "UPDATE https_verification_cache SET expires_at = ? WHERE domain = ?",
            (past_time.isoformat(), "example.com")
        )
        db2.conn.commit()
        
        cache2 = HttpsVerificationCache(db2)
        
        # Cleanup should remove expired entry
        removed = cache2.cleanup_expired()
        assert removed >= 1  # Should have removed the expired entry
        
        # Verify entry is gone
        cached = cache2.get("example.com")
        assert cached is None
        
        db2.conn.close()
        
        print("  OK - Expired entries cleaned up")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_analyzer_integration_with_persistence():
    """Test HttpLinksAnalyzer integration with persistent cache."""
    print("Test 7 - Analyzer integration with persistence")
    
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_analyzer.db"
    
    try:
        # Session 1: Analyze with HTTPS verification
        db1 = DatabaseManager(str(db_path))
        cache1 = HttpsVerificationCache(db1)
        service1 = HttpsVerificationService(cache1, timeout=5)
        
        analyzer1 = HttpLinksAnalyzer(
            max_issues=None,
            enable_https_verification=True,
            https_verification_service=service1
        )
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            content1 = "Voir http://example.com/page1"
            issues1 = analyzer1.analyze(content1)
            
            assert len(issues1) == 1
            assert issues1[0].suggested_text is not None
            call_count_1 = mock_urlopen.call_count
        
        db1.conn.close()
        
        # Session 2: Analyze again (should use cache)
        db2 = DatabaseManager(str(db_path))
        cache2 = HttpsVerificationCache(db2)
        service2 = HttpsVerificationService(cache2, timeout=5)
        
        analyzer2 = HttpLinksAnalyzer(
            max_issues=None,
            enable_https_verification=True,
            https_verification_service=service2
        )
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = Mock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response
            
            content2 = "Voir http://example.com/page2"
            issues2 = analyzer2.analyze(content2)
            
            assert len(issues2) == 1
            assert issues2[0].suggested_text is not None
            call_count_2 = mock_urlopen.call_count
        
        db2.conn.close()
        
        # Session 2 should not make network call
        assert call_count_2 == 0
        
        print("  OK - Analyzer integration with persistence")
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("HTTPS PERSISTENCE TESTS")
    print("=" * 60)
    print()
    
    test_cache_persistence_across_sessions()
    test_cache_entry_expiration()
    test_multiple_sessions_same_domain()
    test_different_domains_separate_cache()
    test_cache_invalidation_persists()
    test_database_cleanup_expired()
    test_analyzer_integration_with_persistence()
    
    print()
    print("=" * 60)
    print("ALL HTTPS PERSISTENCE TESTS PASSED")
    print("=" * 60)
