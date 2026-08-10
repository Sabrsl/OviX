"""
PetScan retriever for Wikipedia articles.

Uses the centralized api_throttler for all API calls to ensure
consistent rate limiting and error handling.
"""

import requests
from typing import List
from .base import BaseRetriever, Article
from ..utils.published_tracker import PublishedTracker
from ..utils.api_throttler import get_global_throttler


class PetScanRetriever(BaseRetriever):
    """Retrieves articles from PetScan queries."""
    
    def __init__(self, tracker_file: str = "published_articles.json"):
        """Initialize retriever.
        
        Args:
            tracker_file: Path to published articles tracker file
        """
        super().__init__()
        self.tracker = PublishedTracker(tracker_file)
        self.api_throttler = get_global_throttler()
        
        # Load PetScan URL and timeout from config.yaml
        import yaml
        from pathlib import Path
        self.PETSCAN_API_URL = "https://petscan.wmflabs.org/"
        self.api_timeout = 30
        
        try:
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config:
                        if 'api_urls' in config and 'petscan' in config['api_urls']:
                            self.PETSCAN_API_URL = config['api_urls']['petscan']
                        if 'timeouts' in config and 'petscan_api' in config['timeouts']:
                            self.api_timeout = config['timeouts']['petscan_api']
        except Exception:
            pass
    
    def retrieve(self, psid: int = None, query_params: dict = None,
                 max_articles: int = 100, exclude_published: bool = True, offset: int = 0) -> List[Article]:
        """Retrieve articles from PetScan.
        
        Args:
            psid: PetScan query ID (if using saved query)
            query_params: Dictionary of PetScan parameters (alternative to psid)
            max_articles: Maximum number of articles to retrieve
            exclude_published: Whether to exclude recently published articles (default: True)
            offset: Number of articles to skip (for pagination)
            
        Returns:
            List of Article objects
        """
        if psid:
            # Use saved PetScan query
            params = {
                'psid': psid,
                'format': 'json',
                'doit': '1',
                'offset': offset  # Add offset for pagination
            }
        elif query_params:
            # Use custom query parameters
            params = query_params.copy()
            params['format'] = 'json'
            params['doit'] = '1'
            params['offset'] = offset  # Add offset for pagination
        else:
            raise ValueError("Either psid or query_params must be provided")
        
        try:
            # Apply throttling before request
            self.api_throttler.wait_if_needed()
            
            response = requests.get(self.PETSCAN_API_URL, params=params, timeout=self.api_timeout)
            
            # Handle 429 errors
            if response.status_code == 429:
                self.api_throttler.report_429()
                logger.warning(f"Received 429 from PetScan, backing off...")
                self.api_throttler.wait_if_needed()
                response = requests.get(self.PETSCAN_API_URL, params=params, timeout=self.api_timeout)
                if response.status_code == 429:
                    logger.error("Still getting 429 from PetScan after backoff")
                    raise Exception("Rate limit exceeded")
                else:
                    self.api_throttler.report_success()
            else:
                self.api_throttler.report_success()
            
            response.raise_for_status()
            data = response.json()
            
            articles = []
            if '*articles' in data:
                for article_data in data['*articles']:
                    if len(articles) >= max_articles:
                        break
                    article = self._create_article_from_data(article_data)
                    # Don't apply exclude_published filter here - let the caller handle it
                    # This ensures we can paginate through all articles even if some are filtered out
                    articles.append(article)
            
            return articles
            
        except requests.RequestException as e:
            raise Exception(f"Error fetching from PetScan: {e}")
    
    def _create_article_from_data(self, data: dict) -> Article:
        """Create an Article object from PetScan data.
        
        Args:
            data: Article data from PetScan
            
        Returns:
            Article object
        """
        return Article(
            title=data.get('title', ''),
            page_id=data.get('id'),
            url=data.get('url')
        )
    
    def get_source_type(self) -> str:
        """Get source type identifier."""
        return "petscan"
