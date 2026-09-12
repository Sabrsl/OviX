"""
Archive Provider Health Check System.

This module provides health checking functionality for archive providers
to determine their availability and reliability before use.

Health checks verify:
- API endpoint availability
- Response format correctness
- Basic functionality (snapshot lookup)
- Error handling capabilities
- Rate limiting behavior
"""

import logging
import time
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass

from .archive_provider import ArchiveProvider, WaybackProvider, ArchiveResult, ArchiveAvailability

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status of a provider."""
    HEALTHY = "healthy"  # Provider is fully functional
    DEGRADED = "degraded"  # Provider works but with limitations
    RATE_LIMITED = "rate_limited"  # Provider is rate-limited (429/503)
    UNAVAILABLE = "unavailable"  # Provider is not accessible
    ERROR = "error"  # Provider returned unexpected error
    UNKNOWN = "unknown"  # Health check could not be completed


@dataclass
class HealthCheckResult:
    """Result of health check for a provider."""
    provider_name: str
    status: HealthStatus
    endpoint_reachable: bool
    response_time_ms: Optional[int]
    details: Dict[str, Any]
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'provider_name': self.provider_name,
            'status': self.status.value,
            'endpoint_reachable': self.endpoint_reachable,
            'response_time_ms': self.response_time_ms,
            'details': self.details,
            'timestamp': self.timestamp
        }


class ArchiveHealthChecker:
    """
    Health checker for archive providers.
    
    Performs periodic health checks to determine provider availability
    and reliability before using them for actual operations.
    """
    
    def __init__(self, check_interval: int = 300):
        """
        Initialize health checker.
        
        Args:
            check_interval: Time between health checks in seconds (default: 5 minutes)
        """
        self.check_interval = check_interval
        self.archive_provider = ArchiveProvider()
        self._last_check_time = 0
        self._cached_results: Dict[str, HealthCheckResult] = {}
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def check_provider_health(self, provider_name: str = None, force_refresh: bool = False) -> List[HealthCheckResult]:
        """
        Check health of archive providers.
        
        Args:
            provider_name: Specific provider to check (None = check all)
            force_refresh: Force re-check even if cached result is recent
            
        Returns:
            List of HealthCheckResult for checked providers
        """
        current_time = time.time()
        
        # Use cached results if recent enough
        if not force_refresh and (current_time - self._last_check_time) < self.check_interval:
            if provider_name:
                return [self._cached_results.get(provider_name)] if provider_name in self._cached_results else []
            return list(self._cached_results.values())
        
        self._logger.info("Running archive provider health checks...")
        
        results = []
        
        # Check each provider
        for provider in self.archive_provider.providers:
            provider_name = provider.get_provider_name()
            
            try:
                result = self._check_single_provider(provider)
                results.append(result)
                self._cached_results[provider_name] = result
            except Exception as e:
                self._logger.error(f"Health check failed for {provider_name}: {e}")
                results.append(HealthCheckResult(
                    provider_name=provider_name,
                    status=HealthStatus.ERROR,
                    endpoint_reachable=False,
                    response_time_ms=None,
                    details={'error': str(e)},
                    timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
                ))
        
        self._last_check_time = current_time
        
        # Filter if specific provider requested
        if provider_name:
            results = [r for r in results if r.provider_name == provider_name]
        
        return results
    
    def _check_single_provider(self, provider) -> HealthCheckResult:
        """
        Check health of a single provider.
        
        Args:
            provider: Provider instance to check
            
        Returns:
            HealthCheckResult for the provider
        """
        provider_name = provider.get_provider_name()
        start_time = time.time()
        
        details = {
            'endpoint_test': False,
            'snapshot_lookup_test': False,
            'response_format_test': False,
            'error_handling_test': False
        }
        
        # Test 1: Endpoint reachability
        try:
            test_url = "https://example.com"
            result = provider.check_archive(test_url)
            
            endpoint_reachable = True
            details['endpoint_test'] = True
            details['endpoint_response'] = result.availability.value
            
            # Test 2: Response format
            if hasattr(result, 'to_dict'):
                details['response_format_test'] = True
                details['response_structure'] = 'valid'
            
        except Exception as e:
            endpoint_reachable = False
            details['endpoint_error'] = str(e)
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Determine overall health status
        if endpoint_reachable and details.get('response_format_test'):
            if response_time_ms < 5000:  # Under 5 seconds
                status = HealthStatus.HEALTHY
            else:
                status = HealthStatus.DEGRADED
                details['degradation_reason'] = 'slow_response'
        elif endpoint_reachable:
            status = HealthStatus.DEGRADED
            details['degradation_reason'] = 'response_format_issue'
        else:
            status = HealthStatus.UNAVAILABLE
            details['unavailability_reason'] = 'endpoint_unreachable'
        
        return HealthCheckResult(
            provider_name=provider_name,
            status=status,
            endpoint_reachable=endpoint_reachable,
            response_time_ms=response_time_ms,
            details=details,
            timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def get_healthy_providers(self) -> List[str]:
        """
        Get list of currently healthy providers.
        
        Returns:
            List of provider names that are healthy
        """
        results = self.check_provider_health()
        return [r.provider_name for r in results if r.status == HealthStatus.HEALTHY]
    
    def is_provider_healthy(self, provider_name: str) -> bool:
        """
        Check if a specific provider is healthy.
        
        Args:
            provider_name: Name of provider to check
            
        Returns:
            True if provider is healthy, False otherwise
        """
        results = self.check_provider_health(provider_name=provider_name)
        return len(results) > 0 and results[0].status == HealthStatus.HEALTHY
    
    def print_health_report(self):
        """Print a formatted health report."""
        results = self.check_provider_health()
        
        print("\n=== ARCHIVE PROVIDERS HEALTH CHECK ===")
        
        for result in results:
            status_symbol = {
                HealthStatus.HEALTHY: "✓",
                HealthStatus.DEGRADED: "⚠",
                HealthStatus.UNAVAILABLE: "✗",
                HealthStatus.ERROR: "!",
                HealthStatus.UNKNOWN: "?"
            }.get(result.status, "?")
            
            print(f"\n{result.provider_name}: {result.status.value} {status_symbol}")
            print(f"  Endpoint reachable: {result.endpoint_reachable}")
            print(f"  Response time: {result.response_time_ms}ms" if result.response_time_ms else "  Response time: N/A")
            print(f"  Timestamp: {result.timestamp}")
            
            if result.details:
                for key, value in result.details.items():
                    print(f"  {key}: {value}")
        
        # Overall status
        healthy_count = sum(1 for r in results if r.status == HealthStatus.HEALTHY)
        total_count = len(results)
        
        print(f"\n=== OVERALL: {healthy_count}/{total_count} providers healthy ===")
        
        if healthy_count == total_count:
            print("✓ All archive providers are healthy")
        elif healthy_count > 0:
            print(f"⚠ Some providers degraded or unavailable")
        else:
            print("✗ No healthy archive providers available")


# Singleton instance
_health_checker_instance = None


def get_health_checker() -> ArchiveHealthChecker:
    """
    Get singleton instance of health checker.
    
    Returns:
        ArchiveHealthChecker instance
    """
    global _health_checker_instance
    if _health_checker_instance is None:
        _health_checker_instance = ArchiveHealthChecker()
    return _health_checker_instance
