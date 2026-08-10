# Simple import test to verify modules can be imported
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("Testing imports...")

try:
    from wikipedia_maintenance.utils.secure_credentials import SecureCredentialManager, get_credential_manager
    print("✓ secure_credentials imported successfully")
except Exception as e:
    print(f"✗ secure_credentials import failed: {e}")

try:
    from wikipedia_maintenance.utils.structured_logging import StructuredLogger, setup_structured_logging
    print("✓ structured_logging imported successfully")
except Exception as e:
    print(f"✗ structured_logging import failed: {e}")

try:
    from wikipedia_maintenance.utils.published_tracker import PublishedTracker
    print("✓ published_tracker imported successfully")
except Exception as e:
    print(f"✗ published_tracker import failed: {e}")

try:
    from wikipedia_maintenance.utils.publisher import Publisher
    print("✓ publisher imported successfully")
except Exception as e:
    print(f"✗ publisher import failed: {e}")

print("\nAll imports tested")