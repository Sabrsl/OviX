"""
Centralized retry logic for consistent error handling across the application.

This module provides a unified retry mechanism with:
- Exponential backoff
- Maximum retry limits
- Configurable retry conditions
- Consistent error handling
- Telemetry and logging
"""

import logging
import time
import random
from typing import Callable, Type, Optional, Any, List, Tuple
from functools import wraps
from dataclasses import dataclass
from enum import Enum
from urllib.error import URLError


class RateLimitError(Exception):
    """Exception raised when rate limit is exceeded."""
    pass

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategies for different scenarios."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    retry_on_status_codes: Optional[List[int]] = None
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be non-negative")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")


class RetryHandler:
    """
    Centralized retry handler with configurable strategies.
    
    Provides consistent retry logic across all modules with:
    - Multiple retry strategies
    - Configurable backoff
    - Exception filtering
    - HTTP status code filtering
    - Detailed logging
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize the retry handler.
        
        Args:
            config: Retry configuration (uses defaults if not provided)
        """
        self.config = config or RetryConfig()
        
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry attempt.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        if self.config.strategy == RetryStrategy.IMMEDIATE:
            return 0.0
        
        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * (attempt + 1)
        else:  # EXPONENTIAL_BACKOFF
            delay = self.config.base_delay * (self.config.backoff_multiplier ** attempt)
        
        # Apply max delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to avoid thundering herd
        if self.config.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay
    
    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Determine if operation should be retried based on exception.
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.config.max_attempts - 1:
            return False
        
        # Check if exception type is in retry list
        for retry_exception in self.config.retry_on_exceptions:
            if isinstance(exception, retry_exception):
                return True
        
        return False
    
    def should_retry_status_code(self, status_code: int, attempt: int) -> bool:
        """
        Determine if HTTP request should be retried based on status code.
        
        Args:
            status_code: HTTP status code
            attempt: Current attempt number
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.config.max_attempts - 1:
            return False
        
        if self.config.retry_on_status_codes is None:
            return False
        
        return status_code in self.config.retry_on_status_codes
    
    def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function return value
            
        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                return func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                
                if not self.should_retry(e, attempt):
                    logger.error(f"Exception {type(e).__name__} not configured for retry: {e}")
                    raise
                
                delay = self.calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_attempts} failed with {type(e).__name__}: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                time.sleep(delay)
        
        # All retries exhausted
        logger.error(f"All {self.config.max_attempts} retry attempts exhausted")
        raise last_exception
    
    def execute_with_retry_on_result(
        self,
        func: Callable,
        should_retry_result: Callable[[Any], bool],
        *args,
        **kwargs
    ) -> Any:
        """
        Like execute_with_retry, but also retries based on the return value
        (not just exceptions) — e.g. an HTTP result object with a status code
        that should trigger a retry without raising.

        Args:
            func: Function to execute
            should_retry_result: Predicate called on the return value; True
                means retry (subject to max_attempts), False means accept
                the result as final.
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            The last result obtained (whether or not it satisfied
            should_retry_result on the final attempt).

        Raises:
            The last exception if func raised on every attempt and none
            were retryable.
        """
        last_result = None

        for attempt in range(self.config.max_attempts):
            try:
                result = func(*args, **kwargs)
            except Exception as e:
                if not self.should_retry(e, attempt):
                    logger.error(f"Exception {type(e).__name__} not configured for retry: {e}")
                    raise
                delay = self.calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_attempts} failed with {type(e).__name__}: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
                continue

            last_result = result

            if attempt >= self.config.max_attempts - 1 or not should_retry_result(result):
                return result

            delay = self.calculate_delay(attempt)
            logger.warning(
                f"Attempt {attempt + 1}/{self.config.max_attempts} returned a retryable result. "
                f"Retrying in {delay:.2f}s..."
            )
            time.sleep(delay)

        return last_result


def retry_with_config(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    backoff_multiplier: float = 2.0,
    jitter: bool = True,
    retry_on_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    retry_on_status_codes: Optional[List[int]] = None
):
    """
    Decorator for retry logic with custom configuration.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        strategy: Retry strategy to use
        backoff_multiplier: Multiplier for exponential backoff
        jitter: Whether to add random jitter to delays
        retry_on_exceptions: Exception types to retry on
        retry_on_status_codes: HTTP status codes to retry on
        
    Returns:
        Decorator function
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        strategy=strategy,
        backoff_multiplier=backoff_multiplier,
        jitter=jitter,
        retry_on_exceptions=retry_on_exceptions,
        retry_on_status_codes=retry_on_status_codes
    )
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            handler = RetryHandler(config)
            return handler.execute_with_retry(func, *args, **kwargs)
        return wrapper
    
    return decorator


# Predefined retry configurations for common scenarios
class RetryPresets:
    """Predefined retry configurations for common use cases."""
    
    @staticmethod
    def wikipedia_api() -> RetryConfig:
        """Retry configuration for Wikipedia API calls."""
        return RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retry_on_exceptions=(
                ConnectionError,
                TimeoutError,
                URLError,
            ),
            retry_on_status_codes=[429, 500, 502, 503, 504]
        )
    
    @staticmethod
    def gemini_api() -> RetryConfig:
        """Retry configuration for Gemini AI API calls."""
        return RetryConfig(
            max_attempts=2,
            base_delay=2.0,
            max_delay=5.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retry_on_exceptions=(
                ConnectionError,
                TimeoutError,
                URLError,
            ),
            retry_on_status_codes=[429, 500, 503]
        )
    
    @staticmethod
    def external_urls() -> RetryConfig:
        """Retry configuration for external URL checks."""
        return RetryConfig(
            max_attempts=2,
            base_delay=1.0,
            max_delay=3.0,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            retry_on_exceptions=(
                ConnectionError,
                TimeoutError,
                URLError,
            ),
            retry_on_status_codes=[429, 500, 502, 503, 504]
        )
    
    @staticmethod
    def database_operations() -> RetryConfig:
        """Retry configuration for database operations."""
        return RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            max_delay=2.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            retry_on_exceptions=(
                ConnectionError,
                TimeoutError,
            )
        )


def get_retry_handler(preset: str) -> RetryHandler:
    """
    Get a retry handler with a predefined configuration.
    
    Args:
        preset: Name of the preset ('wikipedia_api', 'gemini_api', 'external_urls', 'database_operations')
        
    Returns:
        Configured RetryHandler instance
    """
    presets = {
        'wikipedia_api': RetryPresets.wikipedia_api(),
        'gemini_api': RetryPresets.gemini_api(),
        'external_urls': RetryPresets.external_urls(),
        'database_operations': RetryPresets.database_operations()
    }
    
    if preset not in presets:
        raise ValueError(f"Unknown preset: {preset}. Available: {list(presets.keys())}")
    
    return RetryHandler(presets[preset])


# Legacy function names for backward compatibility
def get_wikipedia_retry_handler() -> RetryHandler:
    """Legacy function name for backward compatibility."""
    return get_retry_handler('wikipedia_api')


def get_gemini_retry_handler() -> RetryHandler:
    """Legacy function name for backward compatibility."""
    return get_retry_handler('gemini_api')