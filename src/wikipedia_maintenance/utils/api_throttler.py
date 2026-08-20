"""
API Throttler Module

Provides centralized rate limiting for Wikipedia API calls to prevent 429 errors.
Implements a token bucket algorithm with configurable rate limits and minimum delays.
"""

import time
import threading
import logging
from typing import Optional
from pathlib import Path
import yaml
import random

logger = logging.getLogger(__name__)


class APIThrottler:
    """
    Rate limiter for API calls to prevent 429 errors.
    
    Implements a token bucket algorithm with configurable rate limits
    and minimum delay between requests. Thread-safe for concurrent use.
    """
    
    def __init__(self, min_delay: float = 11.0, max_requests_per_minute: int = 10, load_from_config: bool = True):
        """
        Initialize the API throttler.
        
        Args:
            min_delay: Minimum delay between requests in seconds
            max_requests_per_minute: Maximum requests per minute
            load_from_config: Whether to load configuration from config.yaml (default True)
        """
        self.min_delay = min_delay
        self.max_requests_per_minute = max_requests_per_minute
        self.min_delay_min = 0.0
        self.min_delay_max = 60.0
        self.max_requests_per_minute_min = 1
        self.max_requests_per_minute_max = 60
        self.random_delay = False
        self.consecutive_429s = 0
        
        self.last_request_time = 0.0
        self.request_timestamps = []
        self.lock = threading.Lock()
        
        if load_from_config:
            self._load_config()
    
    def _load_config(self) -> None:
        """Load throttling settings from config.yaml."""
        try:
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and 'api_throttling' in config:
                        throttling_config = config['api_throttling']
                        if 'min_delay' in throttling_config:
                            self.min_delay = throttling_config['min_delay']
                        if 'min_delay_min' in throttling_config:
                            self.min_delay_min = float(throttling_config['min_delay_min'])
                        if 'min_delay_max' in throttling_config:
                            self.min_delay_max = float(throttling_config['min_delay_max'])
                        if 'random_delay' in throttling_config:
                            self.random_delay = throttling_config['random_delay']
                        if 'max_requests_per_minute' in throttling_config:
                            self.max_requests_per_minute = throttling_config['max_requests_per_minute']
                        if 'max_requests_per_minute_min' in throttling_config:
                            self.max_requests_per_minute_min = throttling_config['max_requests_per_minute_min']
                        if 'max_requests_per_minute_max' in throttling_config:
                            self.max_requests_per_minute_max = throttling_config['max_requests_per_minute_max']
                        logger.info(f"Loaded throttling config: min_delay={self.min_delay}s, min_delay_min={self.min_delay_min}s, min_delay_max={self.min_delay_max}s, random_delay={self.random_delay}, max_requests_per_minute={self.max_requests_per_minute}, max_requests_per_minute_min={self.max_requests_per_minute_min}, max_requests_per_minute_max={self.max_requests_per_minute_max}")
        except Exception as e:
            logger.warning(f"Failed to load throttling config: {e}")
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limits."""
        wait_time = 0.0
        
        with self.lock:
            current_time = time.time()
            
            # Clean old timestamps (older than 1 minute)
            self.request_timestamps = [
                ts for ts in self.request_timestamps 
                if current_time - ts < 60.0
            ]
            
            # Check if we've exceeded the rate limit
            # Ensure max_requests_per_minute is within configured range
            effective_max_requests = max(self.max_requests_per_minute_min, 
                                       min(self.max_requests_per_minute, self.max_requests_per_minute_max))
            rate_wait = 0.0
            if len(self.request_timestamps) >= effective_max_requests:
                # Wait until the oldest request is more than 1 minute old
                oldest_timestamp = min(self.request_timestamps)
                rate_wait = max(0.0, 60.0 - (current_time - oldest_timestamp))
                if rate_wait > 0:
                    logger.info(f"Rate limit reached ({effective_max_requests}/min), waiting {rate_wait:.2f}s")
            
            # Base minimum delay (random if configured)
            if self.random_delay:
                effective_delay = random.uniform(self.min_delay_min, self.min_delay_max)
                logger.debug(f"Using random delay: {effective_delay:.2f}s (range: {self.min_delay_min}s-{self.min_delay_max}s)")
            else:
                effective_delay = self.min_delay
            
            # Exponential backoff on top of min_delay if we've been hitting 429s
            if self.consecutive_429s > 0:
                effective_delay = effective_delay * (2 ** min(self.consecutive_429s, 5))
                logger.debug(f"Applying exponential backoff: {effective_delay:.2f}s (consecutive_429s={self.consecutive_429s})")
            
            # Check minimum delay between requests
            delay_wait = max(0.0, effective_delay - (current_time - self.last_request_time))
            
            # Take the maximum wait time between rate limit and delay
            wait_time = max(rate_wait, delay_wait)
            
            # Record the timestamp immediately (based on current time, not projected future)
            # This allows other threads to see the slot is taken without creating artificial cascade
            self.last_request_time = current_time
            self.request_timestamps.append(current_time)
        
        # Sleep OUTSIDE the lock to allow other threads to proceed with their own wait calculations
        if wait_time > 0:
            time.sleep(wait_time)
    
    def report_429(self) -> None:
        """
        Call this whenever a request returns HTTP 429.
        Increases backoff delay for subsequent calls until reset by report_success().
        """
        with self.lock:
            self.consecutive_429s += 1
            logger.warning(f"429 reported, consecutive count={self.consecutive_429s} — backing off")
    
    def report_success(self) -> None:
        """Call this after a successful request to reset backoff state."""
        with self.lock:
            if self.consecutive_429s > 0:
                logger.info("Request succeeded, resetting 429 backoff")
            self.consecutive_429s = 0
    
    def get_request_count(self) -> int:
        """Get number of requests made in the last minute."""
        with self.lock:
            current_time = time.time()
            self.request_timestamps = [
                ts for ts in self.request_timestamps 
                if current_time - ts < 60.0
            ]
            return len(self.request_timestamps)
    
    def get_stats(self) -> dict:
        """Get current throttling statistics."""
        with self.lock:
            current_time = time.time()
            self.request_timestamps = [
                ts for ts in self.request_timestamps 
                if current_time - ts < 60.0
            ]
            return {
                'requests_last_minute': len(self.request_timestamps),
                'max_requests_per_minute': self.max_requests_per_minute,
                'max_requests_per_minute_min': self.max_requests_per_minute_min,
                'max_requests_per_minute_max': self.max_requests_per_minute_max,
                'min_delay': self.min_delay,
                'min_delay_min': self.min_delay_min,
                'min_delay_max': self.min_delay_max,
                'random_delay': self.random_delay,
                'time_since_last_request': current_time - self.last_request_time,
                'consecutive_429s': self.consecutive_429s
            }


# Global throttler instance for shared use across the application
_global_throttler: Optional[APIThrottler] = None


def get_global_throttler() -> APIThrottler:
    """
    Get or create the global API throttler instance.
    
    Returns:
        Shared APIThrottler instance
    """
    global _global_throttler
    if _global_throttler is None:
        _global_throttler = APIThrottler()
    return _global_throttler


def reset_global_throttler() -> None:
    """Reset the global throttler instance (useful for testing)."""
    global _global_throttler
    _global_throttler = None


# Separate throttler for external link checks (more aggressive limits for parallelism)
_link_check_throttler: Optional[APIThrottler] = None


def get_link_check_throttler() -> APIThrottler:
    """
    Get or create the throttler for external link checks.
    
    This throttler uses more aggressive limits suitable for parallel
    link checking operations (higher rate limit, lower delay).
    
    Returns:
        Shared APIThrottler instance for link checks
    """
    global _link_check_throttler
    if _link_check_throttler is None:
        # More aggressive limits: 30 req/min instead of 10, 2s delay instead of 11s
        # load_from_config=False to avoid being overridden by config.yaml global settings
        _link_check_throttler = APIThrottler(min_delay=2.0, max_requests_per_minute=30, load_from_config=False)
    return _link_check_throttler


def reset_link_check_throttler() -> None:
    """Reset the link check throttler instance (useful for testing)."""
    global _link_check_throttler
    _link_check_throttler = None
