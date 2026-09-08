"""
Tests for Domain Enrichment functionality.

Tests cover:
- Domain normalization
- Conflict detection
- Wikidata client
- Domain enrichment service
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from wikipedia_maintenance.utils.wikidata_client import WikidataClient, WikidataEntity
from wikipedia_maintenance.utils.domain_enrichment_service import (
    DomainEnrichmentService,
    CategoryConfig,
    EntryStatus,
    DomainEntry,
)


class TestDomainNormalization:
    """Test domain normalization logic."""
    
    def test_normalize_domain_simple(self):
        """Test basic domain normalization."""
        service = DomainEnrichmentService()
        
        # Test various URL formats
        assert service._normalize_domain("https://example.com") == "example.com"
        assert service._normalize_domain("http://example.com") == "example.com"
        assert service._normalize_domain("https://www.example.com") == "example.com"
        assert service._normalize_domain("https://example.com/") == "example.com"
        assert service._normalize_domain("https://example.com/page") == "example.com"
    
    def test_normalize_domain_with_port(self):
        """Test domain normalization with port."""
        service = DomainEnrichmentService()
        
        assert service._normalize_domain("https://example.com:8080") == "example.com"
        assert service._normalize_domain("http://example.com:443") == "example.com"
    
    def test_normalize_domain_invalid(self):
        """Test domain normalization with invalid URLs."""
        service = DomainEnrichmentService()
        
        assert service._normalize_domain("not-a-url") is None
        assert service._normalize_domain("") is None
        assert service._normalize_domain("htp://invalid") is None
        assert service._normalize_domain("a") is None  # Too short


class TestConflictDetection:
    """Test conflict detection logic."""
    
    def test_no_conflict_new_domain(self):
        """Test no conflict for new domain."""
        service = DomainEnrichmentService()
        service._existing_domains = {}
        
        conflict = service._check_conflict("example.com", "Example Site")
        assert conflict is None
    
    def test_conflict_same_domain_different_name(self):
        """Test conflict when domain exists with different name."""
        service = DomainEnrichmentService()
        service._existing_domains = {"example.com": "Old Name"}
        
        conflict = service._check_conflict("example.com", "New Name")
        assert conflict is not None
        assert "Old Name" in conflict
    
    def test_no_conflict_same_domain_same_name(self):
        """Test no conflict when domain exists with same name."""
        service = DomainEnrichmentService()
        service._existing_domains = {"example.com": "Example Site"}
        
        conflict = service._check_conflict("example.com", "Example Site")
        assert conflict is None


class TestWikidataClient:
    """Test Wikidata client functionality."""
    
    def test_get_entity_success(self, mocker):
        """Test successful entity retrieval."""
        # Mock the session and response
        mock_session = mocker.Mock()
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "entities": {
                "Q123": {
                    "labels": {
                        "fr": {"value": "Test Entity"}
                    },
                    "descriptions": {
                        "fr": {"value": "Test Description"}
                    },
                    "claims": {
                        "P856": [
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "type": "string",
                                        "value": "https://example.com"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        mock_session.get.return_value = mock_response
        
        client = WikidataClient(session=mock_session)
        entity = client.get_entity("Q123")
        
        assert entity is not None
        assert entity.qid == "Q123"
        assert entity.label == "Test Entity"
        assert entity.description == "Test Description"
        assert len(entity.official_websites) == 1
        assert entity.official_websites[0] == "https://example.com"
    
    def test_get_entity_not_found(self, mocker):
        """Test entity not found."""
        mock_session = mocker.Mock()
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "entities": {}
        }
        mock_session.get.return_value = mock_response
        
        client = WikidataClient(session=mock_session)
        entity = client.get_entity("Q999")
        
        assert entity is None
    
    def test_get_entity_no_p856(self, mocker):
        """Test entity without P856."""
        mock_session = mocker.Mock()
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "entities": {
                "Q123": {
                    "labels": {
                        "fr": {"value": "Test Entity"}
                    },
                    "claims": {}
                }
            }
        }
        mock_session.get.return_value = mock_response
        
        client = WikidataClient(session=mock_session)
        entity = client.get_entity("Q123")
        
        assert entity is not None
        assert len(entity.official_websites) == 0


class TestDomainEnrichmentService:
    """Test domain enrichment service."""
    
    def test_initialization(self):
        """Test service initialization."""
        service = DomainEnrichmentService()
        
        assert service.get_state().value == "idle"
        assert service.get_progress().pages_analyzed == 0
    
    def test_pause_idle_state(self):
        """Test pause when in idle state."""
        service = DomainEnrichmentService()
        
        # Should not pause when idle
        service.pause()
        assert service.get_state().value == "idle"
    
    def test_resume_not_paused(self):
        """Test resume when not paused."""
        service = DomainEnrichmentService()
        
        # Should not resume when not paused
        service.resume()
        assert service.get_state().value == "idle"
    
    def test_cancel_not_running(self):
        """Test cancel when not running."""
        service = DomainEnrichmentService()
        
        # Should not cancel when not running
        service.cancel()
        assert service.get_state().value == "idle"
    
    def test_get_new_entries_empty(self):
        """Test getting new entries when none exist."""
        service = DomainEnrichmentService()
        service._entries = []
        
        new_entries = service.get_new_entries()
        assert len(new_entries) == 0
    
    def test_get_new_entries_filtered(self):
        """Test getting only new entries."""
        service = DomainEnrichmentService()
        service._entries = [
            DomainEntry("example.com", "Example", EntryStatus.NEW),
            DomainEntry("test.com", "Test", EntryStatus.ALREADY_PRESENT),
            DomainEntry("conflict.com", "Conflict", EntryStatus.CONFLICT),
        ]
        
        new_entries = service.get_new_entries()
        assert len(new_entries) == 1
        assert new_entries[0].domain == "example.com"
    
    def test_get_preview(self):
        """Test preview generation."""
        service = DomainEnrichmentService()
        service._entries = [
            DomainEntry("example.com", "Example", EntryStatus.NEW, "https://example.com", "Example Page", "Q123"),
        ]
        service._progress.new_domains = 1
        service._progress.already_present = 2
        service._progress.conflicts = 1
        
        preview = service.get_preview()
        
        assert len(preview['new_entries']) == 1
        assert preview['new_entries'][0]['domain'] == "example.com"
        assert preview['summary']['total'] == 1
        assert preview['summary']['already_present'] == 2
        assert preview['summary']['conflicts'] == 1


class TestAtomicYamlWriting:
    """Test atomic YAML writing."""
    
    def test_write_yaml_atomic(self, tmp_path):
        """Test atomic YAML writing."""
        service = DomainEnrichmentService()
        
        # Create a temporary file
        test_file = tmp_path / "test.yaml"
        test_file.write_text("domain_to_site_name:\n  existing.com: [[Existing Site]]\n")
        
        # Update the service to use the temp file
        service.CASE_NORMALIZATION_FILE = test_file
        
        # Write new entries
        entries = [
            DomainEntry("new.com", "New Site", EntryStatus.NEW),
        ]
        
        success = service.write_to_yaml(entries)
        
        assert success is True
        
        # Verify the file was updated
        content = test_file.read_text()
        assert "existing.com" in content
        assert "new.com" in content
        assert "New Site" in content
    
    def test_write_yaml_preserves_existing(self, tmp_path):
        """Test that writing preserves existing entries."""
        service = DomainEnrichmentService()
        
        # Create a temporary file with existing data
        test_file = tmp_path / "test.yaml"
        test_file.write_text("domain_to_site_name:\n  existing.com: [[Existing Site]]\n  another.com: [[Another Site]]\n")
        
        service.CASE_NORMALIZATION_FILE = test_file
        
        # Write new entries
        entries = [
            DomainEntry("new.com", "New Site", EntryStatus.NEW),
        ]
        
        service.write_to_yaml(entries)
        
        # Verify existing entries are preserved
        content = test_file.read_text()
        assert "existing.com" in content
        assert "another.com" in content
        assert "new.com" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])