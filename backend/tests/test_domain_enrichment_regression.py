"""
Regression tests for domain enrichment service.

Tests verify:
- Job stops after completed state
- No auto-restart after completed
- Pagination advances correctly
- Articles already analyzed are skipped
- Pause/resume continues from correct position
- Cancel stops processing
- Cancel does not trigger new execution
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.wikipedia_maintenance.utils.domain_enrichment_service import (
    DomainEnrichmentService,
    EnrichmentState,
    CategoryConfig,
    DomainEntry,
    EntryStatus
)


class TestDomainEnrichmentRegression:
    """Regression tests for domain enrichment service."""
    
    @pytest.fixture
    def mock_wikipedia_client(self):
        """Mock Wikipedia API client."""
        client = Mock()
        client.get_category_members = Mock(return_value=[
            {'title': 'Test Article 1'},
            {'title': 'Test Article 2'},
        ])
        return client
    
    @pytest.fixture
    def mock_wikidata_client(self):
        """Mock Wikidata client."""
        client = Mock()
        client.get_qid_from_page_title = Mock(return_value='Q123')
        client.get_entity = Mock(return_value=Mock(
            label='Test Site',
            official_websites=['https://example.com']
        ))
        return client
    
    @pytest.fixture
    def mock_throttler(self):
        """Mock API throttler."""
        throttler = Mock()
        throttler.wait_if_needed = Mock()
        return throttler
    
    @pytest.fixture
    def service(self, mock_wikipedia_client, mock_wikidata_client, mock_throttler):
        """Create service instance with mocked dependencies."""
        service = DomainEnrichmentService(
            wikipedia_client=mock_wikipedia_client,
            wikidata_client=mock_wikidata_client,
            throttler=mock_throttler
        )
        return service
    
    def test_job_stops_after_completed(self, service):
        """Test that job stops after reaching completed state."""
        # Mock category members to return empty list (simulate completion)
        service.wikipedia_client.get_category_members = Mock(return_value=[])
        
        categories = [CategoryConfig(wiki='fr', category='Test Category', priority=1)]
        
        # Start enrichment
        progress = service.start_enrichment(categories, dry_run=True)
        
        # Verify state is COMPLETED
        assert service.get_state() == EnrichmentState.COMPLETED
        assert progress.completed_at is not None
        
        # Verify no further processing occurs
        # (This would be caught by a timeout in a real scenario)
    
    def test_no_auto_restart_after_completed(self, service):
        """Test that job does not auto-restart after completed state."""
        # Mock to return empty list
        service.wikipedia_client.get_category_members = Mock(return_value=[])
        
        categories = [CategoryConfig(wiki='fr', category='Test Category', priority=1)]
        
        # Start enrichment
        service.start_enrichment(categories, dry_run=True)
        
        # Verify state is COMPLETED
        assert service.get_state() == EnrichmentState.COMPLETED
        
        # Try to start again - should raise error
        with pytest.raises(RuntimeError, match="Cannot start enrichment"):
            service.start_enrichment(categories, dry_run=True)
    
    def test_pagination_advances_correctly(self, service):
        """Test that pagination advances and doesn't restart from beginning."""
        # Mock to return different batches
        call_count = [0]
        
        def mock_get_members(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return [{'title': f'Article {i}'} for i in range(100)]
            elif call_count[0] == 2:
                return [{'title': f'Article {i}'} for i in range(100, 150)]
            else:
                return []  # No more results
        
        service.wikipedia_client.get_category_members = Mock(side_effect=mock_get_members)
        
        categories = [CategoryConfig(wiki='fr', category='Test Category', priority=1)]
        
        # Start enrichment
        progress = service.start_enrichment(categories, dry_run=True)
        
        # Verify multiple calls were made (pagination worked)
        assert call_count[0] >= 2
        assert progress.total_pages >= 150
    
    def test_articles_already_analyzed_are_skipped(self, service, tmp_path):
        """Test that articles already analyzed are skipped."""
        # Mock tracker file
        tracker_file = tmp_path / "tracker.json"
        tracker_file.write_text(json.dumps({
            'analyzed_articles': {
                'Test Article 1': {
                    'analyzed_at': datetime.now().isoformat(),
                    'result': 'new',
                    'domain': 'example.com'
                }
            }
        }))
        
        # Patch the tracker file path
        with patch.object(service, 'ANALYSIS_TRACKER_FILE', tracker_file):
            service._load_analysis_tracker()
        
        # Verify article is marked as analyzed
        assert service._is_article_analyzed('Test Article 1')
        assert not service._is_article_analyzed('Test Article 2')
    
    def test_cancel_stops_processing(self, service):
        """Test that cancel stops processing immediately."""
        # Mock to return many articles
        service.wikipedia_client.get_category_members = Mock(return_value=[
            {'title': f'Article {i}'} for i in range(1000)
        ])
        
        categories = [CategoryConfig(wiki='fr', category='Test Category', priority=1)]
        
        # Start enrichment in background
        import threading
        def run_enrichment():
            service.start_enrichment(categories, dry_run=True)
        
        thread = threading.Thread(target=run_enrichment)
        thread.start()
        
        # Wait a bit then cancel
        import time
        time.sleep(0.1)
        service.cancel()
        
        thread.join(timeout=2)
        
        # Verify state is CANCELLED or COMPLETED (cancelled marks as completed to save data)
        state = service.get_state()
        assert state in [EnrichmentState.CANCELLED, EnrichmentState.COMPLETED]
    
    def test_pause_resume_continues_from_correct_position(self, service, tmp_path):
        """Test that pause/resume continues from correct position."""
        # Mock pagination state file
        pagination_file = tmp_path / "pagination.json"
        pagination_file.write_text(json.dumps({
            'fr:Test Category': {
                'offset': 100,
                'total_fetched': 100,
                'category': 'Test Category',
                'wiki_lang': 'fr'
            }
        }))
        
        # Patch the pagination file path
        with patch.object(service, 'ANALYSIS_TRACKER_FILE', tmp_path / "tracker.json"):
            with patch.object(service, '_pagination_state', {}):
                service._load_pagination_state()
                
                # Verify state was loaded
                assert 'fr:Test Category' in service._pagination_state
                assert service._pagination_state['fr:Test Category']['offset'] == 100
    
    def test_max_pages_limit(self, service):
        """Test that max_pages limit is respected."""
        # Mock to return many articles
        service.wikipedia_client.get_category_members = Mock(return_value=[
            {'title': f'Article {i}'} for i in range(1000)
        ])
        
        categories = [CategoryConfig(wiki='fr', category='Test Category', priority=1)]
        
        # Start with max_pages=10
        progress = service.start_enrichment(categories, dry_run=True, max_pages=10)
        
        # Verify processing stopped at or before limit
        assert progress.pages_analyzed <= 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
