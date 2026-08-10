"""
User contributions retriever for Wikipedia articles.

Provides robust retrieval of articles edited by a given user,
with options for content fetching, pagination, filtering, and
detailed metadata. Uses pywikibot for Wikipedia interaction.
"""

import logging
from typing import List, Optional, Dict, Any, Generator, Iterator, TYPE_CHECKING
from datetime import datetime, timedelta

from .base import BaseRetriever, Article
from ..utils.published_tracker import PublishedTracker

if TYPE_CHECKING:
    import pywikibot
    from pywikibot import Page, Site, User

logger = logging.getLogger(__name__)


class UserContribsRetriever(BaseRetriever):
    """
    Retrieves articles from a user's contributions.

    Enhanced with:
        - Pagination support (fetch beyond max_articles using continuation)
        - Optional fetching of full page content
        - Detailed contribution metadata (timestamp, size, edit summary)
        - Filtering by date range, minor edits, etc.
        - Proper exception handling and logging
        - Generator interface for streaming results
    """

    def __init__(self, site: Optional['pywikibot.Site'] = None, fetch_content: bool = False, tracker_file: str = "published_articles.json"):
        """
        Initialize the retriever.

        Args:
            site: Pywikibot Site object; if None, use the default site.
            fetch_content: Whether to retrieve the page text content.
            tracker_file: Path to published articles tracker file
        """
        import pywikibot
        super().__init__()
        self.site = site or pywikibot.Site()
        self.fetch_content = fetch_content
        self.tracker = PublishedTracker(tracker_file)

    def set_site(self, site: 'pywikibot.Site') -> None:
        """Set the site to use for API calls."""
        self.site = site

    def retrieve(
        self,
        username: str,
        max_articles: int = 100,
        namespace: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        only_major: bool = False,
        only_minor: bool = False,
        content: Optional[bool] = None,
        exclude_published: bool = True,
    ) -> List[Article]:
        """
        Retrieve articles from a user's contributions.

        Args:
            username: Wikipedia username.
            max_articles: Maximum number of articles to retrieve.
            namespace: Namespace filter (0 for main namespace).
            start_date: Only include edits after this datetime.
            end_date: Only include edits before this datetime.
            only_major: If True, only include non-minor edits.
            only_minor: If True, only include minor edits.
            content: Override the default fetch_content behavior.
            exclude_published: Whether to exclude recently published articles (default: True)

        Returns:
            List of Article objects, sorted by latest edit.
        """
        if not self.site:
            raise ValueError("Site not set. Call set_site() first.")

        user = User(self.site, username)
        articles: List[Article] = []
        seen_titles: set = set()
        count = 0

        # Use a generator to get contributions with pagination
        for contrib in self._iter_contributions(
            user,
            namespace=namespace,
            start_date=start_date,
            end_date=end_date,
            only_major=only_major,
            only_minor=only_minor,
        ):
            title = contrib.get('title')
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            # Don't apply exclude_published filter here - let the caller handle it
            # This ensures we can paginate through all articles even if some are filtered out

            try:
                page = Page(self.site, title)
                if not page.exists():
                    continue

                article = self._create_article_from_contribution(page, contrib)
                # Optionally fetch content
                if content if content is not None else self.fetch_content:
                    article.text = page.text

                articles.append(article)
                count += 1
                if count >= max_articles:
                    break
            except Exception as e:
                logger.warning(f"Error processing article {title}: {e}")
                continue

        return articles

    def _iter_contributions(
        self,
        user: 'pywikibot.User',
        namespace: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        only_major: bool = False,
        only_minor: bool = False,
    ) -> Iterator[Dict[str, Any]]:
        """
        Generator that yields contributions one by one with pagination.

        Uses pywikibot's user.contributions() with total=None to fetch all,
        but applies filtering and pagination manually to respect max_articles
        and date filters.
        """
        # Convert dates to timestamps if provided
        start_ts = start_date.strftime("%Y%m%d%H%M%S") if start_date else None
        end_ts = end_date.strftime("%Y%m%d%H%M%S") if end_date else None

        # Use pywikibot's built-in contribution iterator
        for contrib in user.contributions(
            total=None,  # fetch all; we'll stop when done
            namespace=namespace,
            start=start_ts,
            end=end_ts,
        ):
            # Filter by minor/major
            if only_major and contrib.get('minor'):
                continue
            if only_minor and not contrib.get('minor'):
                continue
            yield contrib

    def _create_article_from_contribution(
        self, page: 'pywikibot.Page', contrib: Dict[str, Any]
    ) -> Article:
        """
        Build an Article object from a Page and its contribution metadata.

        Extends the base Article with extra fields: timestamp, size, summary.
        """
        # Base fields from the page
        article = Article(
            title=page.title(),
            page_id=page.pageid,
            revision_id=page.latest_revision_id,
            url=page.full_url(),
        )

        # Add contribution metadata (optional attributes)
        # We can assign extra attributes if the Article class supports them,
        # or we can store them in a dict. We'll store as attributes if they exist.
        timestamp = contrib.get('timestamp')
        if timestamp:
            article.timestamp = timestamp

        size = contrib.get('size')
        if size is not None:
            article.size = size

        summary = contrib.get('summary')
        if summary:
            article.summary = summary

        return article

    def retrieve_generator(
        self,
        username: str,
        namespace: int = 0,
        max_articles: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        only_major: bool = False,
        only_minor: bool = False,
        content: Optional[bool] = None,
    ) -> Generator[Article, None, None]:
        """
        Generator version of retrieve(), yielding articles one by one.

        Useful for processing large batches without holding all results in memory.
        """
        if not self.site:
            raise ValueError("Site not set. Call set_site() first.")

        user = User(self.site, username)
        seen_titles: set = set()
        count = 0

        for contrib in self._iter_contributions(
            user,
            namespace=namespace,
            start_date=start_date,
            end_date=end_date,
            only_major=only_major,
            only_minor=only_minor,
        ):
            title = contrib.get('title')
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            try:
                page = Page(self.site, title)
                if not page.exists():
                    continue

                article = self._create_article_from_contribution(page, contrib)
                if content if content is not None else self.fetch_content:
                    article.text = page.text

                yield article
                count += 1
                if count >= max_articles:
                    break
            except Exception as e:
                logger.warning(f"Error processing article {title}: {e}")
                continue

    def get_source_type(self) -> str:
        """Return the source type identifier."""
        return "user_contribs"

    # ------------------------------------------------------------------
    # Additional utility methods
    # ------------------------------------------------------------------

    def get_edit_count(self, username: str, namespace: int = 0) -> int:
        """
        Get the total number of edits a user has made in a namespace.

        Useful for estimating how many articles to retrieve.
        """
        if not self.site:
            raise ValueError("Site not set.")
        user = User(self.site, username)
        # Use pywikibot's method if available
        try:
            return user.editCount(namespace=namespace)
        except AttributeError:
            # Fallback: iterate through contributions (expensive)
            count = 0
            for _ in user.contributions(total=None, namespace=namespace):
                count += 1
            return count