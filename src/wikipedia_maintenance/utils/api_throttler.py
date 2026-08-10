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
    
    def __init__(self, min_delay: float = 11.0, max_requests_per_minute: int = 10):
        """
        Initialize API throttler.
        
        Args:
            min_delay: Default delay between consecutive requests in seconds (will be randomized)
            max_requests_per_minute: Maximum number of requests allowed per minute (10-15)
        """
        self.min_delay = min_delay
        self.min_delay_min = 8.0
        self.min_delay_max = 15.0
        self.random_delay = True
        self.max_requests_per_minute = max_requests_per_minute
        self.max_requests_per_minute_min = 10
        self.max_requests_per_minute_max = 15
        self.last_request_time = 0.0
        self.request_timestamps = []
        self.lock = threading.Lock()
        self.consecutive_429s = 0  # Track backoff state for exponential backoff
        
        # Load configuration from config.yaml if available
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
            if len(self.request_timestamps) >= effective_max_requests:
                # Wait until the oldest request is more than 1 minute old
                oldest_timestamp = min(self.request_timestamps)
                wait_time = 60.0 - (current_time - oldest_timestamp)
                if wait_time > 0:
                    logger.info(f"Rate limit reached ({effective_max_requests}/min), waiting {wait_time:.2f}s")
                    time.sleep(wait_time)
                    current_time = time.time()
            
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
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < effective_delay:
                wait_time = effective_delay - time_since_last_request
                if wait_time > 0:
                    time.sleep(wait_time)
                    current_time = time.time()
            
            # Record this request
            self.last_request_time = current_time
            self.request_timestamps.append(current_time)
    
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
