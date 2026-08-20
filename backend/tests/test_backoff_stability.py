"""
Backoff exponential stability test for multi-archive provider system.

Tests the Playbill case multiple times with exponential backoff (2s, 4s, 8s)
to measure success rate and total execution time.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from wikipedia_maintenance.utils.archive_provider import ArchiveProvider

def test_playbill_backoff(run_number: int):
    """Test the Playbill URL with exponential backoff."""
    
    playbill_url = "http://www.playbill.com/news/article/serenade-with-larsen-and-henry-ends-off-broadway-run-dec.-15-146192"
    
    print("=" * 80)
    print(f"RUN #{run_number}: Playbill URL (Wayback 503 case) - Exponential Backoff")
    print("=" * 80)
    print(f"URL: {playbill_url}")
    print()
    
    # Initialize archive provider
    provider = ArchiveProvider()
    
    # Measure execution time
    start_time = time.time()
    
    # Check archive availability
    result = provider.check_archive(playbill_url)
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    print()
    print("=" * 80)
    print(f"RUN #{run_number} RESULT")
    print("=" * 80)
    print(f"Availability: {result.availability.value}")
    print(f"Archive URL: {result.archive_url}")
    print(f"Archive Date: {result.archive_date}")
    print(f"Provider: {result.provider}")
    print(f"Reason: {result.reason}")
    print(f"Execution Time: {execution_time:.2f}s")
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
    
    return result, execution_time

if __name__ == "__main__":
    num_runs = 5
    results = []
    execution_times = []
    
    print(f"Running backoff linear stability test with {num_runs} iterations...")
    print("Backoff strategy: 2s, 3s, 4s (linear progression)")
    print()
    
    for i in range(1, num_runs + 1):
        result, exec_time = test_playbill_backoff(i)
        results.append(result)
        execution_times.append(exec_time)
    
    print("=" * 80)
    print("BACKOFF LINEAR STABILITY TEST SUMMARY")
    print("=" * 80)
    
    available_count = sum(1 for r in results if r.availability.value == "available")
    not_available_count = sum(1 for r in results if r.availability.value == "not_available")
    provider_unavailable_count = sum(1 for r in results if r.availability.value == "provider_unavailable")
    
    avg_execution_time = sum(execution_times) / len(execution_times)
    max_execution_time = max(execution_times)
    min_execution_time = min(execution_times)
    
    print(f"Total runs: {num_runs}")
    print(f"Available: {available_count}")
    print(f"Not Available: {not_available_count}")
    print(f"Provider Unavailable: {provider_unavailable_count}")
    print()
    print(f"Average execution time: {avg_execution_time:.2f}s")
    print(f"Min execution time: {min_execution_time:.2f}s")
    print(f"Max execution time: {max_execution_time:.2f}s")
    print()
    
    if available_count == num_runs:
        print("✅ STABLE: All runs found archive")
    elif available_count > 0:
        print("⚠️  PARTIAL: Some runs found archive, some didn't")
    else:
        print("❌ UNSTABLE: No runs found archive")
    
    print("=" * 80)
