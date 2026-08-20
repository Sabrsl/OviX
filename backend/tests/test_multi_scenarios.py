"""
Multi-scenario test script for multi-archive provider system.

Tests different scenarios:
1. URL with archive (Playbill - Wayback 503 case)
2. URL without any archive (true NOT_AVAILABLE)
3. URL where only Archive.org has capture
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from wikipedia_maintenance.utils.archive_provider import ArchiveProvider

def test_scenario(name: str, url: str, expected_availability: str):
    """Test a specific scenario."""
    
    print("=" * 80)
    print(f"SCENARIO: {name}")
    print("=" * 80)
    print(f"URL: {url}")
    print(f"Expected: {expected_availability}")
    print()
    
    # Initialize archive provider
    provider = ArchiveProvider()
    
    # Check archive availability
    result = provider.check_archive(url)
    
    print()
    print("=" * 80)
    print(f"RESULT")
    print("=" * 80)
    print(f"Availability: {result.availability.value}")
    print(f"Archive URL: {result.archive_url}")
    print(f"Archive Date: {result.archive_date}")
    print(f"Provider: {result.provider}")
    print(f"Reason: {result.reason}")
    print()
    
    if result.availability.value == expected_availability:
        print("✅ PASS: Result matches expected availability")
    else:
        print(f"❌ FAIL: Expected {expected_availability}, got {result.availability.value}")
    
    print("=" * 80)
    print()
    
    return result.availability.value == expected_availability

if __name__ == "__main__":
    scenarios = [
        {
            "name": "Playbill URL (Wayback 503 case - has archive)",
            "url": "http://www.playbill.com/news/article/serenade-with-larsen-and-henry-ends-off-broadway-run-dec.-15-146192",
            "expected": "available"
        },
        {
            "name": "URL without any archive (true NOT_AVAILABLE)",
            "url": "http://this-domain-definitely-does-not-exist-123456789.com/page.html",
            "expected": "not_available"
        },
        {
            "name": "URL where only Archive.org might have capture",
            "url": "http://web.archive.org/web/20200101000000/https://example.com/",
            "expected": "not_available"  # This is a Wayback URL itself, not an original URL
        }
    ]
    
    print("Running multi-scenario test...")
    print()
    
    results = []
    for scenario in scenarios:
        passed = test_scenario(
            scenario["name"],
            scenario["url"],
            scenario["expected"]
        )
        results.append((scenario["name"], passed))
    
    print("=" * 80)
    print("MULTI-SCENARIO TEST SUMMARY")
    print("=" * 80)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print()
    print(f"Total: {passed_count}/{total_count} scenarios passed")
    
    if passed_count == total_count:
        print("✅ All scenarios passed")
    else:
        print("⚠️  Some scenarios failed")
    
    print("=" * 80)
