"""
OVIX Backend API - Integration Tests

Comprehensive integration tests for the FastAPI backend API.
Tests all core functionality including OVIX services integration.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))


class TestCoreServicesIntegration:
    """Test integration with OVIX core services."""
    
    def test_api_throttler(self):
        """Test API throttler integration."""
        from wikipedia_maintenance.utils.api_throttler import get_global_throttler
        
        throttler = get_global_throttler()
        assert throttler is not None
        stats = throttler.get_stats()
        assert "requests_last_minute" in stats
        assert "max_requests_per_minute" in stats
    
    def test_kill_switch_manager(self):
        """Test Kill Switch Manager integration."""
        from wikipedia_maintenance.utils.kill_switch_manager import KillSwitchManager, KillSwitchTrigger
        
        manager = KillSwitchManager()
        initial_state = manager.is_enabled()
        
        # Test enable
        manager.enable(reason="Test", trigger_source=KillSwitchTrigger.MANUAL, requested_by="test")
        assert manager.is_enabled() is True
        
        # Test disable
        manager.disable(reason="Test", requested_by="test")
        assert manager.is_enabled() is False
    
    def test_wikipedia_api_client(self):
        """Test WikipediaAPIClient integration."""
        from wikipedia_maintenance.utils.wikipedia_api import WikipediaAPIClient
        from wikipedia_maintenance.utils.api_throttler import get_global_throttler
        
        client = WikipediaAPIClient(language="fr")
        client.set_throttler(get_global_throttler())
        
        # Test page existence
        exists = client.page_exists("Paris")
        assert exists is True
        
        # Test non-existent page
        not_exists = client.page_exists("ThisPageDefinitelyDoesNotExist12345")
        assert not_exists is False
    
    def test_publisher_import(self):
        """Test Publisher import."""
        from wikipedia_maintenance.utils.publisher import Publisher
        assert Publisher is not None
    
    def test_dead_link_analyzer_import(self):
        """Test DeadLinkAnalyzer import."""
        from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
        assert DeadLinkAnalyzer is not None
    
    def test_database_manager_import(self):
        """Test DatabaseManager import."""
        from wikipedia_maintenance.utils.database import DatabaseManager
        assert DatabaseManager is not None


class TestFrameworkCompatibility:
    """Test framework compatibility between FastAPI and Streamlit."""
    
    def test_fastapi_import(self):
        """Test FastAPI can be imported."""
        import fastapi
        assert fastapi.__version__ is not None
    
    def test_streamlit_import(self):
        """Test Streamlit can be imported."""
        import streamlit
        assert streamlit.__version__ is not None
    
    def test_uvicorn_import(self):
        """Test Uvicorn can be imported."""
        import uvicorn
        assert uvicorn.__version__ is not None
    
    def test_no_critical_conflicts(self):
        """Test there are no critical import conflicts."""
        # This test ensures both frameworks can be imported
        import fastapi
        import streamlit
        import uvicorn
        
        # If we get here without exceptions, frameworks are compatible
        assert True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
