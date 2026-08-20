"""
Test script to debug import issues
"""

import sys
import os
from pathlib import Path

# Configure paths
project_root = Path(__file__).parent
os.environ['PYWIKIBOT_DIR'] = str(project_root)
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

print(f"Python version: {sys.version}")
print(f"Project root: {project_root}")
print(f"PYWIKIBOT_DIR: {os.environ.get('PYWIKIBOT_DIR')}")
print(f"sys.path: {sys.path}")

# Test basic imports
print("\n--- Testing basic imports ---")
try:
    import wikipedia_maintenance
    print("✓ wikipedia_maintenance import: PASS")
except Exception as e:
    print(f"✗ wikipedia_maintenance import: FAIL - {e}")

# Test specific modules
modules_to_test = [
    "wikipedia_maintenance.utils.api_throttler",
    "wikipedia_maintenance.utils.kill_switch_manager",
    "wikipedia_maintenance.utils.published_tracker",
    "wikipedia_maintenance.utils.analyzed_tracker",
    "wikipedia_maintenance.utils.database",
    "wikipedia_maintenance.utils.publisher",
    "wikipedia_maintenance.analyzers.dead_links",
    "wikipedia_maintenance.utils.wikipedia_api",
    "wikipedia_maintenance.retrievers.category",
    "wikipedia_maintenance.orchestrator.scheduler",
]

print("\n--- Testing specific modules ---")
for module_name in modules_to_test:
    try:
        __import__(module_name)
        print(f"✓ {module_name}: PASS")
    except Exception as e:
        print(f"✗ {module_name}: FAIL - {e}")

# Test pywikibot
print("\n--- Testing pywikibot ---")
try:
    import pywikibot
    print(f"✓ pywikibot import: PASS (version {pywikibot.__version__})")
except Exception as e:
    print(f"✗ pywikibot import: FAIL - {e}")

# Test FastAPI
print("\n--- Testing FastAPI ---")
try:
    import fastapi
    print(f"✓ fastapi import: PASS (version {fastapi.__version__})")
except Exception as e:
    print(f"✗ fastapi import: FAIL - {e}")

# Test uvicorn
print("\n--- Testing uvicorn ---")
try:
    import uvicorn
    print(f"✓ uvicorn import: PASS (version {uvicorn.__version__})")
except Exception as e:
    print(f"✗ uvicorn import: FAIL - {e}")
