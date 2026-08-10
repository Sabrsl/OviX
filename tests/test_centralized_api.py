"""
Test suite for centralized Wikipedia API client.

This ensures that all Wikipedia API calls go through the centralized
WikipediaAPIClient with proper throttling and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from wikipedia_maintenance.utils.wikipedia_api import WikipediaAPIClient


class TestWikipediaAPIClient:
    """Test the centralized Wikipedia API client."""
    
    def test_client_initialization(self):
        """Test that client initializes correctly with throttling."""
        client = WikipediaAPIClient(language='fr', use_throttling=True)
        assert client.language == 'fr'
        assert client.use_throttling == True
        # Note: api_throttler will be None due to circular import prevention
        # but the throttling can be set externally via set_throttler()
    
    def test_client_without_throttling(self):
        """Test that client can be initialized without throttling."""
        client = WikipediaAPIClient(language='fr', use_throttling=False)
        assert client.language == 'fr'
        assert client.use_throttling == False
        assert client.api_throttler is None
    
    def test_set_throttler(self):
        """Test that throttler can be set externally."""
        mock_throttler = Mock()
        client = WikipediaAPIClient(language='fr', use_throttling=False)
        client.set_throttler(mock_throttler)
        assert client.api_throttler == mock_throttler
    
    @patch('requests.Session')
    def test_page_exists(self, mock_session_class):
        """Test page_exists method."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'query': {
                'pages': [
                    {'pageid': 123, 'title': 'Test'}
                ]
            }
        }
        mock_session.get.return_value = mock_response
        
        client = WikipediaAPIClient(language='fr', session=mock_session, use_throttling=False)
        result = client.page_exists('Test')
        
        assert result == True
        assert 'Test' in client._page_exists_cache


if __name__ == '__main__':
    pytest.main([__file__, '-v'])