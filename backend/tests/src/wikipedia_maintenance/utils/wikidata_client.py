"""
Wikidata API client for retrieving entity data and official websites.

This client provides methods to:
- Get entity data by QID
- Retrieve official website URLs (P856)
- Batch query multiple entities
"""

import logging
from typing import List, Optional, Dict, Any, Set
from dataclasses import dataclass, field
import requests

logger = logging.getLogger(__name__)


@dataclass
class WikidataEntity:
    """Represents a Wikidata entity with its official websites."""
    qid: str
    label: Optional[str] = None
    description: Optional[str] = None
    official_websites: List[str] = field(default_factory=list)


class WikidataClient:
    """
    Client for interacting with the Wikidata API.

    Uses the existing throttling and retry patterns from WikipediaAPIClient.
    """

    WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
    WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        timeout: float = 10.0,
        user_agent: Optional[str] = None,
        throttler=None,
    ):
        """
        Initialize the Wikidata client.

        Args:
            session: Optional requests.Session for connection pooling
            timeout: Request timeout in seconds
            user_agent: User-Agent string for API requests
            throttler: Optional APIThrottler instance for rate limiting
        """
        self.timeout = timeout

        # Use bot identity system if user_agent not provided
        if user_agent is None:
            try:
                from .bot_identity import get_user_agent
                self.user_agent = get_user_agent(purpose="Wikidata API")
            except ImportError:
                self.user_agent = 'OviX/1.0 (Wikidata client)'
        else:
            self.user_agent = user_agent

        self.throttler = throttler
        self._session = session

        # Initialize session if not provided
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({'User-Agent': self.user_agent})

    def _make_request(self, params: Dict[str, Any], method: str = 'GET', api_url: Optional[str] = None) -> Any:
        """
        Make a throttled request to a MediaWiki-style API, with 429 backoff and retry.

        Args:
            params: API parameters
            method: HTTP method (GET or POST)
            api_url: Override target URL (defaults to the Wikidata API)

        Returns:
            JSON response data

        Raises:
            Exception: If request fails
        """
        if not self._session:
            raise Exception("No session available")

        url = api_url or self.WIKIDATA_API_URL

        # Apply throttling before request if throttler is available
        if self.throttler:
            self.throttler.wait_if_needed()

        try:
            if method == 'GET':
                response = self._session.get(url, params=params, timeout=self.timeout)
            else:
                response = self._session.post(url, data=params, timeout=self.timeout)

            # Handle 429 errors with exponential backoff
            if response.status_code == 429:
                if self.throttler:
                    self.throttler.report_429()
                logger.warning("Received 429 error from %s, backing off...", url)
                # Retry once with increased delay
                if self.throttler:
                    self.throttler.wait_if_needed()
                if method == 'GET':
                    response = self._session.get(url, params=params, timeout=self.timeout)
                else:
                    response = self._session.post(url, data=params, timeout=self.timeout)
                if response.status_code == 429:
                    logger.error("Still getting 429 from %s after backoff, giving up", url)
                    raise Exception("Rate limit exceeded after retry")
                else:
                    if self.throttler:
                        self.throttler.report_success()
            else:
                if self.throttler:
                    self.throttler.report_success()

            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"API request to {url} failed: {e}")
            raise

    @staticmethod
    def _pick_localized_value(values: Dict[str, Dict[str, Any]]) -> Optional[str]:
        """
        Pick the best available localized string from a labels/descriptions dict,
        preferring French, then English, then the first available value.

        Correctly handles the case where no localization exists at all.
        """
        if not values:
            return None

        fr = values.get('fr', {}).get('value')
        if fr:
            return fr

        en = values.get('en', {}).get('value')
        if en:
            return en

        first = next(iter(values.values()), None)
        if first:
            return first.get('value')

        return None

    @staticmethod
    def _extract_official_websites(entity_data: Dict[str, Any], qid: str) -> List[str]:
        """Extract P856 (official website) string values from an entity's claims."""
        claims = entity_data.get('claims', {})
        p856_claims = claims.get('P856', [])

        official_websites: List[str] = []
        for claim in p856_claims:
            try:
                mainsnak = claim.get('mainsnak', {})
                datavalue = mainsnak.get('datavalue', {})
                if datavalue.get('type') == 'string':
                    url = datavalue.get('value')
                    if url:
                        official_websites.append(url)
            except (KeyError, AttributeError) as e:
                logger.debug(f"Error extracting P856 value from {qid}: {e}")

        return official_websites

    def _entity_from_data(self, qid: str, entity_data: Dict[str, Any]) -> WikidataEntity:
        """Build a WikidataEntity from a raw wbgetentities entity payload."""
        labels = entity_data.get('labels', {})
        descriptions = entity_data.get('descriptions', {})

        return WikidataEntity(
            qid=qid,
            label=self._pick_localized_value(labels),
            description=self._pick_localized_value(descriptions),
            official_websites=self._extract_official_websites(entity_data, qid),
        )

    def get_entity(self, qid: str) -> Optional[WikidataEntity]:
        """
        Get entity data by QID.

        Args:
            qid: Wikidata entity ID (e.g., "Q123")

        Returns:
            WikidataEntity or None if not found
        """
        if not qid or not qid.strip():
            logger.warning("get_entity called with empty QID")
            return None

        try:
            params = {
                'action': 'wbgetentities',
                'ids': qid,
                'props': 'labels|descriptions|claims',
                'format': 'json',
            }

            data = self._make_request(params)

            entities = data.get('entities', {})
            if qid not in entities:
                logger.warning(f"Entity {qid} not found")
                return None

            entity_data = entities[qid]

            # An entity that was deleted/merged comes back with a 'missing' marker
            if 'missing' in entity_data:
                logger.warning(f"Entity {qid} is marked missing")
                return None

            return self._entity_from_data(qid, entity_data)

        except Exception as e:
            logger.error(f"Error getting entity {qid}: {e}")
            return None

    def get_entities_batch(self, qids: List[str]) -> Dict[str, Optional[WikidataEntity]]:
        """
        Get multiple entities in a single batch request.

        Args:
            qids: List of Wikidata entity IDs

        Returns:
            Dictionary mapping QIDs to WikidataEntity objects
        """
        if not qids:
            return {}

        # Deduplicate while preserving order, and drop empty/blank ids
        seen: Set[str] = set()
        clean_qids: List[str] = []
        for qid in qids:
            if qid and qid.strip() and qid not in seen:
                seen.add(qid)
                clean_qids.append(qid)

        if not clean_qids:
            return {}

        # Wikidata API allows up to 50 entities per request
        batch_size = 50
        results: Dict[str, Optional[WikidataEntity]] = {}

        for i in range(0, len(clean_qids), batch_size):
            batch = clean_qids[i:i + batch_size]

            try:
                params = {
                    'action': 'wbgetentities',
                    'ids': '|'.join(batch),
                    'props': 'labels|descriptions|claims',
                    'format': 'json',
                }

                data = self._make_request(params)
                entities = data.get('entities', {})

                for qid in batch:
                    entity_data = entities.get(qid)
                    if entity_data and 'missing' not in entity_data:
                        results[qid] = self._entity_from_data(qid, entity_data)
                    else:
                        results[qid] = None

            except Exception as e:
                logger.error(f"Error getting batch entities {batch}: {e}")
                # Mark all in batch as failed
                for qid in batch:
                    results[qid] = None

        # Include original (possibly duplicate) query keys in the result too
        for qid in qids:
            if qid not in results:
                results[qid] = results.get(qid)

        return results

    def get_qid_from_page_title(self, title: str, wiki_lang: str = 'fr') -> Optional[str]:
        """
        Get the Wikidata QID for a Wikipedia page title.

        Args:
            title: Wikipedia page title
            wiki_lang: Wikipedia language code (default: 'fr')

        Returns:
            QID string or None if not found
        """
        if not title or not title.strip():
            logger.warning("get_qid_from_page_title called with empty title")
            return None

        try:
            params = {
                'action': 'query',
                'prop': 'pageprops',
                'ppprop': 'wikibase_item',
                'titles': title,
                'format': 'json',
            }

            api_url = f"https://{wiki_lang}.wikipedia.org/w/api.php"

            # Routed through _make_request so it benefits from the same
            # 429 backoff/retry handling as every other call in this client.
            data = self._make_request(params, method='GET', api_url=api_url)

            pages = data.get('query', {}).get('pages', {})

            for page_id, page_data in pages.items():
                if page_id == '-1':  # Page doesn't exist
                    continue

                pageprops = page_data.get('pageprops', {})
                qid = pageprops.get('wikibase_item')

                if qid:
                    return qid

            return None

        except Exception as e:
            logger.error(f"Error getting QID for {title}: {e}")
            return None