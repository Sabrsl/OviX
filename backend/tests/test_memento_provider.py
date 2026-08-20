"""
Test isolé pour MementoAggregatorProvider

Ce script teste le provider Memento Aggregator sur une URL connue
pour vérifier que le parsing JSON correspond bien à la réponse réelle du serveur.
"""

import sys
import logging
from pathlib import Path

# Ajouter le src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wikipedia_maintenance.utils.archive_provider import MementoAggregatorProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# URLs de test (choisies pour leur probabilité d'avoir des archives)
TEST_URLS = [
    "http://www.example.com",  # URL simple, très probablement archivée
    "https://www.wikipedia.org",  # URL majeure, certainement archivée
    "http://www.tpi.setec.fr/FR/050-rd/titane/titane.pdf",  # URL du test Serge Salat
]

def test_memento_provider():
    """Test MementoAggregatorProvider sur plusieurs URLs."""
    provider = MementoAggregatorProvider()
    
    logger.info("=" * 80)
    logger.info("TEST ISOLÉ MementoAggregatorProvider")
    logger.info("=" * 80)
    
    for url in TEST_URLS:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Testing URL: {url}")
        logger.info(f"{'=' * 80}")
        
        result = provider.check_archive(url)
        
        logger.info(f"Result availability: {result.availability.value}")
        logger.info(f"Result reason: {result.reason}")
        
        if result.availability.value == "available":
            logger.info(f"✅ Archive found!")
            logger.info(f"   Archive URL: {result.archive_url}")
            logger.info(f"   Archive date: {result.archive_date}")
            logger.info(f"   Metadata: {result.metadata}")
        elif result.availability.value == "not_available":
            logger.info(f"⚠️  No archive found (confirmed absence)")
        elif result.availability.value == "check_failed":
            logger.info(f"❌ Check failed: {result.reason}")
        elif result.availability.value == "environment_error":
            logger.info(f"🔴 Environment error: {result.reason}")
        else:
            logger.info(f"❓ Unknown status: {result.availability.value}")
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST TERMINÉ")
    logger.info("=" * 80)

if __name__ == "__main__":
    test_memento_provider()
