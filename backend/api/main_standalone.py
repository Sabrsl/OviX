"""
OVIX Backend API - Standalone Version

This version uses a minimal dependency set to avoid conflicts with Streamlit.
It will be tested first before integrating with the full OVIX core.
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
    title="OVIX Backend API - Standalone",
    description="Standalone API for Wikipedia Dead Link Repair Tool",
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
        },
        "python_version": sys.version,
        "project_root": str(project_root)
    }


# ============================================================================
# Import Test Endpoint
# ============================================================================

@app.get("/api/test-imports")
async def test_imports():
    """Test if we can import the OVIX core modules."""
    import_results = {}
    
    # Test basic imports
    try:
        import wikipedia_maintenance
        import_results["wikipedia_maintenance"] = "PASS"
    except Exception as e:
        import_results["wikipedia_maintenance"] = f"FAIL: {str(e)}"
    
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
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            import_results[module_name] = "PASS"
        except Exception as e:
            import_results[module_name] = f"FAIL: {str(e)}"
    
    return {
        "success": True,
        "imports": import_results
    }


# ============================================================================
# Pywikibot Test Endpoint
# ============================================================================

@app.get("/api/test-pywikibot")
async def test_pywikibot():
    """Test pywikibot initialization."""
    try:
        import pywikibot
        return {
            "success": True,
            "pywikibot_version": pywikibot.__version__,
            "pywikibot_dir": os.environ.get('PYWIKIBOT_DIR'),
            "status": "PASS"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status": "FAIL"
        }


# ============================================================================
# Wikipedia Client Test Endpoint
# ============================================================================

@app.get("/api/test-wikipedia-client")
async def test_wikipedia_client():
    """Test WikipediaAPIClient initialization."""
    try:
        from wikipedia_maintenance.utils.wikipedia_api import WikipediaAPIClient
        from wikipedia_maintenance.utils.kill_switch_manager import KillSwitchManager
        
        # Initialize client
        client = WikipediaAPIClient(language="fr")
        
        # Test kill switch
        kill_switch = KillSwitchManager()
        kill_switch.check_and_raise()
        
        return {
            "success": True,
            "client_initialized": True,
            "language": "fr",
            "kill_switch_enabled": kill_switch.is_enabled(),
            "status": "PASS"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status": "FAIL"
        }


# ============================================================================
# Article Retrieval Test Endpoint
# ============================================================================

@app.get("/api/test-article-retrieval")
async def test_article_retrieval():
    """Test article retrieval (read-only)."""
    try:
        from wikipedia_maintenance.utils.wikipedia_api import WikipediaAPIClient
        from wikipedia_maintenance.utils.kill_switch_manager import KillSwitchManager
        from wikipedia_maintenance.utils.api_throttler import get_global_throttler
        
        # Initialize client
        client = WikipediaAPIClient(language="fr")
        client.set_throttler(get_global_throttler())
        
        kill_switch = KillSwitchManager()
        kill_switch.check_and_raise()
        
        # Test retrieval of a simple article
        article_title = "Paris"
        article_content = client.get_page_content(article_title)
        
        return {
            "success": True,
            "article_title": article_title,
            "content_length": len(article_content) if article_content else 0,
            "has_content": bool(article_content),
            "status": "PASS"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status": "FAIL"
        }


# ============================================================================
# Kill Switch Test Endpoint
# ============================================================================

@app.get("/api/test-kill-switch")
async def test_kill_switch():
    """Test Kill Switch functionality."""
    try:
        from wikipedia_maintenance.utils.kill_switch_manager import KillSwitchManager, KillSwitchTrigger
        
        kill_switch = KillSwitchManager()
        
        # Get current state
        initial_state = kill_switch.is_enabled()
        
        # Test activation
        kill_switch.enable(reason="API test", trigger_source=KillSwitchTrigger.MANUAL, requested_by="api_test")
        activated_state = kill_switch.is_enabled()
        
        # Test deactivation
        kill_switch.disable(reason="API test completed", requested_by="api_test")
        final_state = kill_switch.is_enabled()
        
        return {
            "success": True,
            "initial_state": initial_state,
            "activated_state": activated_state,
            "final_state": final_state,
            "kill_switch_works": not initial_state and activated_state and not final_state,
            "status": "PASS"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status": "FAIL"
        }


# ============================================================================
# Basic Routes
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "OVIX Backend API - Standalone Version",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/health",
            "import_test": "/api/test-imports",
            "pywikibot_test": "/api/test-pywikibot",
            "wikipedia_client_test": "/api/test-wikipedia-client",
            "article_retrieval_test": "/api/test-article-retrieval",
            "kill_switch_test": "/api/test-kill-switch"
        }
    }


# ============================================================================
# Main entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("Starting OVIX Backend API (Standalone)...")
    print("API Documentation: http://127.0.0.1:8001/docs")
    print("Import Test: http://127.0.0.1:8001/api/test-imports")
    print("Pywikibot Test: http://127.0.0.1:8001/api/test-pywikibot")
    print("Wikipedia Client Test: http://127.0.0.1:8001/api/test-wikipedia-client")
    print("Article Retrieval Test: http://127.0.0.1:8001/api/test-article-retrieval")
    print("Kill Switch Test: http://127.0.0.1:8001/api/test-kill-switch")
    
    uvicorn.run(
        app,  # Use app directly instead of string
        host="127.0.0.1",  # Use localhost instead of 0.0.0.0
        port=8001,  # Use different port
        reload=True,  # Enable reload for development
        log_level="info"
    )
