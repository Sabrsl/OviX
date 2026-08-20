"""
OVIX Backend API - Simplified Main Application

This is a simplified version to test the basic FastAPI setup.
"""

import sys
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Configure paths
project_root = Path(__file__).parent.parent.parent
os.environ['PYWIKIBOT_DIR'] = str(project_root)
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Configure logging
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="OVIX Backend API",
    description="API for Wikipedia Dead Link Repair Tool",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "services": {
            "api": "ok"
        }
    }


# ============================================================================
# Basic Routes
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "OVIX Backend API",
        "version": "1.0.0",
        "docs": "/docs"
    }


# ============================================================================
# Main entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("Starting OVIX Backend API (Simplified)...")
    print("API Documentation: http://localhost:8000/docs")
    
    uvicorn.run(
        "backend.api.main_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
