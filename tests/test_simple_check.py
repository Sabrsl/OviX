import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("Testing imports one by one...")

try:
    from wikipedia_maintenance.utils import WikipediaAPIClient
    print("✓ WikipediaAPIClient")
except Exception as e:
    print(f"✗ WikipediaAPIClient: {e}")

try:
    from wikipedia_maintenance.utils import get_credential_manager
    print("✓ get_credential_manager")
except Exception as e:
    print(f"✗ get_credential_manager: {e}")

try:
    from wikipedia_maintenance.utils import setup_structured_logging
    print("✓ setup_structured_logging")
except Exception as e:
    print(f"✗ setup_structured_logging: {e}")

try:
    from wikipedia_maintenance.utils import get_retry_handler
    print("✓ get_retry_handler")
except Exception as e:
    print(f"✗ get_retry_handler: {e}")

try:
    from wikipedia_maintenance.utils import get_user_agent
    print("✓ get_user_agent")
except Exception as e:
    print(f"✗ get_user_agent: {e}")

try:
    from wikipedia_maintenance.utils import BotDiscussionManager
    print("✓ BotDiscussionManager")
except Exception as e:
    print(f"✗ BotDiscussionManager: {e}")

try:
    from wikipedia_maintenance.utils import PerformanceMonitor
    print("✓ PerformanceMonitor")
except Exception as e:
    print(f"✗ PerformanceMonitor: {e}")

try:
    from wikipedia_maintenance.utils import ControlledParallelism
    print("✓ ControlledParallelism")
except Exception as e:
    print(f"✗ ControlledParallelism: {e}")

try:
    from wikipedia_maintenance.utils import PayloadOptimizer
    print("✓ PayloadOptimizer")
except Exception as e:
    print(f"✗ PayloadOptimizer: {e}")

try:
    from wikipedia_maintenance.utils import BatchProcessor
    print("✓ BatchProcessor")
except Exception as e:
    print(f"✗ BatchProcessor: {e}")

print("\nAll core imports tested")