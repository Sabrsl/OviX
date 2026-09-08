"""
Daily Article Collector for automated daily article collection.

Handles:
- Idempotent daily article collection from Wikipedia categories
- Batch retrieval (100 articles per batch)
- Integration with existing CategoryRetriever
- Database logging for idempotence
- Automation lock for concurrent collection prevention
"""

import logging
import random
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from wikipedia_maintenance.retrievers import CategoryRetriever
from wikipedia_maintenance.utils.database import DatabaseManager
from wikipedia_maintenance.utils.published_tracker import PublishedTracker
from wikipedia_maintenance.utils.analyzed_tracker import AnalyzedTracker

logger = logging.getLogger(__name__)


@dataclass
class DailyCollectionConfig:
    """Configuration for daily article collection."""
    enabled: bool = True
    category: str = "Article à wikifier/Liste complète"
    max_articles: int = 500
    batch_size: int = 100
    exclude_published: bool = True
    exclude_analyzed: bool = True
    lang: str = 'fr'
    family: str = 'wikipedia'


class DailyArticleCollector:
    """
    Daily article collector for automated article collection.
    
    Collects articles from Wikipedia categories and adds them to the analysis queue
    with idempotence guarantees (only once per day).
    """
    
    def __init__(
        self,
        config: DailyCollectionConfig,
        database: DatabaseManager,
        site: Optional[Any] = None,
        published_tracker: Optional[PublishedTracker] = None,
        analyzed_tracker: Optional[AnalyzedTracker] = None
    ):
        """
        Initialize daily article collector.
        
        Args:
            config: DailyCollectionConfig with collection settings
            database: DatabaseManager instance
            site: Pywikibot site object (optional, will create if not provided)
            published_tracker: PublishedTracker for filtering published articles
            analyzed_tracker: AnalyzedTracker for filtering analyzed articles
        """
        self.config = config
        self.database = database
        self.site = site
        self.published_tracker = published_tracker
        self.analyzed_tracker = analyzed_tracker
        
        # Statistics
        self.stats = {
            'articles_retrieved': 0,
            'articles_excluded_published': 0,
            'articles_excluded_analyzed': 0,
            'articles_added_to_queue': 0
        }
        
        logger.info(f"DailyArticleCollector initialized (category={config.category}, max={config.max_articles})")
    
    def has_collected_today(self) -> bool:
        """
        Check if articles have already been collected today.
        
        Returns:
            True if collection already done today
        """
        return self.database.has_collected_today()
    
    def collect_articles(self) -> Dict[str, Any]:
        """
        Collect articles from the configured category.
        
        This method is idempotent - it will only collect once per day.
        
        Returns:
            Collection result with statistics
        """
        # Check if already collected today
        if self.has_collected_today():
            logger.info("Daily collection already completed today, skipping")
            return {
                'success': True,
                'skipped': True,
                'reason': 'already_collected_today',
                'stats': self.stats
            }
        
        # Check if collection is enabled
        if not self.config.enabled:
            logger.info("Daily collection is disabled in config")
            return {
                'success': True,
                'skipped': True,
                'reason': 'disabled',
                'stats': self.stats
            }
        
        # Try to acquire automation lock to prevent concurrent collections
        session_id = f"daily_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        lock_acquired = self.database.acquire_automation_lock(
            session_id=session_id,
            locked_by="daily_collector",
            automation_type="daily_collection"
        )
        
        if not lock_acquired:
            logger.warning("Daily collection lock already held, skipping")
            return {
                'success': True,
                'skipped': True,
                'reason': 'lock_held',
                'stats': self.stats
            }
        
        try:
            logger.info(f"Starting daily article collection from '{self.config.category}'")
            
            # Initialize site if not provided
            if self.site is None:
                import pywikibot
                self.site = pywikibot.Site(self.config.lang, self.config.family)
                logger.info(f"Created pywikibot site for {self.config.lang}.{self.config.family}")
            
            # Create retriever
            retriever = CategoryRetriever(
                self.site,
                tracker_file="published_articles.json" if self.published_tracker else None
            )
            
            # Normalize category name
            category_name = self.config.category
            if not category_name.startswith("Category:"):
                category_name = f"Category:{category_name}"
            
            # Retrieve articles in batches
            all_articles = []
            total_retrieved = 0
            offset = random.randint(0, 5000)  # Random starting offset
            
            while len(all_articles) < self.config.max_articles:
                batch_size = min(self.config.batch_size, self.config.max_articles - len(all_articles))
                
                logger.info(f"Retrieving batch: offset={offset}, batch_size={batch_size}, target={self.config.max_articles}")
                
                batch_articles = retriever.retrieve(
                    category_name=category_name,
                    max_articles=batch_size,
                    recursive=False,
                    exclude_published=self.config.exclude_published,
                    exclude_analyzed=self.config.exclude_analyzed
                )
                
                if not batch_articles:
                    logger.info("No more articles available in category")
                    break
                
                total_retrieved += len(batch_articles)
                logger.info(f"Retrieved {len(batch_articles)} articles (total: {total_retrieved})")
                
                # Filter articles
                filtered_articles = self._filter_articles(batch_articles)
                all_articles.extend(filtered_articles)
                
                offset += batch_size
                
                # Stop if we have enough articles
                if len(all_articles) >= self.config.max_articles:
                    break
                
                # Stop if we've retrieved too many without getting enough eligible articles
                if total_retrieved > self.config.max_articles * 3:
                    logger.warning(f"Retrieved {total_retrieved} articles but only {len(all_articles)} are eligible, stopping")
                    break
            
            # Limit to max_articles
            all_articles = all_articles[:self.config.max_articles]
            
            # Add to analysis queue
            added_count = self._add_to_analysis_queue(all_articles)
            
            # Log the collection
            self.database.log_daily_collection(
                articles_count=added_count,
                category=self.config.category,
                source_details=f"batch_size={self.config.batch_size}"
            )
            
            # Release lock
            self.database.release_automation_lock(session_id)
            
            logger.info(f"Daily collection completed: {added_count} articles added to queue")
            
            return {
                'success': True,
                'skipped': False,
                'articles_added': added_count,
                'stats': self.stats
            }
            
        except Exception as e:
            logger.error(f"Error during daily collection: {e}", exc_info=True)
            
            # Release lock on error
            try:
                self.database.release_automation_lock(session_id)
            except Exception as lock_error:
                logger.error(f"Error releasing lock: {lock_error}")
            
            return {
                'success': False,
                'skipped': False,
                'error': str(e),
                'stats': self.stats
            }
    
    def _filter_articles(self, articles: List[Any]) -> List[Any]:
        """
        Filter articles based on configuration.
        
        Args:
            articles: List of Article objects
            
        Returns:
            Filtered list of articles
        """
        filtered = []
        
        for article in articles:
            # Check if already published (if configured)
            if self.config.exclude_published and self.published_tracker:
                if self.published_tracker.is_published(article.title):
                    self.stats['articles_excluded_published'] += 1
                    continue
            
            # Check if already analyzed (if configured)
            if self.config.exclude_analyzed and self.analyzed_tracker:
                if self.analyzed_tracker.is_analyzed(article.title):
                    self.stats['articles_excluded_analyzed'] += 1
                    continue
            
            filtered.append(article)
        
        self.stats['articles_retrieved'] += len(articles)
        return filtered
    
    def _add_to_analysis_queue(self, articles: List[Any]) -> int:
        """
        Add articles to the analysis queue in database.
        
        Args:
            articles: List of Article objects
            
        Returns:
            Number of articles added
        """
        added_count = 0
        
        for article in articles:
            article_title = article.title if hasattr(article, 'title') else article.get('title')
            page_id = article.page_id if hasattr(article, 'page_id') else article.get('page_id')
            revision_id = article.revision_id if hasattr(article, 'revision_id') else article.get('revision_id')
            
            if not article_title:
                continue
            
            # Generate unique ID
            import hashlib
            article_id = f"{article_title}_{revision_id if revision_id else 0}"
            
            try:
                cursor = self.database.conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO articles_to_analyze
                    (id, title, page_id, revision_id, source, source_details, priority, added_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'medium', ?, 'pending')
                """, (
                    article_id,
                    article_title,
                    page_id,
                    revision_id,
                    'daily_collection',
                    self.config.category,
                    datetime.now().isoformat()
                ))
                self.database.conn.commit()
                
                if cursor.rowcount > 0:
                    added_count += 1
                    logger.debug(f"Added article to analysis queue: {article_title}")
                    
            except Exception as e:
                logger.warning(f"Failed to add article {article_title} to queue: {e}")
                self.database.conn.rollback()
        
        self.stats['articles_added_to_queue'] = added_count
        return added_count
