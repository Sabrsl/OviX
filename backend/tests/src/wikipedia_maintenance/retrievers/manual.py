"""
Manual retriever for Wikipedia articles.
"""

from typing import List, TYPE_CHECKING
from .base import BaseRetriever, Article
from ..utils.published_tracker import PublishedTracker
from ..utils.api_throttler import get_global_throttler

if TYPE_CHECKING:
    import pywikibot


class ManualRetriever(BaseRetriever):
    """Retrieves articles from a manually provided list of titles."""
    
    def __init__(self, tracker_file: str = "published_articles.json"):
        """Initialize retriever.
        
        Args:
            tracker_file: Path to published articles tracker file
        """
        super().__init__()
        self.tracker = PublishedTracker(tracker_file)
        self.api_throttler = get_global_throttler()
    
    def retrieve(self, titles: List[str], exclude_published: bool = True) -> List[Article]:
        """Retrieve articles from a list of titles.
        
        Args:
            titles: List of article titles
            exclude_published: Whether to exclude recently published articles (default: True)
            
        Returns:
            List of Article objects
        """
        import pywikibot
        
        if not self.site:
            raise ValueError("Site not set. Call set_site() first.")
        
        articles = []
        for title in titles:
            # Exclude recently published articles
            if exclude_published and self.tracker.is_recently_published(title):
                continue
            
            # Apply throttling before each pywikibot call
            self.api_throttler.wait_if_needed()
            
            try:
                page = pywikibot.Page(self.site, title)
                if page.exists():
                    articles.append(self._create_article(page))
            except pywikibot.exceptions.NoPage:
                # Skip non-existent pages
                continue
            except Exception as e:
                # Log error but continue with other articles
                print(f"Error retrieving {title}: {e}")
                continue
        
        return articles
    
    def _create_article(self, page: 'pywikibot.Page') -> Article:
        """Create an Article object from a Pywikibot Page.
        
        Args:
            page: Pywikibot Page object
            
        Returns:
            Article object
        """
        return Article(
            title=page.title(),
            page_id=page.pageid,
            revision_id=page.latest_revision_id,
            url=page.full_url()
        )
    
    def get_source_type(self) -> str:
        """Get source type identifier."""
        return "manual"
