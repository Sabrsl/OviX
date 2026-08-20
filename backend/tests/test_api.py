"""
OVIX Backend API - Basic Tests

Tests the FastAPI endpoints to ensure they work correctly.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

from fastapi.testclient import TestClient
from backend.api.main import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check returns 200."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "services" in data


class TestAuthentication:
    """Test authentication endpoints."""
    
    def test_login_without_credentials(self, client):
        """Test login without credentials (retrieval only)."""
        response = client.post("/api/auth/login", json={
            "lang": "fr",
            "family": "wikipedia"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["lang"] == "fr"
    
    def test_get_auth_status(self, client):
        """Test get auth status."""
        response = client.get("/api/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert "authenticated" in data
    
    def test_logout(self, client):
        """Test logout."""
        response = client.post("/api/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestArticles:
    """Test article endpoints."""
    
    def test_category_search_requires_auth(self, client):
        """Test category search requires authentication."""
        response = client.post("/api/articles/category", json={
            "category": "Article à wikifier",
            "limit": 10
        })
        assert response.status_code == 401
    
    def test_manual_search_requires_auth(self, client):
        """Test manual search requires authentication."""
        response = client.post("/api/articles/manual", json={
            "titles": ["Test"]
        })
        assert response.status_code == 401


class TestAnalysis:
    """Test analysis endpoints."""
    
    def test_start_analysis_requires_auth(self, client):
        """Test start analysis requires authentication."""
        response = client.post("/api/analysis/start", json={
            "article_title": "Test",
            "mode": "regex"
        })
        assert response.status_code == 401
    
    def test_get_analysis_status_not_found(self, client):
        """Test get analysis status for non-existent job."""
        response = client.get("/api/analysis/nonexistent")
        assert response.status_code == 404


class TestDiff:
    """Test diff endpoints."""
    
    def test_generate_diff(self, client):
        """Test diff generation."""
        response = client.post("/api/diff/generate", json={
            "original": "Hello world",
            "corrected": "Hello world!",
            "diff_type": "html"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "diff_id" in data
        assert data["stats"]["original_length"] == 11
        assert data["stats"]["corrected_length"] == 12
    
    def test_get_diff_info(self, client):
        """Test get diff info."""
        # First create a diff
        create_response = client.post("/api/diff/generate", json={
            "original": "Test",
            "corrected": "Test modified",
            "diff_type": "html"
        })
        diff_id = create_response.json()["diff_id"]
        
        # Then get it
        response = client.get(f"/api/diff/{diff_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["diff_id"] == diff_id


class TestPublication:
    """Test publication endpoints."""
    
    def test_validate_requires_auth(self, client):
        """Test publication validation requires authentication."""
        response = client.post("/api/publication/validate", json={
            "article_title": "Test",
            "corrected_content": "Test",
            "summary": "Test",
            "dry_run": True
        })
        assert response.status_code == 401
    
    def test_publish_requires_auth(self, client):
        """Test publish requires authentication."""
        response = client.post("/api/publication/publish", json={
            "article_title": "Test",
            "corrected_content": "Test",
            "summary": "Test",
            "dry_run": True
        })
        assert response.status_code == 401


class TestHistory:
    """Test history endpoints."""
    
    def test_get_published_history(self, client):
        """Test get published history."""
        response = client.get("/api/history/published")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "items" in data
    
    def test_get_analyzed_history(self, client):
        """Test get analyzed history."""
        response = client.get("/api/history/analyzed")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_statistics(self, client):
        """Test get statistics."""
        response = client.get("/api/history/statistics")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "stats" in data


class TestLogs:
    """Test log endpoints."""
    
    def test_get_logs(self, client):
        """Test get logs."""
        response = client.get("/api/logs/")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_recent_logs(self, client):
        """Test get recent logs."""
        response = client.get("/api/logs/recent")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_log_stats(self, client):
        """Test get log stats."""
        response = client.get("/api/logs/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestSettings:
    """Test settings endpoints."""
    
    def test_get_settings(self, client):
        """Test get settings."""
        response = client.get("/api/settings/")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "settings" in data


class TestSystem:
    """Test system endpoints."""
    
    def test_get_kill_switch_status(self, client):
        """Test get kill switch status."""
        response = client.get("/api/system/kill-switch")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
    
    def test_activate_kill_switch(self, client):
        """Test activate kill switch."""
        response = client.post("/api/system/kill-switch/activate", json={
            "enabled": True,
            "reason": "Test activation",
            "requested_by": "test"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_deactivate_kill_switch(self, client):
        """Test deactivate kill switch."""
        response = client.post("/api/system/kill-switch/deactivate", json={
            "enabled": False,
            "reason": "Test deactivation",
            "requested_by": "test"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_scheduler_status(self, client):
        """Test get scheduler status."""
        response = client.get("/api/system/scheduler")
        assert response.status_code == 200
        data = response.json()
        assert "is_active" in data
    
    def test_start_scheduler(self, client):
        """Test start scheduler."""
        response = client.post("/api/system/scheduler/start")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_get_automation_status(self, client):
        """Test get automation status."""
        response = client.get("/api/system/automation")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
