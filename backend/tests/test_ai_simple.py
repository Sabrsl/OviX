"""Simple test for AI normalization."""

import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from wikipedia_maintenance.utils.case_normalizer import CaseNormalizer

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def test_simple_ai():
    """Test simple AI normalization."""
    print("=" * 60)
    print("SIMPLE AI NORMALIZATION TEST")
    print("=" * 60)
    
    # Test case where AI should actually intervene (title all uppercase)
    test_text = "{{Article|auteur=JEAN DUPONT|titre=THE GREAT GATSBY}}"
    
    print(f"\nInput: {test_text}")
    
    # Initialize with AI normalization enabled
    normalizer = CaseNormalizer(enabled=True, normalize_with_ai=True)
    
    if not normalizer._gemini_available:
        print("[SKIP] Gemini not available")
        return
    
    try:
        result = normalizer.normalize_text(test_text)
        print(f"Output: {result.normalized_text}")
        print(f"Changes: {result.total_changes}")
        print(f"Ignored: {result.total_ignored}")
        
        for report in result.reports:
            print(f"  Template: {report.template_name}")
            for param, (before, after) in report.parameter_changes.items():
                print(f"    {param}: '{before}' -> '{after}'")
            for param, reason in report.ignored_occurrences:
                print(f"    {param}: ignored ({reason})")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_ai()
