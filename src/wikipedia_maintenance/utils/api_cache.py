"""
Wikipedia API cache system for article list retrieval.

This module provides a caching mechanism to reduce unnecessary API calls to Wikipedia
when retrieving article lists, improving performance and reducing API load.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class WikipediaAPICache:
    """
    Cache for Wikipedia API responses during article list retrieval.
    
    Caches only article list retrieval calls, not analysis, corrections, or publications.
    """
    
    def __init__(self, cache_dir: str = "data/api_cache", ttl_minutes: int = 30):
        """
        Initialize the API cache.
        
        Args:
            cache_dir: Directory to store cache files
            ttl_minutes: Time-to-live for cache entries in minutes
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(minutes=ttl_minutes)
        
        # Statistics
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls_avoided': 0,
            'total_time_saved_ms': 0
        }
        
        logger.info(f"WikipediaAPICache initialized: dir={cache_dir}, ttl={ttl_minutes}min")
    
    def _generate_cache_key(self, params: Dict[str, Any]) -> str:
        """
        Generate a unique cache key from request parameters.
        
        Args:
            params: Dictionary of request parameters
            
        Returns:
            SHA256 hash of the parameters as cache key
        """
        # Convert params to a consistent string representation
        params_str = json.dumps(params, sort_keys=True)
        return hashlib.sha256(params_str.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the file path for a cache entry."""
        return self.cache_dir / f"{cache_key}.json"
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """
        Check if a cache entry is still valid based on TTL.
        
        Args:
            cache_entry: Cache entry dictionary
            
        Returns:
            True if cache is still valid, False otherwise
        """
        cached_time = datetime.fromisoformat(cache_entry['timestamp'])
        return datetime.now() - cached_time < self.ttl
    
    def get(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached response if available and valid.
        
        Args:
            params: Request parameters
            
        Returns:
            Cached response if valid, None otherwise
        """
        cache_key = self._generate_cache_key(params)
        cache_file = self._get_cache_file_path(cache_key)
        
        if not cache_file.exists():
            self.stats['cache_misses'] += 1
            logger.debug(f"Cache miss: {cache_key}")
            return None
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_entry = json.load(f)
            
            if not self._is_cache_valid(cache_entry):
                logger.debug(f"Cache expired: {cache_key}")
                self.stats['cache_misses'] += 1
                # Delete expired cache file
                cache_file.unlink()
                return None
            
            self.stats['cache_hits'] += 1
            self.stats['api_calls_avoided'] += 1
            
            # Calculate time saved (estimated)
            cached_time = datetime.fromisoformat(cache_entry['timestamp'])
            time_saved = (datetime.now() - cached_time).total_seconds() * 1000
            self.stats['total_time_saved_ms'] += time_saved
            
            logger.info(f"Cache hit: {cache_key} (saved {time_saved/1000:.1f}s)")
            return cache_entry['response']
            
        except Exception as e:
            logger.warning(f"Error reading cache: {e}")
            self.stats['cache_misses'] += 1
            return None
    
    def set(self, params: Dict[str, Any], response: Any) -> None:
        """
        Store a response in the cache.
        
        Args:
            params: Request parameters
            response: Response to cache
        """
        cache_key = self._generate_cache_key(params)
        cache_file = self._get_cache_file_path(cache_key)
        
        cache_entry = {
            'timestamp': datetime.now().isoformat(),
            'params': params,
            'response': response
        }
        
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_entry, f, indent=2, default=str)
            logger.debug(f"Cached response: {cache_key}")
        except Exception as e:
            logger.warning(f"Error writing cache: {e}")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except Exception as e:
                logger.warning(f"Error deleting cache file {cache_file}: {e}")
        
        logger.info("Cache cleared")
    
    def clear_expired(self) -> int:
        """
        Clear only expired cache entries.
        
        Returns:
            Number of entries cleared
        """
        cleared = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_entry = json.load(f)
                
                if not self._is_cache_valid(cache_entry):
                    cache_file.unlink()
                    cleared += 1
            except Exception as e:
                logger.warning(f"Error checking cache file {cache_file}: {e}")
        
        logger.info(f"Cleared {cleared} expired cache entries")
        return cleared
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.stats,
            'total_requests': total_requests,
            'hit_rate_percent': round(hit_rate, 2),
            'time_saved_seconds': round(self.stats['total_time_saved_ms'] / 1000, 2)
        }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'api_calls_avoided': 0,
            'total_time_saved_ms': 0
        }
        logger.info("Cache statistics reset")


# Global cache instance
_global_cache: Optional[WikipediaAPICache] = None


def get_cache(ttl_minutes: int = 30) -> WikipediaAPICache:
    """
    Get or create the global cache instance.
    
    Args:
        ttl_minutes: Time-to-live for cache entries
        
    Returns:
        Global WikipediaAPICache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = WikipediaAPICache(ttl_minutes=ttl_minutes)
    return _global_cache


def reset_global_cache() -> None:
    """Reset the global cache instance."""
    global _global_cache
    _global_cache = None
