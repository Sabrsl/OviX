"""
HTTPS Verification Cache abstraction.

Provides a clean interface for caching HTTPS verification results,
separating cache logic from database operations.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum


class VerificationStatus(Enum):
    """HTTPS verification status."""
    HTTPS_AVAILABLE = "HTTPS_AVAILABLE"
    HTTPS_UNAVAILABLE = "HTTPS_UNAVAILABLE"
    CHECK_FAILED = "CHECK_FAILED"


class HttpsVerificationCache:
    """
    Cache abstraction for HTTPS verification results.
    
    Provides a clean interface for storing and retrieving HTTPS verification
    results with appropriate TTL management.
    """
    
    # Default TTL values (in days)
    DEFAULT_TTL_AVAILABLE = 30  # HTTPS_AVAILABLE: 30 days
    DEFAULT_TTL_UNAVAILABLE = 7  # HTTPS_UNAVAILABLE: 7 days
    DEFAULT_TTL_FAILED = 1  # CHECK_FAILED: 1 day
    
    def __init__(self, db_manager, ttl_available: int = None, 
                 ttl_unavailable: int = None, ttl_failed: int = None):
        """
        Initialize the HTTPS verification cache.
        
        Args:
            db_manager: DatabaseManager instance
            ttl_available: TTL for HTTPS_AVAILABLE status (days)
            ttl_unavailable: TTL for HTTPS_UNAVAILABLE status (days)
            ttl_failed: TTL for CHECK_FAILED status (days)
        """
        self.db = db_manager
        self.ttl_available = ttl_available or self.DEFAULT_TTL_AVAILABLE
        self.ttl_unavailable = ttl_unavailable or self.DEFAULT_TTL_UNAVAILABLE
        self.ttl_failed = ttl_failed or self.DEFAULT_TTL_FAILED
        
        # Lock for preventing concurrent checks of same domain
        self._pending_checks: Dict[str, Any] = {}
    
    def get(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Get cached verification result for a domain.
        
        Args:
            domain: Domain to check
            
        Returns:
            Verification result dict or None if not found/expired
        """
        result = self.db.get_https_verification(domain)
        if result:
            status = result.get('status')
            # Convert string status to enum for easier comparison
            try:
                result['status_enum'] = VerificationStatus(status)
            except ValueError:
                # If status is invalid, treat as cache miss
                return None
        return result
    
    def set(self, domain: str, status: VerificationStatus, 
             https_url: Optional[str] = None, http_status_code: Optional[int] = None,
             redirect_url: Optional[str] = None, error_type: Optional[str] = None) -> None:
        """
        Store verification result in cache.
        
        Args:
            domain: Domain that was checked
            status: Verification status enum
            https_url: HTTPS URL that was checked
            http_status_code: HTTP status code from check
            redirect_url: Final URL after redirects
            error_type: Type of error if check failed
        """
        # Determine TTL based on status
        if status == VerificationStatus.HTTPS_AVAILABLE:
            ttl = self.ttl_available
        elif status == VerificationStatus.HTTPS_UNAVAILABLE:
            ttl = self.ttl_unavailable
        else:  # CHECK_FAILED
            ttl = self.ttl_failed
        
        self.db.set_https_verification(
            domain=domain,
            status=status.value,
            ttl_days=ttl,
            https_url=https_url,
            http_status_code=http_status_code,
            redirect_url=redirect_url,
            error_type=error_type
        )
    
    def invalidate(self, domain: str) -> None:
        """
        Invalidate cache entry for a domain.
        
        Args:
            domain: Domain to invalidate
        """
        self.db.invalidate_https_verification(domain)
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        return self.db.cleanup_expired_https_verifications()
    
    def is_check_pending(self, domain: str) -> bool:
        """
        Check if a verification is currently pending for this domain.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if check is pending
        """
        return domain in self._pending_checks
    
    def mark_check_pending(self, domain: str) -> None:
        """
        Mark a domain check as pending.
        
        Args:
            domain: Domain to mark as pending
        """
        self._pending_checks[domain] = datetime.now()
    
    def mark_check_complete(self, domain: str) -> None:
        """
        Mark a domain check as complete.
        
        Args:
            domain: Domain to mark as complete
        """
        if domain in self._pending_checks:
            del self._pending_checks[domain]
    
    def get_ttl_for_status(self, status: VerificationStatus) -> int:
        """
        Get TTL in days for a given status.
        
        Args:
            status: Verification status
            
        Returns:
            TTL in days
        """
        if status == VerificationStatus.HTTPS_AVAILABLE:
            return self.ttl_available
        elif status == VerificationStatus.HTTPS_UNAVAILABLE:
            return self.ttl_unavailable
        else:  # CHECK_FAILED
            return self.ttl_failed
