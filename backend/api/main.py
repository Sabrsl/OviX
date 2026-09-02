"""
OVIX Backend API - Main FastAPI Application

This FastAPI application exposes the existing Python core services
to the React frontend while maintaining compatibility with Streamlit.
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from dotenv import load_dotenv
import uvicorn

# Force UTF-8 encoding for Windows
if sys.platform == 'win32':
    import locale
    import codecs
    try:
        # Try to set UTF-8 encoding
        codecs.register(lambda name: codecs.lookup('utf-8') if name == 'mbcs' else None)
        os.environ['PYTHONIOENCODING'] = 'utf-8'
    except:
        pass

# Set PROJECT_ROOT based on script location (consistent across all entry points)
# backend/api/main.py -> project root (go up 3 levels)
current_path = Path(__file__).resolve()
PROJECT_ROOT = current_path.parent.parent.parent
os.environ['PROJECT_ROOT'] = str(PROJECT_ROOT.absolute())

# Load environment variables
env_path = PROJECT_ROOT / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment variables from {env_path}")
else:
    print(f".env file not found at {env_path}, trying default location")
    load_dotenv()  # Try default location

# Configure paths
os.environ['PYWIKIBOT_DIR'] = str(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

# Configure logging
log_dir = PROJECT_ROOT / "logs"
log_dir.mkdir(exist_ok=True)

# Import logging configuration
sys.path.insert(0, str(PROJECT_ROOT / 'utils'))
from logging_config import setup_logging
setup_logging()

logger = logging.getLogger(__name__)
logger.info(f"PROJECT_ROOT set to: {PROJECT_ROOT.absolute()}")

# Import existing services
from wikipedia_maintenance.utils.api_throttler import get_global_throttler
from wikipedia_maintenance.utils.kill_switch_manager import get_kill_switch_manager
from wikipedia_maintenance.utils.published_tracker import PublishedTracker
from wikipedia_maintenance.utils.analyzed_tracker import get_analyzed_tracker
from wikipedia_maintenance.utils.database import DatabaseManager
from wikipedia_maintenance.orchestrator.scheduler_state_sqlite import SQLiteStateManager
from wikipedia_maintenance.utils.automation_state_sqlite import SQLiteAutomationStateManager
from wikipedia_maintenance.utils.config import Config

# Global service instances
_global_throttler = None
_kill_switch_manager = None
_published_tracker = None
_analyzed_tracker = None
_database_manager = None
_scheduler_state_manager = None
_scheduler = None
_automation_state_manager = None
_config = None
_automation_orchestrator = None  # Active automation orchestrator instance
# _automation_launch_lock removed - now using database lock for distributed safety


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting OVIX Backend API...")
    
    # Initialize global services
    global _global_throttler, _kill_switch_manager, _published_tracker
    global _analyzed_tracker, _database_manager, _scheduler_state_manager
    global _scheduler, _automation_state_manager, _config, _automation_orchestrator

    try:
        _global_throttler = get_global_throttler()
        logger.info("Global throttler initialized")

        # Initialize database FIRST (needed by kill switch manager)
        db_path = str(PROJECT_ROOT / "data" / "wikipedia_maintenance.db")
        logger.info(f"Initializing database with path: {db_path}")
        logger.info(f"Database file exists: {Path(db_path).exists()}")
        _database_manager = DatabaseManager(db_path)

        # Verify database has data
        try:
            cursor = _database_manager.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM analysis_results")
            count = cursor.fetchone()[0]
            logger.info(f"Database verification: {count} analysis results found")
        except Exception as e:
            logger.warning(f"Could not verify database contents: {e}")

        # Now initialize kill switch manager with database
        try:
            _kill_switch_manager = get_kill_switch_manager(database=_database_manager)
            logger.info("Kill switch manager initialized")
        except Exception as e:
            logger.error(f"Could not initialize kill switch manager: {e}", exc_info=True)
            _kill_switch_manager = None

        _published_tracker = PublishedTracker()
        logger.info("Published tracker initialized")

        try:
            _analyzed_tracker = get_analyzed_tracker()
            logger.info("Analyzed tracker initialized successfully")
        except Exception as e:
            logger.error(f"Could not initialize analyzed tracker: {e}", exc_info=True)
            _analyzed_tracker = None

        try:
            _scheduler_state_manager = SQLiteStateManager(_database_manager)
            logger.info("Scheduler state manager initialized (SQLite)")
        except Exception as e:
            logger.error(f"Could not initialize scheduler state manager: {e}", exc_info=True)
            _scheduler_state_manager = None

        try:
            from wikipedia_maintenance.orchestrator.scheduler import Scheduler, SchedulerConfig
            from wikipedia_maintenance.utils.publisher import Publisher
            import pywikibot

            # Initialize publisher
            publisher = Publisher()

            # Initialize pywikibot site for scheduler
            try:
                site = pywikibot.Site('fr', 'wikipedia')
                logger.info("Pywikibot site initialized for scheduler")
            except Exception as e:
                logger.warning(f"Could not initialize pywikibot site: {e}")
                site = None

            # Initialize scheduler config
            scheduler_config = SchedulerConfig(
                state_file=str(PROJECT_ROOT / "data" / "scheduler_state.json"),
                dry_run=True,  # Default to dry-run mode
                daily_limit=30,
                stop_on_empty_queue=False,  # Don't stop on empty queue - will transfer articles
                category=None,  # Will be set via API
                articles_to_process=10,  # Default for manual runs
                site=site  # Pass pywikibot site
            )

            # Initialize scheduler
            _scheduler = Scheduler(
                config=scheduler_config,
                publisher=publisher,
                published_tracker=_published_tracker,
                analyzed_tracker=_analyzed_tracker,
                kill_switch_manager=_kill_switch_manager,
                database=_database_manager
            )
            logger.info("Scheduler initialized (with database, kill switch, and site)")
        except Exception as e:
            logger.error(f"Could not initialize scheduler: {e}", exc_info=True)
            _scheduler = None
        
        try:
            _automation_state_manager = SQLiteAutomationStateManager(_database_manager)
            logger.info("Automation state manager initialized (SQLite)")
        except Exception as e:
            logger.error(f"Could not initialize automation state manager: {e}", exc_info=True)
            _automation_state_manager = None
        
        try:
            _config = Config()
            logger.info("Config initialized")
        except Exception as e:
            logger.error(f"Could not initialize config: {e}", exc_info=True)
            _config = None
        
        logger.info("All services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down OVIX Backend API...")


# Create FastAPI application
app = FastAPI(
    title="OVIX Backend API",
    description="API for Wikipedia Dead Link Repair Tool",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Dependencies
# ============================================================================

def get_throttler():
    """Dependency to get global throttler."""
    if _global_throttler is None:
        raise HTTPException(status_code=500, detail="Throttler not initialized")
    return _global_throttler


def get_kill_switch():
    """Dependency to get kill switch manager."""
    global _kill_switch_manager
    if _kill_switch_manager is None:
        logger.warning("Kill switch manager not available")
    return _kill_switch_manager


def get_scheduler_state():
    """Dependency to get scheduler state manager."""
    global _scheduler_state_manager
    if _scheduler_state_manager is None:
        logger.warning("Scheduler state manager not available")
    return _scheduler_state_manager


def get_scheduler():
    """Dependency to get scheduler instance."""
    global _scheduler
    if _scheduler is None:
        logger.warning("Scheduler not available")
    return _scheduler


def get_automation_state():
    """Dependency to get automation state manager."""
    global _automation_state_manager
    if _automation_state_manager is None:
        logger.warning("Automation state manager not available")
    return _automation_state_manager


def get_automation_orchestrator():
    """Dependency to get active automation orchestrator."""
    global _automation_orchestrator
    if _automation_orchestrator is None:
        logger.warning("Automation orchestrator not available")
    return _automation_orchestrator


def set_automation_orchestrator(orchestrator):
    """Set the active automation orchestrator."""
    global _automation_orchestrator
    _automation_orchestrator = orchestrator
    logger.info("Automation orchestrator set globally")


def get_automation_lock():
    """Dependency to get database automation lock manager."""
    global _database_manager
    if _database_manager is None:
        logger.warning("Database manager not available for automation lock")
        return None
    return _database_manager


def get_published_tracker():
    """Dependency to get published tracker."""
    global _published_tracker
    if _published_tracker is None:
        try:
            _published_tracker = PublishedTracker()
            logger.info("Published tracker initialized in dependency")
        except Exception as e:
            logger.error(f"Could not initialize published tracker: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Published tracker not initialized")
    return _published_tracker


def get_analyzed_tracker():
    """Dependency to get analyzed tracker."""
    global _analyzed_tracker
    if _analyzed_tracker is None:
        try:
            from wikipedia_maintenance.utils.analyzed_tracker import get_analyzed_tracker as _get_analyzed_tracker
            _analyzed_tracker = _get_analyzed_tracker()
            logger.info("Analyzed tracker initialized successfully in dependency")
        except Exception as e:
            logger.error(f"Could not initialize analyzed tracker: {e}", exc_info=True)
            _analyzed_tracker = None
    return _analyzed_tracker


def get_database():
    """Dependency to get database manager."""
    global _database_manager
    if _database_manager is None:
        try:
            # Use absolute path to ensure database is found
            db_path = str(PROJECT_ROOT / "data" / "wikipedia_maintenance.db")
            logger.info(f"Initializing database manager with path: {db_path}")
            logger.info(f"Database file exists: {Path(db_path).exists()}")
            
            _database_manager = DatabaseManager(db_path)
            logger.info("Database manager initialized in dependency")
            
            # Verify database has data
            try:
                cursor = _database_manager.conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM analysis_results")
                count = cursor.fetchone()[0]
                logger.info(f"Database verification: {count} analysis results found")
            except Exception as e:
                logger.warning(f"Could not verify database contents: {e}")
                
        except Exception as e:
            logger.error(f"Could not initialize database manager: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Database manager not initialized")
    return _database_manager


def get_config():
    """Dependency to get configuration."""
    global _config
    if _config is None:
        logger.warning("Config not available")
    return _config


# ============================================================================
# Health Check
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    try:
        logger.info("Health check requested")
        health_status = {
            "status": "healthy",
            "services": {
                "api": "ok",
                "throttler": "ok" if _global_throttler else "not_initialized",
                "kill_switch": "ok" if _kill_switch_manager else "not_initialized",
                "published_tracker": "ok" if _published_tracker else "not_initialized",
                "analyzed_tracker": "ok" if _analyzed_tracker else "not_initialized",
                "database": "ok" if _database_manager else "not_initialized",
                "scheduler_state": "ok" if _scheduler_state_manager else "not_initialized",
                "automation_state": "ok" if _automation_state_manager else "not_initialized",
                "config": "ok" if _config else "not_initialized",
            }
        }
        logger.info(f"Health check status: {health_status}")
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc)
            }
        }
    )


# ============================================================================
# Import routes
# ============================================================================

from backend.api.routes import (
    auth,
    articles,
    analysis,
    config,
    diff,
    publication,
    history,
    logs,
    settings,
    system,
    manual_review,
    migration,
    stats_v2,
    stats_compare,
    article_scheduler
)

# Register routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(articles.router, prefix="/api/articles", tags=["Articles"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(config.router, prefix="/api/config", tags=["Configuration"])
app.include_router(diff.router, prefix="/api/diff", tags=["Diff"])
app.include_router(publication.router, prefix="/api/publication", tags=["Publication"])
app.include_router(history.router, prefix="/api/history", tags=["History"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(manual_review.router, prefix="/api", tags=["Manual Review"])
app.include_router(migration.router, prefix="/api/migration", tags=["Migration"])
app.include_router(stats_v2.router, tags=["Stats-V2"])
app.include_router(stats_compare.router, tags=["Stats-Comparison"])
app.include_router(article_scheduler.router, prefix="/api/article-scheduler", tags=["Article Scheduler"])


# ============================================================================
# Main entry point
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "backend.api.main:app",
        host=os.environ.get("API_HOST", "0.0.0.0"),
        port=int(os.environ.get("API_PORT", "8000")),
        reload=True,  # Enabled for development
        log_level="info"
    )
