"""
Detailed server startup test with error capture
"""

import sys
import os
from pathlib import Path
import subprocess

# Configure paths
project_root = Path(__file__).parent
os.environ['PYWIKIBOT_DIR'] = str(project_root)

print("Starting detailed server test...")
print(f"Project root: {project_root}")

# Try to run uvicorn as a subprocess
try:
    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "test_fastapi_minimal:app", "--host", "0.0.0.0", "--port", "8000"],
        capture_output=True,
        text=True,
        timeout=5,
        cwd=str(project_root)
    )
    
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
    
except subprocess.TimeoutExpired:
    print("Server started successfully (timeout expected)")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
