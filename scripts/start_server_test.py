"""
Start server test script
"""

import sys
import os
from pathlib import Path

# Configure paths
project_root = Path(__file__).parent
os.environ['PYWIKIBOT_DIR'] = str(project_root)
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

print("Starting server test...")
print(f"Project root: {project_root}")
print(f"Python path: {sys.path[:3]}")

try:
    import uvicorn
    from test_fastapi_minimal import app
    
    print("✓ Imports successful")
    print("Starting uvicorn server...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
