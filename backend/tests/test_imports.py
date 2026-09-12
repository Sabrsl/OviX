"""
Test imports from the new backend/src structure.
"""

import sys
from pathlib import Path

# Add backend/src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'backend' / 'src'))


def test_analyzer_imports():
    """Test that all analyzers can be imported."""
    from wikipedia_maintenance.analyzers import (
        DeadLinkAnalyzer,
        HttpLinksAnalyzer,
        ReferenceEnricherAnalyzer,
        ReferenceAnalyzer,
        ReferenceValidatorAnalyzer,
        BrokenLinkAnalyzer,
        XMLTypographyAnalyzer
    )
    assert DeadLinkAnalyzer is not None
    assert HttpLinksAnalyzer is not None
    assert ReferenceEnricherAnalyzer is not None
    assert ReferenceAnalyzer is not None
    assert ReferenceValidatorAnalyzer is not None
    assert BrokenLinkAnalyzer is not None
    assert XMLTypographyAnalyzer is not None


def test_utils_imports():
    """Test that utils can be imported."""
    from wikipedia_maintenance.utils import DatabaseManager
    from wikipedia_maintenance.utils.publisher import Publisher
    from wikipedia_maintenance.utils.config import load_config
    assert DatabaseManager is not None
    assert Publisher is not None
    assert load_config is not None


def test_orchestrator_imports():
    """Test that orchestrator modules can be imported."""
    from wikipedia_maintenance.orchestrator import AutomationOrchestrator
    from wikipedia_maintenance.orchestrator.scheduler import Scheduler
    assert AutomationOrchestrator is not None
    assert Scheduler is not None


def test_retrievers_imports():
    """Test that retrievers can be imported."""
    from wikipedia_maintenance.retrievers import CategoryRetriever
    from wikipedia_maintenance.retrievers import ManualRetriever
    assert CategoryRetriever is not None
    assert ManualRetriever is not None


if __name__ == "__main__":
    test_analyzer_imports()
    test_utils_imports()
    test_orchestrator_imports()
    test_retrievers_imports()
    print("All import tests passed!")
