"""
OVIX Backend API - System Routes

Handles system-level operations like Kill Switch and Scheduler control.
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Models
# ============================================================================

class KillSwitchStatusResponse(BaseModel):
    """Kill switch status response."""
    enabled: bool
    reason: str
    trigger_source: str
    requested_by: Optional[str] = None
    requested_at: Optional[str] = None
    last_checked: Optional[str] = None


class KillSwitchActionRequest(BaseModel):
    """Kill switch action request."""
    enabled: bool
    reason: str
    requested_by: str = "api"


class SchedulerStatusResponse(BaseModel):
    """Scheduler status response."""
    is_active: bool
    is_paused: bool  # NEW: Track pause state
    daily_published_count: int
    queue_size: int
    next_publish_time: Optional[str] = None
    statistics: dict
    current_task: Optional[str] = None
    next_execution: Optional[str] = None
    last_execution: Optional[str] = None
    daily_limit: Optional[int] = None


class SchedulerActionRequest(BaseModel):
    """Scheduler action request."""
    action: str  # "start", "pause", "resume", "stop"


class SchedulerConfigRequest(BaseModel):
    """Scheduler configuration request."""
    daily_limit: Optional[int] = None
    working_hours_start: Optional[int] = None
    working_hours_end: Optional[int] = None
    dry_run: Optional[bool] = None
    category: Optional[str] = None
    articles_to_process: Optional[int] = None


class ManualSchedulerRunRequest(BaseModel):
    """Manual scheduler run request."""
    include_analyzed: bool = False
    lia_mode: bool = False


class AutomationStatusResponse(BaseModel):
    """Automation orchestrator status response."""
    success: bool
    status: str
    session_id: str
    current_step: str
    articles_processed: int
    articles_published: int
    articles_error: int
    category_name: str
    started_at: str
    article_states: List[Dict[str, Any]] = []


class SystemStatusResponse(BaseModel):
    """System status response."""
    wikipedia: dict
    scheduler: dict
    kill_switch: dict
    # Additional system information
    database_stats: Optional[dict] = None


# ============================================================================
# Dependencies
# ============================================================================

def get_kill_switch():
    """Get kill switch manager."""
    try:
        from backend.api.main import get_kill_switch
        return get_kill_switch()
    except Exception as e:
        logger.warning(f"Kill switch manager not initialized: {e}")
        return None


def get_scheduler_state():
    """Get scheduler state manager."""
    try:
        from backend.api.main import get_scheduler_state
        return get_scheduler_state()
    except Exception as e:
        logger.warning(f"Scheduler state manager not initialized: {e}")
        return None


def get_scheduler():
    """Get scheduler instance."""
    try:
        from backend.api.main import get_scheduler
        return get_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler not initialized: {e}")
        return None


def get_automation_state():
    """Get automation state manager."""
    try:
        from backend.api.main import get_automation_state
        return get_automation_state()
    except Exception as e:
        logger.warning(f"Automation state manager not initialized: {e}")
        return None


def get_automation_orchestrator():
    """Get active automation orchestrator."""
    try:
        from backend.api.main import get_automation_orchestrator
        return get_automation_orchestrator()
    except Exception as e:
        logger.warning(f"Automation orchestrator not initialized: {e}")
        return None


def get_wikipedia_session():
    """Get Wikipedia session."""
    from backend.api.routes.auth import get_wikipedia_session as get_session
    return get_session()


# ============================================================================
# System Status Routes
# ============================================================================

@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    kill_switch = Depends(get_kill_switch),
    scheduler_state = Depends(get_scheduler_state),
    wikipedia_session = Depends(get_wikipedia_session)
):
    """
    Get overall system status (LEGACY - PARTIALLY DEPRECATED).

    ⚠️ Statistics in this endpoint now use centralized StatsService.
    For complete statistics, use /api/stats/v2/system instead.
    
    Returns the status of all major system components.
    Services that are unavailable return default values instead of failing.
    """
    try:
        logger.info("Getting system status...")
        
        # Get kill switch status - safe fallback
        ks_state = None
        try:
            if kill_switch:
                ks_state = kill_switch.get_state()
                logger.info(f"Kill switch status: {ks_state}")
            else:
                logger.info("Kill switch manager not available")
        except Exception as e:
            logger.warning(f"Failed to get kill switch status: {e}")
            ks_state = type('obj', (object,), {'enabled': False, 'reason': 'Unavailable', 'trigger_source': 'error', 'requested_by': 'system', 'requested_at': None})()

        # Get scheduler status - safe fallback
        sched_state = None
        try:
            if scheduler_state:
                sched_state = scheduler_state.get_state()
                logger.info(f"Scheduler status: {sched_state}")
            else:
                logger.info("Scheduler state manager not available")
        except Exception as e:
            logger.warning(f"Failed to get scheduler status: {e}")
            sched_state = type('obj', (object,), {'is_active': False, 'daily_published_count': 0, 'queue': [], 'next_publish_time': None})()

        # Get Wikipedia status - safe fallback
        wiki_status = {
            "connected": wikipedia_session.get("authenticated", False) if wikipedia_session else False,
            "username": wikipedia_session.get("username") if wikipedia_session else None,
            "language": wikipedia_session.get("lang") if wikipedia_session else None,
            "family": wikipedia_session.get("family") if wikipedia_session else None,
            "site": str(wikipedia_session.get("site")) if wikipedia_session and wikipedia_session.get("site") else None
        }
        logger.info(f"Wikipedia status: {wiki_status}")

        # Get database statistics from centralized StatsService
        try:
            from backend.stats import StatsService
            stats_service = StatsService()
            article_stats = stats_service.get_article_stats()
            total_articles = article_stats.total
            published_articles = article_stats.published
            articles_with_changes = stats_service.get_database_stats().articles_with_changes
            logger.info(f"Database stats from StatsService: total={total_articles}, published={published_articles}, with_changes={articles_with_changes}")
        except Exception as e:
            logger.warning(f"Failed to get database stats from StatsService: {e}")
            total_articles = 0
            published_articles = 0
            articles_with_changes = 0

        response_data = SystemStatusResponse(
            wikipedia=wiki_status,
            scheduler={
                "is_active": sched_state.is_active if sched_state else False,
                "daily_published_count": sched_state.daily_published_count if sched_state else 0,
                "queue_size": len(sched_state.queue) if sched_state and hasattr(sched_state, 'queue') else 0,
                "next_publish_time": sched_state.next_publish_time if sched_state else None,
                "total_articles": total_articles,
                "published_articles": published_articles,
                "articles_with_changes": articles_with_changes
            },
            kill_switch={
                "enabled": ks_state.enabled if ks_state else False,
                "reason": ks_state.reason if ks_state else "Unavailable",
                "trigger_source": ks_state.trigger_source if ks_state else "error",
                "requested_by": ks_state.requested_by if ks_state else "system",
                "requested_at": ks_state.requested_at if ks_state else None
            },
            database_stats={
                "total_articles": total_articles,
                "published_articles": published_articles,
                "articles_with_changes": articles_with_changes,
                "pending_articles": total_articles - published_articles
            }
        )
        
        logger.info(f"System status response: {response_data}")
        return response_data

    except Exception as e:
        logger.error(f"Failed to get system status: {e}", exc_info=True)
        # Return safe defaults instead of failing
        logger.info("Returning safe defaults for system status")
        return SystemStatusResponse(
            wikipedia={"connected": False, "username": None, "language": None, "family": None, "site": None},
            scheduler={"is_active": False, "daily_published_count": 0, "queue_size": 0, "next_publish_time": None, "total_articles": 0, "published_articles": 0, "articles_with_changes": 0},
            kill_switch={"enabled": False, "reason": "Error", "trigger_source": "error", "requested_by": "system", "requested_at": None},
            database_stats={"total_articles": 0, "published_articles": 0, "articles_with_changes": 0, "pending_articles": 0}
        )


# ============================================================================
# Kill Switch Routes
# ============================================================================

@router.get("/kill-switch", response_model=KillSwitchStatusResponse)
async def get_kill_switch_status(kill_switch = Depends(get_kill_switch)):
    """
    Get Kill Switch status.
    
    Returns the current status of the Kill Switch.
    """
    try:
        if not kill_switch:
            # Return default status when kill switch is not initialized
            return KillSwitchStatusResponse(
                enabled=False,
                reason="Kill switch manager not initialized",
                trigger_source="system",
                requested_by="system",
                requested_at=None,
                last_checked=None
            )
        
        state = kill_switch.get_state()
        
        return KillSwitchStatusResponse(
            enabled=state.enabled,
            reason=state.reason,
            trigger_source=state.trigger_source,
            requested_by=state.requested_by,
            requested_at=state.requested_at,
            last_checked=state.last_checked
        )
        
    except Exception as e:
        logger.error(f"Failed to get kill switch status: {e}", exc_info=True)
        # Return safe defaults instead of failing
        return KillSwitchStatusResponse(
            enabled=False,
            reason="Error",
            trigger_source="error",
            requested_by="system",
            requested_at=None,
            last_checked=None
        )


@router.post("/kill-switch/activate")
async def activate_kill_switch(
    request: KillSwitchActionRequest,
    kill_switch = Depends(get_kill_switch)
):
    """
    Activate the Kill Switch.

    This will stop all automated operations.
    """
    try:
        if not kill_switch:
            return {
                "success": False,
                "message": "Kill switch manager not initialized"
            }

        from wikipedia_maintenance.utils.kill_switch_manager import KillSwitchTrigger
        from backend.api.routes.auth import _wikipedia_session

        # Use authenticated username from session if available
        username = _wikipedia_session.get("username") or request.requested_by

        kill_switch.enable(
            reason=request.reason,
            trigger_source=KillSwitchTrigger.MANUAL,
            requested_by=username
        )

        logger.warning(f"Kill Switch activated by {username}: {request.reason}")

        return {
            "success": True,
            "message": "Kill Switch activated",
            "reason": request.reason
        }

    except Exception as e:
        logger.error(f"Failed to activate kill switch: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to activate: {str(e)}"
        }


@router.post("/kill-switch/deactivate")
async def deactivate_kill_switch(
    request: KillSwitchActionRequest,
    kill_switch = Depends(get_kill_switch)
):
    """
    Deactivate the Kill Switch.

    This will allow automated operations to resume.
    """
    try:
        if not kill_switch:
            return {
                "success": False,
                "message": "Kill switch manager not initialized"
            }

        from backend.api.routes.auth import _wikipedia_session

        # Use authenticated username from session if available
        username = _wikipedia_session.get("username") or request.requested_by

        kill_switch.disable(
            reason=request.reason,
            requested_by=username
        )

        logger.info(f"Kill Switch deactivated by {username}: {request.reason}")

        return {
            "success": True,
            "message": "Kill Switch deactivated",
            "reason": request.reason
        }

    except Exception as e:
        logger.error(f"Failed to deactivate kill switch: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to deactivate: {str(e)}"
        }


# ============================================================================
# Scheduler Routes
# ============================================================================

@router.get("/scheduler", response_model=SchedulerStatusResponse)
async def get_scheduler_status(scheduler = Depends(get_scheduler)):
    """
    Get Scheduler status.
    
    Returns the current status of the Scheduler.
    """
    try:
        if not scheduler:
            # Return default status when scheduler is not initialized
            return SchedulerStatusResponse(
                is_active=False,
                is_paused=False,  # NEW: Include pause state in default response
                daily_published_count=0,
                queue_size=0,
                next_publish_time=None,
                statistics={},
                current_task=None,
                next_execution=None,
                last_execution=None,
                daily_limit=None
            )
        
        state = scheduler.state_manager.get_state()
        
        logger.info(f"Scheduler status requested - is_active: {state.is_active}, queue_size: {len(state.queue)}, daily_published: {state.daily_published_count}")
        
        # Determine current task based on state
        current_task = None
        if state.is_active and len(state.queue) > 0:
            current_task = f"Processing {len(state.queue)} articles in queue"
        elif state.is_active:
            current_task = "Waiting for articles"
        
        return SchedulerStatusResponse(
            is_active=state.is_active,
            is_paused=getattr(state, 'is_paused', False),  # NEW: Include pause state
            daily_published_count=state.daily_published_count,
            queue_size=len(state.queue),
            next_publish_time=state.next_publish_time,
            statistics=state.statistics,
            current_task=current_task,
            next_execution=state.next_publish_time,
            last_execution=None,  # Could be tracked in state if needed
            daily_limit=100  # Default, could be from config
        )
        
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {e}", exc_info=True)
        # Return safe defaults instead of failing
        return SchedulerStatusResponse(
            is_active=False,
            daily_published_count=0,
            queue_size=0,
            next_publish_time=None,
            statistics={},
            current_task=None,
            next_execution=None,
            last_execution=None,
            daily_limit=None
        )


@router.post("/scheduler/start")
async def start_scheduler(scheduler = Depends(get_scheduler)):
    """
    Start the Scheduler.
    """
    try:
        if not scheduler:
            return {
                "success": False,
                "message": "Scheduler not initialized"
            }

        if scheduler.is_running():
            return {
                "success": False,
                "message": "Scheduler is already running"
            }

        # Start the scheduler and wait for it to actually start
        import asyncio
        logger.info("Starting scheduler via API...")
        await scheduler.start()

        # Wait a moment and verify scheduler is actually running
        await asyncio.sleep(2.0)  # Wait 2 seconds to allow scheduler to initialize
        
        # Verify scheduler is running
        if not scheduler.is_running():
            logger.error("Scheduler failed to start - verification failed")
            return {
                "success": False,
                "message": "Scheduler failed to start - verification failed"
            }
        
        # Also verify state file if available
        try:
            state = scheduler.state_manager.get_state()
            if not state.is_active:
                logger.error("Scheduler state file shows not active after start")
                return {
                    "success": False,
                    "message": "Scheduler state verification failed"
                }
        except Exception as e:
            logger.warning(f"Could not verify scheduler state: {e}")

        logger.info("Scheduler started and verified successfully via API")

        return {
            "success": True,
            "message": "Scheduler started and verified"
        }

    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to start scheduler: {str(e)}"
        }


@router.post("/scheduler/pause")
async def pause_scheduler(scheduler = Depends(get_scheduler)):
    """
    Pause the Scheduler (preserves state for resume).
    """
    try:
        if not scheduler:
            return {
                "success": False,
                "message": "Scheduler not initialized"
            }

        if not scheduler.is_running():
            return {
                "success": False,
                "message": "Scheduler is not running"
            }

        if scheduler.is_paused():
            return {
                "success": False,
                "message": "Scheduler is already paused"
            }

        # Pause the scheduler (preserves state)
        logger.info("Pausing scheduler via API...")
        await scheduler.pause()

        # Wait a moment and verify scheduler is actually paused
        import asyncio
        await asyncio.sleep(1.0)  # Wait 1 second to allow scheduler to pause
        
        # Verify scheduler is paused
        if not scheduler.is_paused():
            logger.error("Scheduler failed to pause - verification failed")
            return {
                "success": False,
                "message": "Scheduler failed to pause - verification failed"
            }

        logger.info("Scheduler paused successfully via API")

        return {
            "success": True,
            "message": "Scheduler paused (state preserved for resume)"
        }

    except Exception as e:
        logger.error(f"Failed to pause scheduler: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to pause scheduler: {str(e)}"
        }


@router.post("/scheduler/resume")
async def resume_scheduler(scheduler = Depends(get_scheduler)):
    """
    Resume the Scheduler (from paused state).
    """
    try:
        if not scheduler:
            return {
                "success": False,
                "message": "Scheduler not initialized"
            }

        if scheduler.is_running():
            return {
                "success": False,
                "message": "Scheduler is already running"
            }

        if not scheduler.is_paused():
            return {
                "success": False,
                "message": "Scheduler is not paused (use start instead)"
            }

        # Resume the scheduler
        import asyncio
        logger.info("Resuming scheduler via API...")
        await scheduler.resume()

        # Wait a moment and verify scheduler is actually running
        await asyncio.sleep(2.0)  # Wait 2 seconds to allow scheduler to initialize
        
        # Verify scheduler is running
        if not scheduler.is_running():
            logger.error("Scheduler failed to resume - verification failed")
            return {
                "success": False,
                "message": "Scheduler failed to resume - verification failed"
            }
        
        # Also verify state file if available
        try:
            state = scheduler.state_manager.get_state()
            if not state.is_active or state.is_paused:
                logger.error("Scheduler state file shows not active or still paused after resume")
                return {
                    "success": False,
                    "message": "Scheduler state verification failed"
                }
        except Exception as e:
            logger.warning(f"Could not verify scheduler state: {e}")

        logger.info("Scheduler resumed and verified successfully via API")

        return {
            "success": True,
            "message": "Scheduler resumed from paused state"
        }

    except Exception as e:
        logger.error(f"Failed to resume scheduler: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to resume scheduler: {str(e)}"
        }


@router.post("/scheduler/stop")
async def stop_scheduler(scheduler = Depends(get_scheduler)):
    """
    Stop the Scheduler (terminates session, clears state).
    """
    try:
        if not scheduler:
            return {
                "success": False,
                "message": "Scheduler not initialized"
            }

        if not scheduler.is_running():
            return {
                "success": False,
                "message": "Scheduler is not running"
            }

        # Stop the scheduler (terminates session)
        logger.info("Stopping scheduler via API...")
        await scheduler.stop()

        # Wait a moment and verify scheduler is actually stopped
        import asyncio
        await asyncio.sleep(1.0)  # Wait 1 second to allow scheduler to stop
        
        # Verify scheduler is stopped
        if scheduler.is_running():
            logger.error("Scheduler failed to stop - still running")
            return {
                "success": False,
                "message": "Scheduler failed to stop - still running"
            }

        logger.info("Scheduler stopped successfully via API")

        return {
            "success": True,
            "message": "Scheduler stopped (session terminated)"
        }

    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to stop scheduler: {str(e)}"
        }


@router.get("/scheduler/config")
async def get_scheduler_config(scheduler = Depends(get_scheduler)):
    """
    Get Scheduler configuration.
    """
    try:
        if not scheduler:
            return {
                "success": False,
                "message": "Scheduler not initialized"
            }

        return {
            "success": True,
            "config": {
                "daily_limit": scheduler.config.daily_limit,
                "dry_run": scheduler.config.dry_run,
                "stop_on_empty_queue": scheduler.config.stop_on_empty_queue,
                "category": getattr(scheduler.config, 'category', None),
                "articles_to_process": getattr(scheduler.config, 'articles_to_process', None)
            }
        }

    except Exception as e:
        logger.error(f"Failed to get scheduler config: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to get scheduler config: {str(e)}"
        }


@router.post("/scheduler/config")
async def update_scheduler_config(
    request: SchedulerConfigRequest,
    scheduler = Depends(get_scheduler)
):
    """
    Update Scheduler configuration.
    """
    try:
        if not scheduler:
            return {
                "success": False,
                "message": "Scheduler not initialized"
            }

        # Update configuration
        if request.daily_limit is not None:
            scheduler.config.daily_limit = request.daily_limit
        if request.dry_run is not None:
            scheduler.config.dry_run = request.dry_run
        if request.working_hours_start is not None:
            scheduler.timing_manager.WORKING_HOUR_START = request.working_hours_start
        if request.working_hours_end is not None:
            scheduler.timing_manager.WORKING_HOUR_END = request.working_hours_end
        if request.category is not None:
            scheduler.config.category = request.category
        if request.articles_to_process is not None:
            scheduler.config.articles_to_process = request.articles_to_process

        logger.info(f"Scheduler configuration updated: {request.dict(exclude_unset=True)}")

        return {
            "success": True,
            "message": "Scheduler configuration updated"
        }

    except Exception as e:
        logger.error(f"Failed to update scheduler config: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to update scheduler config: {str(e)}"
        }


@router.post("/scheduler/run-manual")
async def run_manual_scheduler(
    request: ManualSchedulerRunRequest,
    scheduler = Depends(get_scheduler),
    automation_state = Depends(get_automation_state),
    kill_switch_manager = Depends(get_kill_switch)
):
    """
    Run automation orchestrator with current configuration - full workflow like Streamlit.
    This retrieves articles from Wikipedia, analyzes them, corrects them, and starts scheduler.
    
    Request body:
    - include_analyzed: bool - Include already analyzed articles (default: False)
    - lia_mode: bool - Use AI mode for analysis (default: False)
    """
    try:
        # Phase 4 FIX: Check global launch lock to prevent concurrent launches
        try:
            from backend.api.main import get_automation_launch_lock, set_automation_launch_lock
        except ImportError:
            logger.error("Failed to import launch lock functions")
            return {
                "success": False,
                "message": "Erreur de configuration du système de verrouillage"
            }
        
        if get_automation_launch_lock():
            logger.warning("Automation launch lock is already set, rejecting concurrent launch")
            return {
                "success": False,
                "message": "Une automatisation est déjà en cours de lancement. Veuillez attendre quelques secondes avant de réessayer."
            }
        
        # Set lock immediately to prevent race conditions
        set_automation_launch_lock(True)
        
        try:
            if not scheduler:
                return {
                    "success": False,
                    "message": "Scheduler not initialized"
                }

            # P1 CRITICAL FIX: Check if there's already an active automation session
            if automation_state:
                current_state = automation_state.get_state()
                if current_state and current_state.status in ['running', 'paused']:
                    logger.warning(f"Automation already active with status: {current_state.status}, session: {current_state.session_id}")
                    return {
                        "success": False,
                        "message": f"Une automatisation est déjà en cours (session: {current_state.session_id}, statut: {current_state.status}). Veuillez l'arrêter d'abord ou attendre qu'elle se termine."
                    }
            
            # Also check scheduler status
            if scheduler and scheduler.is_running():
                logger.warning("Scheduler is already running, cannot start new automation")
                return {
                    "success": False,
                    "message": "Le scheduler est déjà en cours d'exécution. Veuillez l'arrêter d'abord ou attendre qu'il se termine."
                }

            # Get configuration
            category = getattr(scheduler.config, 'category', None)
            articles_to_process = getattr(scheduler.config, 'articles_to_process', 10)
            dry_run = getattr(scheduler.config, 'dry_run', True)
            
            # Get options from request body
            include_analyzed = request.include_analyzed
            lia_mode = request.lia_mode

            logger.info(f"Manual automation run requested - Category: {category}, Articles: {articles_to_process}, Dry-run: {dry_run}, Include analyzed: {include_analyzed}, LIA mode: {lia_mode}")

            if not category:
                return {
                    "success": False,
                    "message": "Category not configured. Please configure a category first."
                }

            # Import AutomationOrchestrator for full workflow
            from wikipedia_maintenance.orchestrator.automation_orchestrator import AutomationOrchestrator
            import asyncio

            # Get site from scheduler config
            site = scheduler.config.site if scheduler.config.site else None
            if not site:
                import pywikibot
                site = pywikibot.Site('fr', 'wikipedia')
                logger.info("Created default site for automation")

            # Create AutomationOrchestrator with full workflow
            orchestrator = AutomationOrchestrator(
                lang='fr',
                family='wikipedia',
                category_name=category,
                max_articles=articles_to_process,
                dry_run=dry_run,
                lia_mode=lia_mode,  # Use AI mode if requested
                include_analyzed=include_analyzed,  # Include already analyzed articles if requested
                ai_provider="gemini",
                gemini_api_key=None,
                gemini_project_id=None,
                gemini_model='gemini-flash-lite-latest',
                ollama_url='http://localhost:11434',
                ollama_model='mistral:instruct',
                ollama_fallback='llama3:instruct',
                telegram_bot_token=None,
                telegram_admin_ids=[],
                # Reuse existing components from scheduler
                publisher=scheduler.publisher,
                published_tracker=scheduler.published_tracker,
                analyzed_tracker=scheduler.analyzed_tracker,
                # Pass kill switch manager for emergency stop
                kill_switch_manager=kill_switch_manager
            )

            # Set site for orchestrator
            orchestrator.site = site

            # Store orchestrator globally for pause/stop control
            from backend.api.main import set_automation_orchestrator
            set_automation_orchestrator(orchestrator)

            # Run automation as background task in FastAPI event loop
            async def run_automation_background():
                try:
                    logger.info("Starting automation orchestrator in background...")
                    await orchestrator.startup()
                    logger.info("Automation orchestrator completed successfully")
                except Exception as e:
                    logger.error(f"Automation failed: {e}", exc_info=True)
                finally:
                    # Release lock when automation completes or fails
                    set_automation_launch_lock(False)
                    logger.info("Automation launch lock released")

            # Create background task
            asyncio.create_task(run_automation_background())

            logger.info("Automation orchestrator started in background")

            return {
                "success": True,
                "message": f"Automation started: retrieving {articles_to_process} articles from category '{category}'"
            }
            
        except Exception as e:
            # Release lock on any error
            set_automation_launch_lock(False)
            raise e

    except Exception as e:
        logger.error(f"Failed to run automation: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to run automation: {str(e)}"
        }


# ============================================================================
# Automation Routes
# ============================================================================

@router.get("/automation", response_model=AutomationStatusResponse)
async def get_automation_status(automation_state = Depends(get_automation_state)):
    """
    Get Automation status.
    
    Returns the current status of the Automation Orchestrator.
    """
    try:
        if not automation_state:
            return AutomationStatusResponse(
                success=True,
                status="not_initialized",
                session_id="",
                current_step="No active automation session",
                articles_processed=0,
                articles_published=0,
                articles_error=0,
                category_name="",
                started_at="",
                article_states=[]
            )
        
        state = automation_state.get_state()
        
        if not state:
            return AutomationStatusResponse(
                success=True,
                status="not_initialized",
                session_id="",
                current_step="No active automation session",
                articles_processed=0,
                articles_published=0,
                articles_error=0,
                category_name="",
                started_at="",
                article_states=[]
            )
        
        # Extract article states for articles currently being processed
        article_states = []
        if state.article_states:
            for article_dict in state.article_states:
                article_states.append({
                    "title": article_dict.get("title"),
                    "status": article_dict.get("status"),
                    "progress": article_dict.get("progress"),
                    "current_step": article_dict.get("current_step"),
                    "started_at": article_dict.get("started_at"),
                    "elapsed_time_seconds": article_dict.get("elapsed_time_seconds")
                })
        
        return AutomationStatusResponse(
            success=True,
            status=state.status,
            session_id=state.session_id,
            current_step=state.current_step,
            articles_processed=state.articles_processed,
            articles_published=state.articles_published,
            articles_error=state.articles_error,
            category_name=state.category_name,
            started_at=state.started_at,
            article_states=article_states
        )
        
    except Exception as e:
        logger.error(f"Failed to get automation status: {e}", exc_info=True)
        # Return safe defaults instead of failing
        return AutomationStatusResponse(
            success=True,
            status="error",
            session_id="",
            current_step=f"Failed to get automation status: {str(e)}",
            articles_processed=0,
            articles_published=0,
            articles_error=0,
            category_name="",
            started_at="",
            article_states=[]
        )


@router.post("/automation/pause")
async def pause_automation(automation_orchestrator = Depends(get_automation_orchestrator)):
    """
    Pause the active automation orchestrator.
    """
    try:
        if not automation_orchestrator:
            return {
                "success": False,
                "message": "No active automation orchestrator"
            }
        
        result = automation_orchestrator.pause()
        if result:
            return {
                "success": True,
                "message": "Automation paused successfully"
            }
        else:
            return {
                "success": False,
                "message": "Automation is already paused"
            }
    except Exception as e:
        logger.error(f"Failed to pause automation: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to pause automation: {str(e)}"
        }


@router.post("/automation/resume")
async def resume_automation(automation_orchestrator = Depends(get_automation_orchestrator)):
    """
    Resume the paused automation orchestrator.
    
    P2-1 FIX: Now properly calls async resume() method which can restore interrupted sessions.
    """
    try:
        if not automation_orchestrator:
            return {
                "success": False,
                "message": "No active automation orchestrator"
            }
        
        result = await automation_orchestrator.resume()
        if result:
            return {
                "success": True,
                "message": "Automation resumed successfully"
            }
        else:
            return {
                "success": False,
                "message": "Automation is not paused or no session to resume"
            }
    except Exception as e:
        logger.error(f"Failed to resume automation: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to resume automation: {str(e)}"
        }


@router.post("/automation/stop")
async def stop_automation(automation_orchestrator = Depends(get_automation_orchestrator)):
    """
    Stop the active automation orchestrator.
    """
    try:
        if not automation_orchestrator:
            return {
                "success": False,
                "message": "No active automation orchestrator"
            }
        
        result = automation_orchestrator.stop()
        if result:
            return {
                "success": True,
                "message": "Automation stopped successfully"
            }
        else:
            return {
                "success": False,
                "message": "Automation is already stopped"
            }
    except Exception as e:
        logger.error(f"Failed to stop automation: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to stop automation: {str(e)}"
        }
