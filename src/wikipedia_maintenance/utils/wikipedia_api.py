"""
Wikipedia API client for page existence checks, category operations, and metadata retrieval.

This is the CENTRALIZED client for ALL Wikipedia API calls. All modules must use this client
to ensure consistent throttling, error handling, and monitoring.

Provides:
    - page_exists(title) - Check if a page exists
    - category_exists(title) - Check if a category exists
    - resolve_redirect(title) - Resolve redirects to canonical title
    - get_page_metadata(title) - Get page metadata
    - get_page_content(title) - Get page wikitext content
    - get_category_members(category) - Get category members
    - edit_page(title, content, summary) - Edit a page
    - check_page_protection(titles) - Check protection status
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PageMetadata:
    """Metadata about a Wikipedia page."""
    title: str
    pageid: int
    exists: bool
    is_redirect: bool
    redirect_target: Optional[str] = None
    last_revision_id: Optional[int] = None
    last_revision_timestamp: Optional[str] = None
    length: Optional[int] = None


class WikipediaAPIClient:
    """CENTRALIZED client for ALL Wikipedia API operations with throttling."""
    
    def __init__(
        self,
        language: str = 'fr',
        api_url: Optional[str] = None,
        session=None,
        timeout: float = 10.0,
        user_agent: Optional[str] = None,
        use_throttling: bool = True,
    ):
        """
        Args:
            language: Language code (e.g., 'fr', 'en').
            api_url: Custom API URL (if None, uses standard Wikipedia API).
            session: Optional requests.Session for connection pooling.
            timeout: Request timeout in seconds.
            user_agent: User-Agent string for API requests (if None, uses bot identity).
            use_throttling: Whether to apply global throttling (default: True).
        """
        # Use provided language or fallback to config
        if language is None or language == '':
            try:
                from .config import load_config
                config = load_config()
                self.language = config.wikipedia.lang.lower()
            except Exception:
                self.language = 'fr'  # Ultimate fallback
        else:
            self.language = language.lower()
            
        # Use provided timeout or fallback to config
        if timeout is None or timeout <= 0:
            try:
                from .config import load_config
                config = load_config()
                self.timeout = config.wikipedia.timeout
            except Exception:
                self.timeout = 10.0  # Ultimate fallback
        else:
            self.timeout = timeout
            
        self.api_url = api_url or f'https://{self.language}.wikipedia.org/w/api.php'
        
        # P2 FIX: Use bot identity system if user_agent not provided
        if user_agent is None:
            try:
                from .bot_identity import get_user_agent
                self.user_agent = get_user_agent(purpose="Wikipedia API")
            except ImportError:
                self.user_agent = 'WikipediaMaintenanceTool/1.0'
        else:
            self.user_agent = user_agent
            
        self.use_throttling = use_throttling
        self._session = session
        self.api_throttler = None  # Set externally via set_throttler() if needed
    
    def set_throttler(self, throttler):
        """Set the throttler instance externally to avoid circular imports."""
        self.api_throttler = throttler
        
        # Caches
        self._page_exists_cache: Dict[str, bool] = {}
        self._category_exists_cache: Dict[str, bool] = {}
        self._redirect_cache: Dict[str, Optional[str]] = {}
        self._metadata_cache: Dict[str, PageMetadata] = {}
        
        # Initialize session if not provided
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                # Set User-Agent to avoid being blocked
                self._session.headers.update({'User-Agent': self.user_agent})
            except ImportError:
                logger.warning("requests not installed; API calls will fail.")
                self._session = None
    
    def _make_request(self, params: Dict[str, Any], method: str = 'GET') -> Any:
        """
        Make a throttled request to the Wikipedia API.
        
        Args:
            params: API parameters
            method: HTTP method (GET or POST)
            
        Returns:
            JSON response data
            
        Raises:
            Exception: If request fails
        """
        if not self._session:
            raise Exception("No session available")
        
        # Apply throttling before request if throttler is available
        if self.api_throttler:
            self.api_throttler.wait_if_needed()
        
        # Add maxlag parameter to respect server lag
        params = params.copy()
        if 'maxlag' not in params:
            params['maxlag'] = 5
        
        try:
            if method == 'GET':
                response = self._session.get(self.api_url, params=params, timeout=self.timeout)
            else:
                response = self._session.post(self.api_url, data=params, timeout=self.timeout)
            
            # Handle 429 errors with exponential backoff
            if response.status_code == 429:
                if self.api_throttler:
                    self.api_throttler.report_429()
                logger.warning(f"Received 429 error, backing off...")
                # Retry once with increased delay
                if self.api_throttler:
                    self.api_throttler.wait_if_needed()
                response = self._session.get(self.api_url, params=params, timeout=self.timeout)
                if response.status_code == 429:
                    logger.error("Still getting 429 after backoff, giving up")
                    raise Exception("Rate limit exceeded after retry")
                else:
                    if self.api_throttler:
                        self.api_throttler.report_success()
            else:
                if self.api_throttler:
                    self.api_throttler.report_success()
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"Wikipedia API request failed: {e}")
            raise
    
    def page_exists(self, title: str) -> bool:
        """
        Check if a page exists on Wikipedia.
        
        Args:
            title: Page title (without namespace prefix unless needed).
            
        Returns:
            True if page exists, False otherwise.
        """
        if title in self._page_exists_cache:
            return self._page_exists_cache[title]
        
        if not self._session:
            return True  # Assume exists if no session
        
        try:
            params = {
                'action': 'query',
                'titles': title,
                'format': 'json',
                'formatversion': 2,
            }
            data = self._make_request(params)
            
            pages = data.get('query', {}).get('pages', [])
            if not pages:
                self._page_exists_cache[title] = False
                return False
            
            page = pages[0]
            exists = 'missing' not in page
            self._page_exists_cache[title] = exists
            return exists
            
        except Exception as e:
            logger.warning(f"Error checking page existence for {title}: {e}")
            # Assume exists to avoid false positives
            return True
    
    def category_exists(self, title: str) -> bool:
        """
        Check if a category exists on Wikipedia.
        
        Args:
            title: Category title (with or without 'Catégorie:' prefix).
            
        Returns:
            True if category exists, False otherwise.
        """
        # Normalize title
        if not title.lower().startswith('catégorie:') and not title.lower().startswith('category:'):
            title = f'Catégorie:{title}'
        
        if title in self._category_exists_cache:
            return self._category_exists_cache[title]
        
        if not self._session:
            return True  # Assume exists if no session
        
        try:
            params = {
                'action': 'query',
                'titles': title,
                'format': 'json',
                'formatversion': 2,
            }
            data = self._make_request(params)
            
            pages = data.get('query', {}).get('pages', [])
            if not pages:
                self._category_exists_cache[title] = False
                return False
            
            page = pages[0]
            exists = 'missing' not in page
            self._category_exists_cache[title] = exists
            return exists
            
        except Exception as e:
            logger.warning(f"Error checking category existence for {title}: {e}")
            return True
    
    def resolve_redirect(self, title: str) -> Optional[str]:
        """
        Resolve a redirect to its canonical target.
        
        Args:
            title: Page title that might be a redirect.
            
        Returns:
            Canonical target title if redirect, None if not a redirect or error.
        """
        if title in self._redirect_cache:
            return self._redirect_cache[title]
        
        if not self._session:
            return None
        
        try:
            params = {
                'action': 'query',
                'titles': title,
                'redirects': 1,
                'format': 'json',
                'formatversion': 2,
            }
            data = self._make_request(params)
            
            redirects = data.get('query', {}).get('redirects', [])
            if redirects:
                target = redirects[0].get('to')
                self._redirect_cache[title] = target
                return target
            
            # Not a redirect
            self._redirect_cache[title] = None
            return None
            
        except Exception as e:
            logger.warning(f"Error resolving redirect for {title}: {e}")
            self._redirect_cache[title] = None
            return None
    
    def get_page_metadata(self, title: str) -> Optional[PageMetadata]:
        """
        Get metadata about a page.
        
        Args:
            title: Page title.
            
        Returns:
            PageMetadata object or None if error.
        """
        if title in self._metadata_cache:
            return self._metadata_cache[title]
        
        if not self._session:
            return None
        
        try:
            params = {
                'action': 'query',
                'titles': title,
                'prop': 'info|redirects',
                'inprop': 'subjectid',
                'format': 'json',
                'formatversion': 2,
            }
            data = self._make_request(params)
            
            pages = data.get('query', {}).get('pages', [])
            if not pages:
                return None
            
            page = pages[0]
            
            # Check redirect
            redirect_target = None
            redirects = data.get('query', {}).get('redirects', [])
            if redirects:
                redirect_target = redirects[0].get('to')
            
            metadata = PageMetadata(
                title=page.get('title', title),
                pageid=page.get('pageid', 0),
                exists='missing' not in page,
                is_redirect=redirect_target is not None,
                redirect_target=redirect_target,
                last_revision_id=page.get('lastrevid'),
                last_revision_timestamp=page.get('touched'),
                length=page.get('length'),
            )
            
            self._metadata_cache[title] = metadata
            return metadata
            
        except Exception as e:
            logger.warning(f"Error getting metadata for {title}: {e}")
            return None
    
    def get_page_content(self, title: str, revision_id: Optional[int] = None) -> Optional[str]:
        """
        Get the wikitext content of a page.
        
        Args:
            title: Page title.
            revision_id: Optional specific revision ID.
            
        Returns:
            Wikitext content or None if error.
        """
        if not self._session:
            return None
        
        try:
            params = {
                'action': 'query',
                'titles': title,
                'prop': 'revisions',
                'rvprop': 'content',
                'rvslots': 'main',
                'format': 'json',
                'formatversion': 2,
            }
            if revision_id:
                params['revids'] = revision_id
            
            data = self._make_request(params)
            
            pages = data.get('query', {}).get('pages', [])
            if not pages:
                return None
            
            page = pages[0]
            
            # Check if page exists
            if 'missing' in page:
                return None
            
            # Get content
            revisions = page.get('revisions', [])
            if not revisions:
                return None
            
            content = revisions[0].get('slots', {}).get('main', {}).get('content', '')
            return content
            
        except Exception as e:
            logger.warning(f"Error getting content for {title}: {e}")
            return None
    
    def get_category_members(
        self,
        category_name: str,
        max_results: int = 500,
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get members of a category.
        
        Args:
            category_name: Category name (with or without 'Category:' prefix).
            max_results: Maximum number of results to return.
            recursive: Whether to include subcategories.
            
        Returns:
            List of member page data.
        """
        if not self._session:
            return []
        
        # Normalize category name
        if not category_name.lower().startswith('category:') and not category_name.lower().startswith('catégorie:'):
            category_name = f'Category:{category_name}'
        
        try:
            params = {
                'action': 'query',
                'list': 'categorymembers',
                'cmtitle': category_name,
                'cmlimit': max_results,
                'cmtype': 'page' if not recursive else 'page|subcat',
                'format': 'json',
                'formatversion': 2,
            }
            
            data = self._make_request(params)
            
            members = data.get('query', {}).get('categorymembers', [])
            return members
            
        except Exception as e:
            logger.warning(f"Error getting category members for {category_name}: {e}")
            return []
    
    def check_page_protection(self, titles: List[str]) -> Dict[str, bool]:
        """
        Check protection status for multiple pages.
        
        Args:
            titles: List of page titles to check.
            
        Returns:
            Dictionary mapping page titles to protection status (True if protected).
        """
        if not self._session or not titles:
            return {}
        
        try:
            # MediaWiki API accepts up to 50 titles per request
            batch_size = 50
            results = {}
            
            for i in range(0, len(titles), batch_size):
                batch = titles[i:i + batch_size]
                titles_param = '|'.join(batch)
                
                params = {
                    'action': 'query',
                    'prop': 'info',
                    'titles': titles_param,
                    'inprop': 'protection',
                    'format': 'json'
                }
                
                data = self._make_request(params)
                
                # Process results
                for page_id, page_info in data.get('query', {}).get('pages', {}).items():
                    if page_id == '-1':  # Invalid page
                        continue
                    title = page_info.get('title', '')
                    is_protected = bool(page_info.get('protection'))
                    results[title] = is_protected
            
            return results
            
        except Exception as e:
            logger.warning(f"Error checking page protection: {e}")
            return {}
    
    def edit_page(
        self,
        title: str,
        content: str,
        summary: str,
        token: str,
        minor: bool = False,
        bot: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Edit a page on Wikipedia.
        
        Args:
            title: Page title.
            content: New page content.
            summary: Edit summary.
            token: Edit token.
            minor: Whether this is a minor edit.
            bot: Whether this is a bot edit.
            
        Returns:
            API response data or None if error.
        """
        if not self._session:
            return None
        
        try:
            params = {
                'action': 'edit',
                'title': title,
                'text': content,
                'summary': summary,
                'token': token,
                'minor': 1 if minor else 0,
                'bot': 1 if bot else 0,
                'format': 'json',
                'formatversion': 2,
            }
            
            data = self._make_request(params, method='POST')
            return data
            
        except Exception as e:
            logger.warning(f"Error editing page {title}: {e}")
            return None


# Global client instance for shared use across the application
_global_wikipedia_client: Optional[WikipediaAPIClient] = None


def get_wikipedia_client(
    language: str = None,
    api_url: Optional[str] = None,
    session=None,
    timeout: float = None,
    user_agent: str = 'WikipediaMaintenanceTool/1.0',
    use_throttling: bool = True,
    force_new: bool = False
) -> WikipediaAPIClient:
    """
    Get or create the global Wikipedia API client instance.
    
    This ensures all Wikipedia API calls go through a single, throttled client.
    
    Args:
        language: Language code (e.g., 'fr', 'en'). If None, loads from config.
        api_url: Custom API URL (if None, uses standard Wikipedia API).
        session: Optional requests.Session for connection pooling.
        timeout: Request timeout in seconds. If None, loads from config.
        user_agent: User-Agent string for API requests.
        use_throttling: Whether to apply global throttling (default: True).
        force_new: If True, create a new instance instead of using the global one.
        
    Returns:
        Shared WikipediaAPIClient instance
    """
    global _global_wikipedia_client
    
    # Load config defaults if parameters not provided
    if language is None:
        try:
            from .config import load_config
            config = load_config()
            language = config.wikipedia.lang
        except Exception:
            language = 'fr'
            
    if timeout is None:
        try:
            from .config import load_config
            config = load_config()
            timeout = config.wikipedia.timeout
        except Exception:
            timeout = 10.0
    
    if force_new:
        client = WikipediaAPIClient(
            language=language,
            api_url=api_url,
            session=session,
            timeout=timeout,
            user_agent=user_agent,
            use_throttling=use_throttling
        )
        # Set throttler if requested (avoid circular import)
        if use_throttling:
            try:
                from .api_throttler import get_global_throttler
                client.set_throttler(get_global_throttler())
            except ImportError:
                logger.warning("Could not import api_throttler, throttling disabled")
        return client
    
    if _global_wikipedia_client is None:
        _global_wikipedia_client = WikipediaAPIClient(
            language=language,
            api_url=api_url,
            session=session,
            timeout=timeout,
            user_agent=user_agent,
            use_throttling=use_throttling
        )
        # Set throttler if requested (avoid circular import)
        if use_throttling:
            try:
                from .api_throttler import get_global_throttler
                _global_wikipedia_client.set_throttler(get_global_throttler())
            except ImportError:
                logger.warning("Could not import api_throttler, throttling disabled")
        logger.info("Created global Wikipedia API client")
    
    return _global_wikipedia_client


def reset_global_client():
    """Reset the global Wikipedia API client instance (mainly for testing)."""
    global _global_wikipedia_client
    _global_wikipedia_client = None
    logger.info("Reset global Wikipedia API client")
    
    def get_category_members(
        self,
        category: str,
        limit: int = 500,
        namespace: Optional[int] = None,
    ) -> List[str]:
        """
        Get members of a category.
        
        Args:
            category: Category title (with or without 'Catégorie:' prefix).
            limit: Maximum number of members to retrieve.
            namespace: Optional namespace filter (0=articles, 14=categories, etc.).
            
        Returns:
            List of page titles in the category.
        """
        # Normalize title
        if not category.lower().startswith('catégorie:') and not category.lower().startswith('category:'):
            category = f'Catégorie:{category}'
        
        if not self._session:
            return []
        
        members = []
        cmcontinue = None
        
        try:
            while len(members) < limit:
                params = {
                    'action': 'query',
                    'list': 'categorymembers',
                    'cmtitle': category,
                    'cmlimit': min(500, limit - len(members)),
                    'format': 'json',
                    'formatversion': 2,
                }
                if cmcontinue:
                    params['cmcontinue'] = cmcontinue
                if namespace is not None:
                    params['cmnamespace'] = namespace
                
                response = self._session.get(self.api_url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                for member in data.get('query', {}).get('categorymembers', []):
                    title = member.get('title', '')
                    if title:
                        members.append(title)
                
                cmcontinue = data.get('continue', {}).get('cmcontinue')
                if not cmcontinue:
                    break
            
            return members
            
        except Exception as e:
            logger.warning(f"Error getting category members for {category}: {e}")
            return members
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        self._page_exists_cache.clear()
        self._category_exists_cache.clear()
        self._redirect_cache.clear()
        self._metadata_cache.clear()
