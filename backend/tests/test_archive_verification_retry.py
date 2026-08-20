"""
Test script to verify the retry fix for ARCHIVE_VERIFICATION.

Tests the case where Wayback returns 503 during final verification,
which should now trigger retries instead of immediate failure.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wikipedia_maintenance.utils.link_checker import LinkChecker, LinkStatus

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test case: lecourrierdelarchitecte.com archive URL
test_archive_url = "https://web.archive.org/web/20111113163418/http://www.lecourrierdelarchitecte.com/article_2397"

def test_archive_verification_with_retry():
    """Test archive verification with retry logic."""
    logger.info(f"Testing archive verification with retry for: {test_archive_url}")
    
    # Initialize link checker with default retry (to see if retry logic works)
    link_checker = LinkChecker(timeout=10, max_retries=3)
    
    try:
        logger.info("Starting archive verification...")
        archive_check = link_checker.check_link(test_archive_url)
        
        logger.info(f"Archive verification completed:")
        logger.info(f"  Status: {archive_check.status.value}")
        logger.info(f"  HTTP Status: {archive_check.http_status_code}")
        logger.info(f"  Error Type: {archive_check.error_type}")
        logger.info(f"  Retry Count: {archive_check.retry_count}")
        
        if archive_check.status == LinkStatus.HEALTHY:
            logger.info("✅ SUCCESS: Archive is accessible")
            return True
        else:
            if archive_check.http_status_code in (503, 502, 429):
                logger.warning("⚠️  PARTIAL: Archive verification failed due to service unavailability (even after retries)")
            else:
                logger.warning("❌ FAILED: Archive verification failed due to content error")
            return False
            
    except Exception as e:
        logger.error(f"❌ EXCEPTION: Archive verification failed with exception: {e}")
        return False

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("ARCHIVE VERIFICATION RETRY TEST")
    logger.info("=" * 80)
    
    success = test_archive_verification_with_retry()
    
    logger.info("=" * 80)
    if success:
        logger.info("TEST PASSED")
        sys.exit(0)
    else:
        logger.info("TEST FAILED")
        sys.exit(1)
