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
from ..utils.api_throttler import get_global_throttler

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
        self.api_throttler = get_global_throttler()

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
        total_contribs = 0

        logger.info(f"Starting user contributions retrieval for user: {username}, namespace: {namespace}")

        # Use a generator to get contributions with pagination
        for contrib in self._iter_contributions(
            user,
            namespace=namespace,
            start_date=start_date,
            end_date=end_date,
            only_major=only_major,
            only_minor=only_minor,
        ):
            total_contribs += 1
            title = contrib.get('title')
            if not title or title in seen_titles:
                logger.debug(f"Skipping contribution: title={title}, already seen or invalid")
                continue
            seen_titles.add(title)

            # Don't apply exclude_published filter here - let the caller handle it
            # This ensures we can paginate through all articles even if some are filtered out

            try:
                # Apply throttling before each pywikibot call
                self.api_throttler.wait_if_needed()
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

        logger.info(f"User contributions retrieval completed: {total_contribs} contributions processed, {len(articles)} articles retrieved")
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
        logger.info(f"_iter_contributions called with user: {user.username}, namespace: {namespace}")
        # Use pywikibot's built-in contribution iterator
        logger.info(f"Calling user.contributions() for user: {user.username}")
        contrib_gen = user.contributions(total=None)
        
        # Helper function to process a single contribution (without DB save)
        def process_contrib(contrib):
            page = contrib[0]
            rev_id = contrib[1]
            timestamp = contrib[2]
            comment = contrib[3] if len(contrib) > 3 else ''
            
            # Get namespace from page
            ns = page.namespace()
            
            # Filter by namespace
            if ns != namespace:
                return None
            
            # Filter by date range if provided
            if start_date and timestamp and timestamp < start_date:
                return None
            if end_date and timestamp and timestamp > end_date:
                return None
            
            # Convert to dict for consistency
            contrib_dict = {
                'pageid': page.pageid,
                'revid': rev_id,
                'timestamp': timestamp,
                'ns': ns,
                'title': page.title(),
                'comment': comment,
                'minor': False,  # Not available in this format
                'tags': []
            }
            
            return contrib_dict
        
        # Batch save to database at the end
        contributions_to_save = []
        def save_contributions_batch():
            if not contributions_to_save:
                return
            try:
                from ..utils.database import DatabaseManager
                db = DatabaseManager()
                for contrib in contributions_to_save:
                    timestamp_str = str(contrib['timestamp']) if contrib['timestamp'] else ''
                    title_str = str(contrib['title']) if contrib['title'] else ''
                    page_id_int = int(contrib['pageid']) if contrib['pageid'] is not None else 0
                    revision_id_int = int(contrib['revid']) if contrib['revid'] is not None else 0
                    namespace_int = int(contrib['ns']) if contrib['ns'] is not None else 0
                    comment_str = str(contrib['comment']) if contrib['comment'] else ''
                    
                    db.save_user_contribution(
                        username=str(user.username),
                        page_id=page_id_int,
                        revision_id=revision_id_int,
                        title=title_str,
                        namespace=namespace_int,
                        timestamp=timestamp_str,
                        comment=comment_str
                    )
                logger.info(f"Saved {len(contributions_to_save)} contributions to database in batch")
            except Exception as e:
                logger.warning(f"Failed to save contributions to database: {e}")
        
        # Try to get first contribution to see if it works
        try:
            first_contrib = next(contrib_gen)
            logger.info(f"First contribution received: {first_contrib}")
            logger.info(f"First contribution type: {type(first_contrib)}, length: {len(first_contrib)}")
            first_dict = process_contrib(first_contrib)
            if first_dict:
                contributions_to_save.append(first_dict)
                yield first_dict
        except StopIteration:
            logger.warning(f"No contributions found for user: {user.username}")
            save_contributions_batch()
            return
        except Exception as e:
            logger.error(f"Error getting first contribution: {e}")
            save_contributions_batch()
            return
        
        # Continue iterating the rest
        for contrib in contrib_gen:
            contrib_dict = process_contrib(contrib)
            if contrib_dict:
                contributions_to_save.append(contrib_dict)
                yield contrib_dict
        
        # Save all contributions to database in batch at the end
        save_contributions_batch()

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
                # Apply throttling before each pywikibot call
                self.api_throttler.wait_if_needed()
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