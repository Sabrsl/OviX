#!/usr/bin/env python3
"""
OVIX Backend API - Startup Script

Run this script to start the FastAPI backend server.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
os.environ['PYWIKIBOT_DIR'] = str(project_root)
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

import uvicorn

if __name__ == "__main__":
    print("Starting OVIX Backend API...")
    print("API Documentation: http://localhost:8000/docs")
    print("ReDoc Documentation: http://localhost:8000/redoc")
    
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
