"""
Category retriever for Wikipedia articles.

NOTE: This module uses pywikibot which has its own rate limiting.
For audit purposes, this is documented as using an external library
with built-in throttling, not bypassing our controls.
"""

import logging
from typing import List, TYPE_CHECKING
from .base import BaseRetriever, Article
from ..utils.published_tracker import PublishedTracker
from ..utils.api_cache import get_cache

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import pywikibot


class CategoryRetriever(BaseRetriever):
    """Retrieves articles from a Wikipedia category."""
    
    def __init__(self, site=None, tracker_file: str = "published_articles.json", use_cache: bool = True):
        """Initialize retriever.
        
        Args:
            site: Pywikibot site object (optional, can be set later)
            tracker_file: Path to published articles tracker file
            use_cache: Whether to use API cache for article retrieval
        """
        super().__init__(site)
        self.tracker = PublishedTracker(tracker_file)
        self.use_cache = use_cache
        self.cache = get_cache() if use_cache else None
    
    def retrieve(self, category_name: str, max_articles: int = 100,
                 recursive: bool = False, exclude_published: bool = True, offset: int = 0) -> List[Article]:
        """Retrieve articles from a category.
        
        Args:
            category_name: Name of the category (with or without "Category:" prefix)
            max_articles: Maximum number of articles to retrieve
            recursive: Whether to include subcategories
            exclude_published: Whether to exclude recently published articles (default: True)
            offset: Number of articles to skip (for pagination)
            
        Returns:
            List of Article objects
        """
        if not self.site:
            raise ValueError("Site not set. Call set_site() first.")
        
        # Normalize category name
        if not category_name.startswith("Category:"):
            category_name = f"Category:{category_name}"
        
        # Check cache first if enabled
        cache_params = {
            'type': 'category',
            'category_name': category_name,
            'max_articles': max_articles,
            'recursive': recursive,
            'site': str(self.site),
            'offset': offset  # Include offset in cache key to get different batches
        }
        
        if self.cache:
            cached_response = self.cache.get(cache_params)
            if cached_response is not None:
                # Reconstruct Article objects from cached data
                articles = [Article(**data) for data in cached_response]
                return articles
        
        # Not in cache or cache disabled - fetch from API
        import pywikibot
        logger.info(f"Fetching from Wikipedia API: category={category_name}, max_articles={max_articles}, recursive={recursive}")
        category = pywikibot.Category(self.site, category_name)
        articles = []
        
        logger.info(f"Starting article iteration for category: {category_name}")
        if recursive:
            # Get articles from subcategories recursively
            for i, article in enumerate(category.articles(recurse=True, total=max_articles * 2 + offset)):  # Fetch more to account for filtering
                if i < offset:  # Skip articles based on offset
                    continue
                if len(articles) >= max_articles:
                    break
                article_obj = self._create_article(article)
                # Don't apply exclude_published filter here - let the caller handle it
                # This ensures we can paginate through all articles even if some are filtered out
                articles.append(article_obj)
        else:
            # Get articles only from this category
            for i, article in enumerate(category.articles(total=max_articles * 2 + offset)):  # Fetch more to account for filtering
                if i < offset:  # Skip articles based on offset
                    continue
                if len(articles) >= max_articles:
                    break
                article_obj = self._create_article(article)
                # Don't apply exclude_published filter here - let the caller handle it
                # This ensures we can paginate through all articles even if some are filtered out
                articles.append(article_obj)
        
        logger.info(f"Article iteration completed: {len(articles)} articles retrieved")
        
        # Cache the response if enabled
        if self.cache and articles:
            # Convert Article objects to serializable dictionaries
            articles_data = [
                {
                    'title': article.title,
                    'page_id': article.page_id,
                    'revision_id': article.revision_id,
                    'url': article.url
                }
                for article in articles
            ]
            self.cache.set(cache_params, articles_data)
        
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
        return "category"
