"""
Stability test script for multi-archive provider system.

Runs the Playbill test multiple times to verify stability and reproducibility.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from wikipedia_maintenance.utils.archive_provider import ArchiveProvider

def test_playbill_case(run_number: int):
    """Test the Playbill URL that returns 503 on Wayback."""
    
    # The Playbill URL that was problematic
    playbill_url = "http://www.playbill.com/news/article/serenade-with-larsen-and-henry-ends-off-broadway-run-dec.-15-146192"
    
    print("=" * 80)
    print(f"RUN #{run_number}: Playbill URL (Wayback 503 case)")
    print("=" * 80)
    print(f"URL: {playbill_url}")
    print()
    
    # Initialize archive provider
    provider = ArchiveProvider()
    
    # Check archive availability
    result = provider.check_archive(playbill_url)
    
    print()
    print("=" * 80)
    print(f"RUN #{run_number} RESULT")
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
    print()
    
    return result

if __name__ == "__main__":
    num_runs = 4
    results = []
    
    print(f"Running stability test with {num_runs} iterations...")
    print()
    
    for i in range(1, num_runs + 1):
        result = test_playbill_case(i)
        results.append(result)
    
    print("=" * 80)
    print("STABILITY TEST SUMMARY")
    print("=" * 80)
    
    available_count = sum(1 for r in results if r.availability.value == "available")
    not_available_count = sum(1 for r in results if r.availability.value == "not_available")
    provider_unavailable_count = sum(1 for r in results if r.availability.value == "provider_unavailable")
    
    print(f"Total runs: {num_runs}")
    print(f"Available: {available_count}")
    print(f"Not Available: {not_available_count}")
    print(f"Provider Unavailable: {provider_unavailable_count}")
    print()
    
    if available_count == num_runs:
        print("✅ STABLE: All runs found archive")
    elif available_count > 0:
        print("⚠️  UNSTABLE: Some runs found archive, some didn't")
    else:
        print("❌ UNSTABLE: No runs found archive")
    
    print("=" * 80)
