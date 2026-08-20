"""
Test script for multi-archive provider system.

Tests the Playbill case where Wayback returns 503 and the system
should fallback to other providers.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from wikipedia_maintenance.utils.archive_provider import ArchiveProvider

def test_playbill_case():
    """Test the Playbill URL that returns 503 on Wayback."""
    
    # The Playbill URL that was problematic
    playbill_url = "http://www.playbill.com/news/article/serenade-with-larsen-and-henry-ends-off-broadway-run-dec.-15-146192"
    
    print("=" * 80)
    print("TEST: Playbill URL (Wayback 503 case)")
    print("=" * 80)
    print(f"URL: {playbill_url}")
    print()
    
    # Initialize archive provider
    provider = ArchiveProvider()
    
    print(f"Available providers: {[p.get_provider_name() for p in provider.providers]}")
    print()
    
    # Check archive availability
    print("Checking archive availability...")
    result = provider.check_archive(playbill_url)
    
    print()
    print("=" * 80)
    print("RESULT")
    print("=" * 80)
    print(f"Availability: {result.availability.value}")
    print(f"Archive URL: {result.archive_url}")
    print(f"Archive Date: {result.archive_date}")
    print(f"Provider: {result.provider}")
    print(f"Reason: {result.reason}")
    print()
    
    if result.availability.value == "available":
        print("✅ SUCCESS: Archive found via multi-provider fallback")
        print(f"   Provider: {result.provider}")
        print(f"   Archive URL: {result.archive_url}")
    else:
        print("❌ FAILED: No archive found in any provider")
        print(f"   Reason: {result.reason}")
    
    print("=" * 80)
    return result

if __name__ == "__main__":
    test_playbill_case()
