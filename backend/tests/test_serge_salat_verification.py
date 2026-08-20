"""
Test script to verify ARCHIVE_VERIFICATION retry fix on real article.

Analyzes "Serge Salat" article to confirm:
- Retry logs appear (attempt 1/3, retrying)
- ARCHIVE_VERIFICATION_RETRY_EXHAUSTED appears on 503
- Result is classified as REVIEW_REQUIRED instead of ARCHIVE_NOT_ACCESSIBLE
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test article
ARTICLE_TITLE = "Serge Salat"

def test_serge_salat_analysis():
    """Run analysis on Serge Salat article to verify ARCHIVE_VERIFICATION fix."""
    logger.info("=" * 80)
    logger.info(f"TESTING ARCHIVE_VERIFICATION FIX ON ARTICLE: {ARTICLE_TITLE}")
    logger.info("=" * 80)
    
    # Initialize analyzer
    analyzer = DeadLinkAnalyzer()
    
    # Get article content (simplified - in real scenario would fetch from Wikipedia)
    # For this test, we'll use a placeholder content or fetch if possible
    logger.info(f"Fetching article content for: {ARTICLE_TITLE}")
    
    try:
        # Try to fetch from Wikipedia
        import pywikibot
        site = pywikibot.Site("fr", "wikipedia")
        page = pywikibot.Page(site, ARTICLE_TITLE)
        content = page.text
        
        logger.info(f"Article content fetched: {len(content)} characters")
        
        # Run analysis
        logger.info("Starting dead link analysis...")
        issues = analyzer.analyze(content)
        
        logger.info(f"Analysis completed: {len(issues)} issues found")
        
        # Check for specific log patterns
        logger.info("=" * 80)
        logger.info("CHECKING FOR EXPECTED LOG PATTERNS")
        logger.info("=" * 80)
        
        # Look for ARCHIVE_VERIFICATION_RETRY_EXHAUSTED in issues
        retry_exhausted_count = 0
        review_required_count = 0
        archive_not_accessible_count = 0
        
        for issue in issues:
            repair_status = issue.extra.get('repair_status', 'unknown')
            review_reason = issue.extra.get('review_reason', '')
            
            if repair_status == 'REVIEW_REQUIRED' and review_reason == 'archive_service_unavailable_after_retries':
                retry_exhausted_count += 1
                logger.info(f"✅ FOUND: ARCHIVE_VERIFICATION_RETRY_EXHAUSTED → REVIEW_REQUIRED")
                logger.info(f"   URL: {issue.extra.get('url')}")
                logger.info(f"   Archive URL: {issue.extra.get('archive_url')}")
                logger.info(f"   Archive HTTP Status: {issue.extra.get('archive_http_status')}")
            elif repair_status == 'REVIEW_REQUIRED':
                review_required_count += 1
            elif repair_status == 'ARCHIVE_NOT_ACCESSIBLE':
                archive_not_accessible_count += 1
        
        logger.info("=" * 80)
        logger.info("RESULTS")
        logger.info("=" * 80)
        logger.info(f"ARCHIVE_VERIFICATION_RETRY_EXHAUSTED → REVIEW_REQUIRED: {retry_exhausted_count}")
        logger.info(f"Other REVIEW_REQUIRED: {review_required_count}")
        logger.info(f"ARCHIVE_NOT_ACCESSIBLE: {archive_not_accessible_count}")
        
        if retry_exhausted_count > 0:
            logger.info("✅ SUCCESS: Retry logic is working and classifying 503 as REVIEW_REQUIRED")
            return True
        else:
            logger.warning("⚠️  INCONCLUSIVE: No ARCHIVE_VERIFICATION_RETRY_EXHAUSTED found")
            logger.warning("   This could mean:")
            logger.warning("   - No 503 errors occurred during this run")
            logger.warning("   - The fix is not properly deployed")
            logger.warning("   - The article doesn't trigger the ARCHIVE_VERIFICATION path")
            return False
            
    except Exception as e:
        logger.error(f"❌ EXCEPTION: Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_serge_salat_analysis()
    
    logger.info("=" * 80)
    if success:
        logger.info("TEST PASSED")
        sys.exit(0)
    else:
        logger.info("TEST INCONCLUSIVE OR FAILED")
        sys.exit(1)
