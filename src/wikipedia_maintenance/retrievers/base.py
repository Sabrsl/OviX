"""
Base retriever class for Wikipedia articles.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass
from ..utils.api_throttler import get_global_throttler

if TYPE_CHECKING:
    import pywikibot


@dataclass
class Article:
    """Represents a Wikipedia article."""
    title: str
    page_id: int
    revision_id: int
    url: str
    content: Optional[str] = None
    text: Optional[str] = None  # Alias for content


class BaseRetriever:
    """Base class for article retrievers."""
    
    def __init__(self, site: Optional['pywikibot.Site'] = None):
        """
        Initialize retriever.
        
        Args:
            site: Pywikibot site object (optional, can be set later)
        """
        self.site = site
        self.api_throttler = get_global_throttler()
        self._configure_pywikibot_throttling()
    
    def _configure_pywikibot_throttling(self) -> None:
        """Configure pywikibot throttling based on config.yaml settings."""
        try:
            from pathlib import Path
            import yaml
            import pywikibot
            
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and 'api_throttling' in config:
                        throttling_config = config['api_throttling']
                        min_delay = throttling_config.get('min_delay', 11.0)
                        min_delay_min = throttling_config.get('min_delay_min', 8.0)
                        min_delay_max = throttling_config.get('min_delay_max', 15.0)
                        random_delay = throttling_config.get('random_delay', True)
                        max_requests = throttling_config.get('max_requests_per_minute', 10)
                        
                        # Configure pywikibot throttling
                        # Use the default min_delay for pywikibot (it doesn't support random delays)
                        pywikibot.config.put_throttle = min_delay
                        pywikibot.config.maxlag = throttling_config.get('maxlag', 10)  # Wait if server lag exceeds configured seconds
                        pywikibot.config.retry_wait = min_delay
                        
                        import logging
                        logging.getLogger(__name__).info(
                            f"Configured pywikibot throttling: put_throttle={min_delay}s, maxlag={pywikibot.config.maxlag}s, random_delay={random_delay}, range={min_delay_min}s-{min_delay_max}s"
                        )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to configure pywikibot throttling: {e}")
    
    def set_site(self, site: 'pywikibot.Site') -> None:
        """Set the site to use for API calls."""
        self.site = site
    
    def retrieve(self, **kwargs) -> List[Article]:
        """
        Retrieve articles. Must be implemented by subclasses.
        
        Args:
            **kwargs: Implementation-specific parameters
            
        Returns:
            List of Article objects
        """
        raise NotImplementedError("Subclasses must implement retrieve()")
    
    def get_source_type(self) -> str:
        """Get source type identifier."""
        raise NotImplementedError("Subclasses must implement get_source_type()")
