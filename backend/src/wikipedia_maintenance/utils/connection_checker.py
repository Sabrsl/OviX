"""
Connection checker for network availability detection.

Provides utilities to check network connectivity and detect
when connections are restored after interruptions.
"""

import logging
import socket
import urllib.request
import urllib.error
from typing import Optional, Callable
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)


class ConnectionChecker:
    """Checks network connectivity to various services."""
    
    def __init__(self, timeout: float = 5.0):
        """
        Initialize connection checker.
        
        Args:
            timeout: Timeout for connection checks in seconds
        """
        self.timeout = timeout
        self._last_check_time: Optional[datetime] = None
        self._last_check_result: Optional[bool] = None
    
    def check_dns(self, hostname: str = "fr.wikipedia.org") -> bool:
        """
        Check if DNS resolution works.
        
        Args:
            hostname: Hostname to resolve
            
        Returns:
            True if DNS resolution succeeds
        """
        try:
            socket.gethostbyname(hostname)
            return True
        except socket.gaierror:
            return False
        except Exception as e:
            logger.warning(f"DNS check failed: {e}")
            return False
    
    def check_http(self, url: str = "https://www.google.com") -> bool:
        """
        Check if HTTP connection works.
        
        Args:
            url: URL to check (using Google as more reliable target)
            
        Returns:
            True if HTTP connection succeeds
        """
        try:
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status in [200, 301, 302, 303, 307, 308]  # Accept redirects
        except urllib.error.URLError:
            return False
        except Exception as e:
            logger.warning(f"HTTP check failed: {e}")
            return False
    
    def check_wikipedia_api(self, lang: str = "fr") -> bool:
        """
        Check if Wikipedia API is accessible.
        
        Args:
            lang: Wikipedia language code
            
        Returns:
            True if Wikipedia API is accessible
        """
        url = f"https://{lang}.wikipedia.org/w/api.php?action=query&meta=siteinfo&format=json"
        try:
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = response.read().decode('utf-8')
                return '"query"' in data
        except Exception as e:
            logger.warning(f"Wikipedia API check failed: {e}")
            return False
    
    def check_all(self) -> dict:
        """
        Perform all connection checks.
        
        Returns:
            Dictionary with check results
        """
        results = {
            'dns': self.check_dns(),
            'http': self.check_http(),
            'wikipedia_api': self.check_wikipedia_api()
        }
        
        self._last_check_time = datetime.now()
        # Consider connection good if DNS and at least one HTTP check passes
        self._last_check_result = results['dns'] and (results['http'] or results['wikipedia_api'])
        
        logger.info(f"Connection check results: {results}")
        return results
    
    def is_connected(self) -> bool:
        """
        Quick check if connection is available.
        
        Returns:
            True if connection appears available
        """
        if self._last_check_result is not None:
            # Use cached result if recent (within 30 seconds)
            if self._last_check_time and (datetime.now() - self._last_check_time).total_seconds() < 30:
                return self._last_check_result
        
        # Perform fresh check
        results = self.check_all()
        return all(results.values())
    
    async def wait_for_connection(
        self,
        check_interval: float = 10.0,
        max_wait: float = 300.0,
        on_connection_restored: Optional[Callable] = None
    ) -> bool:
        """
        Wait for connection to be restored.
        
        Args:
            check_interval: Interval between checks in seconds
            max_wait: Maximum time to wait in seconds
            on_connection_restored: Callback when connection is restored
            
        Returns:
            True if connection was restored, False if timeout
        """
        logger.info("Waiting for connection to be restored...")
        start_time = datetime.now()
        
        while True:
            if self.is_connected():
                logger.info("Connection restored!")
                if on_connection_restored:
                    on_connection_restored()
                return True
            
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed >= max_wait:
                logger.warning(f"Connection not restored after {max_wait} seconds")
                return False
            
            logger.info(f"Connection still down, waiting {check_interval} seconds...")
            await asyncio.sleep(check_interval)


def get_connection_checker(timeout: float = 5.0) -> ConnectionChecker:
    """
    Get or create connection checker instance.
    
    Args:
        timeout: Timeout for connection checks
        
    Returns:
        ConnectionChecker instance
    """
    return ConnectionChecker(timeout)


async def check_connection_with_retry(
    operation: Callable,
    connection_checker: Optional[ConnectionChecker] = None,
    max_retries: int = 3,
    retry_delay: float = 5.0
):
    """
    Execute operation with connection checking and retry.
    
    Args:
        operation: Operation to execute
        connection_checker: Connection checker instance
        max_retries: Maximum number of retries
        retry_delay: Delay between retries
        
    Returns:
        Operation result
        
    Raises:
        Exception: If operation fails after all retries
    """
    if connection_checker is None:
        connection_checker = get_connection_checker()
    
    last_error = None
    
    for attempt in range(max_retries):
        # Check connection before attempt
        if not connection_checker.is_connected():
            logger.warning(f"Connection down, waiting before attempt {attempt + 1}")
            await connection_checker.wait_for_connection(check_interval=retry_delay, max_wait=60.0)
        
        try:
            return await operation()
        except Exception as e:
            last_error = e
            logger.warning(f"Operation failed (attempt {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                # Wait for connection and retry
                await connection_checker.wait_for_connection(check_interval=retry_delay, max_wait=60.0)
    
    raise last_error or RuntimeError("Operation failed after retries")
