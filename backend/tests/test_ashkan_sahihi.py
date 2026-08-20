"""
Test script pour Ashkan Sahihi - investigation du 0 problèmes détectés dans l'UI
"""

import sys
import logging
from pathlib import Path

# Ajouter le src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

def test_ashkan_sahihi():
    """Test DeadLinkAnalyzer sur l'article Ashkan Sahihi."""
    analyzer = DeadLinkAnalyzer()
    
    article_title = "Ashkan Sahihi"
    
    logger.info("=" * 80)
    logger.info(f"TEST Ashkan Sahihi - {article_title}")
    logger.info("=" * 80)
    
    try:
        issues = analyzer.analyze(article_title)
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"RÉSULTATS")
        logger.info(f"{'=' * 80}")
        logger.info(f"Total problèmes: {len(issues)}")
        
        if issues:
            logger.info(f"\nDétail des problèmes:")
            for i, issue in enumerate(issues, 1):
                logger.info(f"\n{i}. {issue.issue_type}")
                logger.info(f"   Description: {issue.description}")
                logger.info(f"   Sévérité: {issue.severity}")
                logger.info(f"   Confidence: {issue.confidence}")
                if issue.extra:
                    logger.info(f"   Extra: {issue.extra}")
        else:
            logger.info("Aucun problème détecté")
            
        logger.info(f"\n{'=' * 80}")
        logger.info("TEST TERMINÉ")
        logger.info(f"{'=' * 80}")
        
        return issues
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    issues = test_ashkan_sahihi()
