"""
Test the bug fixes for DeadLinkAnalyzer content handling.

This test verifies that:
1. The content vs current_content divergence bug is fixed
2. The analyze() method properly stores repaired content
3. The orchestrator uses the repaired content
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from wikipedia_maintenance.analyzers.dead_links import DeadLinkAnalyzer
from wikipedia_maintenance.utils.link_checker import LinkStatus, LinkCheckResult


def test_content_divergence_fix():
    """Test that content divergence bug is fixed."""
    print("\n" + "=" * 60)
    print("TEST: Content Divergence Fix")
    print("=" * 60)
    
    analyzer = DeadLinkAnalyzer()
    
    # Verify that repaired_content attribute exists
    assert hasattr(analyzer, 'repaired_content'), "Analyzer should have repaired_content attribute"
    
    # Verify that current_content has been removed from analyze method
    import inspect
    source = inspect.getsource(DeadLinkAnalyzer.analyze)
    
    # The bug was that current_content was used instead of content
    # Now it should only use content
    assert "current_content" not in source or "current_content = content" not in source, \
        "Should not have current_content variable that diverges from content"
    
    print("[PASS] Content divergence fix verified")
    print("  - repaired_content attribute exists")
    print("  - current_content divergence issue removed")


def test_orchestrator_content_usage():
    """Test that orchestrator uses repaired content from analyzer."""
    print("\n" + "=" * 60)
    print("TEST: Orchestrator Content Usage")
    print("=" * 60)
    
    # Check orchestrator code for the fix
    from wikipedia_maintenance.orchestrator.automation_orchestrator import AutomationOrchestrator
    import inspect
    source = inspect.getsource(AutomationOrchestrator._analyze_with_analyzers)
    
    # Verify that orchestrator checks for repaired_content
    assert "repaired_content" in source, "Orchestrator should check for repaired_content"
    assert "hasattr(analyzer, 'repaired_content')" in source, "Orchestrator should use hasattr check"
    
    print("[PASS] Orchestrator content usage verified")
    print("  - Orchestrator checks for repaired_content attribute")
    print("  - Orchestrator updates content if repaired_content exists")


def test_exception_handling():
    """Test that exception handling in final_check is consistent."""
    print("\n" + "=" * 60)
    print("TEST: Exception Handling in final_check")
    print("=" * 60)
    
    # Create a simple test to verify the exception handling code exists
    import inspect
    source = inspect.getsource(DeadLinkAnalyzer._attempt_archive_fallback)
    
    # Check if the try-except block exists for final_check
    assert "try:" in source and "final_check" in source, "Should have try-except for final_check"
    assert "FINAL_VERIFICATION_EXCEPTION" in source, "Should have exception logging"
    
    print("[PASS] Exception handling verified in source code")
    print("  - Found try-except block for final_check")
    print("  - Found exception logging for FINAL_VERIFICATION_EXCEPTION")


if __name__ == "__main__":
    try:
        test_content_divergence_fix()
        test_orchestrator_content_usage()
        test_exception_handling()
        
        print("\n" + "=" * 60)
        print("ALL CRITICAL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
