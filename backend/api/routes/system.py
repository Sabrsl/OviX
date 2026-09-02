"""
OVIX Backend API - System Routes

Handles system-level operations like Kill Switch and Scheduler control.
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
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


class KillSwitchDeactivateRequest(BaseModel):
    """Kill switch deactivate request with confirmation."""
    reason: str
    confirmation: str  # Must match "CONFIRM_RESUME" exactly
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
    # Enhanced tracking fields (like article_scheduler)
    session_id: Optional[str] = None
    total_articles: int = 0
    processed_articles: int = 0
    current_article: Optional[str] = None
    current_step: Optional[str] = None
    progress_percentage: float = 0.0
    articles_analyzed: int = 0
    articles_corrected: int = 0
    articles_error: int = 0
    started_at: Optional[str] = None
    estimated_completion: Optional[str] = None


class SchedulerActionRequest(BaseModel):
    """Scheduler action request."""
    action: str  # "start", "pause", "resume", "stop"


class SchedulerActionResponse(BaseModel):
    """Response for scheduler actions (start, pause, resume, stop)."""
    success: bool
    message: str
    session_id: Optional[str] = None
    status: Optional[SchedulerStatusResponse] = None


def _create_default_scheduler_status() -> SchedulerStatusResponse:
    """Create a default scheduler status for error responses."""
    return SchedulerStatusResponse(
        is_active=False,
        is_paused=False,
        daily_published_count=0,
        queue_size=0,
        next_publish_time=None,
        statistics=None,
        current_task=None,
        next_execution=None,
        last_execution=None,
        daily_limit=100,
        session_id=None,
        total_articles=0,
        processed_articles=0,
        current_article=None,
        current_step=None,
        progress_percentage=0.0,
        articles_analyzed=0,
        articles_corrected=0,
        articles_error=0,
        started_at=None,
        estimated_completion=None
    )


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


class TalkPageKillSwitchRequest(BaseModel):
    """Request for kill switch activation via talk page token."""
    token_id: str
    token: str
    action: str  # "stop" or "resume"
    reason: str = "Emergency stop from Wikipedia talk page"


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


def get_automation_lock():
    """Get database automation lock manager."""
    try:
        from backend.api.main import get_automation_lock
        return get_automation_lock()
    except Exception as e:
        logger.warning(f"Automation lock manager not initialized: {e}")
        return None


def get_automation_orchestrator():
    """Get active automation orchestrator."""
    try:
        from backend.api.main import get_automation_orchestrator
        return get_automation_orchestrator()
    except Exception as e:
        logger.warning(f"Automation orchestrator not initialized: {e}")
        return None


def get_event_manager():
    """Get event manager."""
    try:
        from wikipedia_maintenance.utils.event_manager import get_event_manager
        return get_event_manager()
    except Exception as e:
        logger.warning(f"Event manager not initialized: {e}")
        return None


def get_wikipedia_session():
    """Get Wikipedia session."""
    from backend.api.routes.auth import get_wikipedia_session as get_session
    return get_session()


def require_authenticated_user():
    """
    Dependency that ensures the user is authenticated before allowing access.
    
    Returns the authenticated username if valid, raises HTTPException otherwise.
    
    SECURITY: This must be used on all sensitive endpoints (kill switch, etc.)
    """
    from backend.api.routes.auth import get_wikipedia_session
    from fastapi import HTTPException, status
    
    session = get_wikipedia_session()
    
    if not session.get("authenticated"):
        logger.warning("Attempted to access protected endpoint without authentication")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please login via /api/auth/login"
        )
    
    username = session.get("username")
    if not username:
        logger.warning("Authenticated session has no username")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication state"
        )
    
    return username


def require_authorized_operator():
    """
    Dependency that ensures the user is both authenticated AND authorized.
    
    Returns the authenticated username if authorized, raises HTTPException otherwise.
    
    SECURITY: This must be used on RESUME operations to ensure only authorized
    operators can restart the bot after a kill switch activation.
    
    Authorized operators can be configured via environment variable:
    OVIX_AUTHORIZED_OPERATORS (comma-separated list of Wikipedia usernames)
    """
    from fastapi import HTTPException, status
    import os
    
    # First check authentication
    username = require_authenticated_user()
    
    # Check if user is in authorized operators list
    authorized_operators_str = os.getenv("OVIX_AUTHORIZED_OPERATORS", "")
    authorized_operators = [op.strip() for op in authorized_operators_str.split(",") if op.strip()]
    
    # If no operators configured, allow any authenticated user (fallback for development)
    if not authorized_operators:
        logger.warning(
            f"No authorized operators configured in OVIX_AUTHORIZED_OPERATORS. "
            f"Allowing authenticated user {username} for RESUME operation. "
            f"Configure this in production!"
        )
        return username
    
    # Check if user is authorized
    if username not in authorized_operators:
        logger.warning(
            f"Unauthorized RESUME attempt by {username}. "
            f"Authorized operators: {authorized_operators}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"User '{username}' is not authorized to perform RESUME operations. "
                f"Authorized operators: {', '.join(authorized_operators)}"
            )
        )
    
    logger.info(f"Authorized operator {username} verified for RESUME operation")
    return username


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
                "queue_size": sched_state.queue_size if sched_state else 0,
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
    kill_switch = Depends(get_kill_switch),
    username: str = Depends(require_authenticated_user)
):
    """
    Activate the Kill Switch.

    This will stop all automated operations.
    
    SECURITY: Requires Wikipedia authentication via require_authenticated_user dependency.
    """
    try:
        if not kill_switch:
            return {
                "success": False,
                "message": "Kill switch manager not initialized"
            }

        from wikipedia_maintenance.utils.kill_switch_manager import KillSwitchTrigger

        kill_switch.enable(
            reason=request.reason,
            trigger_source=KillSwitchTrigger.MANUAL,
            requested_by=username
        )

        logger.warning(f"🛑 Kill Switch activated by authenticated user {username}: {request.reason}")

        return {
            "success": True,
            "message": "Kill Switch activated",
            "reason": request.reason,
            "requested_by": username
        }

    except Exception as e:
        logger.error(f"Failed to activate kill switch: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to activate: {str(e)}"
        }


@router.post("/kill-switch/deactivate")
async def deactivate_kill_switch(
    request: KillSwitchDeactivateRequest,
    kill_switch = Depends(get_kill_switch),
    username: str = Depends(require_authorized_operator)
):
    """
    Deactivate the Kill Switch.

    This will allow automated operations to resume.
    
    SECURITY: 
    - Requires Wikipedia authentication AND authorization via require_authorized_operator dependency
    - Requires explicit confirmation ("CONFIRM_RESUME") to prevent accidental resume
    - Only authorized operators (configured via OVIX_AUTHORIZED_OPERATORS) can resume
    """
    try:
        if not kill_switch:
            return {
                "success": False,
                "message": "Kill switch manager not initialized"
            }

        # SECURITY: Require explicit confirmation
        if request.confirmation != "CONFIRM_RESUME":
            logger.warning(f"Kill switch deactivation attempted by authorized operator {username} with invalid confirmation: '{request.confirmation}'")
            return {
                "success": False,
                "message": "Invalid confirmation. Must use 'CONFIRM_RESUME' to prevent accidental resume."
            }

        kill_switch.disable(
            reason=request.reason,
            requested_by=username
        )

        logger.warning(f"✅ Kill Switch DEACTIVATED by authorized operator {username} with confirmation: {request.reason}")

        return {
            "success": True,
            "message": "Kill Switch deactivated",
            "reason": request.reason,
            "requested_by": username
        }

    except Exception as e:
        logger.error(f"Failed to deactivate kill switch: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to deactivate: {str(e)}"
        }


@router.post("/kill-switch/talk-page-activate")
async def talk_page_kill_switch_activate(
    request: TalkPageKillSwitchRequest,
    kill_switch = Depends(get_kill_switch)
):
    """
    Activate/Deactivate Kill Switch via secure Wikipedia talk page token.
    
    This endpoint provides secure emergency control from Wikipedia discussion pages
    using one-time-use tokens to prevent unauthorized access.
    
    SECURITY: Token is in POST body (not URL) to prevent leakage in logs/analytics.
    
    Security features:
    - Requires valid one-time-use token
    - Tokens expire after 24 hours
    - Tokens are consumed after use
    - All actions are logged
    - STOP only: RESUME requires dashboard authentication for safety
    """
    try:
        if not kill_switch:
            return {
                "success": False,
                "message": "Kill switch manager not initialized"
            }

        # SECURITY: Only allow STOP action via talk page for safety
        # RESUME must go through authenticated dashboard endpoint
        if request.action == "resume":
            logger.warning("Resume action attempted via talk page token - blocked for security")
            return {
                "success": False,
                "message": "RESUME via talk page is not allowed for security. Use the authenticated dashboard endpoint with confirmation."
            }

        # Get token manager
        from wikipedia_maintenance.utils.talk_page_tokens import (
            get_token_manager, 
            TokenType, 
            TokenStatus
        )
        
        token_manager = get_token_manager()
        
        # Validate token
        status, token_info = token_manager.validate_token(
            request.token_id, 
            request.token
        )
        
        if status != TokenStatus.VALID:
            if status == TokenStatus.USED:
                return {
                    "success": False,
                    "message": "Token already used. Please generate a new token."
                }
            elif status == TokenStatus.EXPIRED:
                return {
                    "success": False,
                    "message": "Token expired. Please generate a new token."
                }
            else:
                return {
                    "success": False,
                    "message": "Invalid token."
                }
        
        # Check if token type matches action (must be EMERGENCY_STOP)
        if token_info.token_type != TokenType.EMERGENCY_STOP:
            return {
                "success": False,
                "message": f"Token type mismatch. Only EMERGENCY_STOP tokens are allowed via talk page."
            }
        
        # Execute the STOP action only
        from wikipedia_maintenance.utils.kill_switch_manager import KillSwitchTrigger
        
        if request.action == "stop":
            kill_switch.enable(
                reason=request.reason,
                trigger_source=KillSwitchTrigger.TALK_PAGE,
                requested_by=token_info.requested_by
            )
            logger.warning(f"🛑 Kill Switch activated via talk page token by {token_info.requested_by}")
        else:
            return {
                "success": False,
                "message": f"Invalid action: {request.action}. Only 'stop' is allowed via talk page."
            }
        
        # Mark token as used (consume it)
        success, _ = token_manager.use_token(request.token_id, request.token)
        
        if not success:
            logger.warning(f"Failed to mark token {request.token_id} as used, but action completed")
        
        return {
            "success": True,
            "message": "Kill Switch STOPPED successfully via talk page",
            "action": request.action,
            "requested_by": token_info.requested_by
        }
        
    except Exception as e:
        logger.error(f"Failed to process talk page kill switch activation: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to process request: {str(e)}"
        }


# ============================================================================
# Scheduler Routes
# ============================================================================

@router.get("/scheduler", response_model=SchedulerStatusResponse)
async def get_scheduler_status(scheduler = Depends(get_scheduler)):
    """
    Get Scheduler status.
    
    Returns the current status of the Scheduler with enhanced tracking.
    """
    try:
        if not scheduler:
            # Return default status when scheduler is not initialized
            return SchedulerStatusResponse(
                is_active=False,
                is_paused=False,
                daily_published_count=0,
                queue_size=0,
                next_publish_time=None,
                statistics={},
                current_task=None,
                next_execution=None,
                last_execution=None,
                daily_limit=None,
                # Enhanced tracking fields
                session_id=None,
                total_articles=0,
                processed_articles=0,
                current_article=None,
                current_step=None,
                progress_percentage=0.0,
                articles_analyzed=0,
                articles_corrected=0,
                articles_error=0,
                started_at=None,
                estimated_completion=None
            )
        
        state = scheduler.state_manager.get_state()
        queue_size = scheduler.state_manager.get_queue_size()
        
        logger.info(f"Scheduler status requested - is_active: {state.is_active}, queue_size: {queue_size}, daily_published: {state.daily_published_count}")
        
        # Determine current task based on state
        current_task = None
        if state.is_active and queue_size > 0:
            current_task = f"Processing {queue_size} articles in queue"
        elif state.is_active:
            current_task = "Waiting for articles"
        
        # Calculate progress percentage
        progress_percentage = 0.0
        total_articles = queue_size + state.daily_published_count
        if total_articles > 0:
            progress_percentage = (state.daily_published_count / total_articles) * 100
        
        return SchedulerStatusResponse(
            is_active=state.is_active,
            is_paused=getattr(state, 'is_paused', False),
            daily_published_count=state.daily_published_count,
            queue_size=queue_size,
            next_publish_time=state.next_publish_time,
            statistics=state.statistics,
            current_task=current_task,
            next_execution=state.next_publish_time,
            last_execution=None,
            daily_limit=getattr(scheduler.config, 'daily_limit', 100),
            # Enhanced tracking fields
            session_id=getattr(state, 'session_id', None),
            total_articles=total_articles,
            processed_articles=state.daily_published_count,
            current_article=getattr(state, 'current_article', None),
            current_step=getattr(state, 'current_step', None),
            progress_percentage=progress_percentage,
            articles_analyzed=getattr(state, 'articles_analyzed', 0),
            articles_corrected=getattr(state, 'articles_corrected', 0),
            articles_error=getattr(state, 'articles_error', 0),
            started_at=getattr(state, 'started_at', None),
            estimated_completion=getattr(state, 'estimated_completion', None)
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
            daily_limit=None,
            # Enhanced tracking fields
            session_id=None,
            total_articles=0,
            processed_articles=0,
            current_article=None,
            current_step=None,
            progress_percentage=0.0,
            articles_analyzed=0,
            articles_corrected=0,
            articles_error=0,
            started_at=None,
            estimated_completion=None
        )


@router.post("/scheduler/start", response_model=SchedulerActionResponse)
async def start_scheduler(
    scheduler = Depends(get_scheduler),
    automation_lock = Depends(get_automation_lock),
    event_manager = Depends(get_event_manager)
):
    """
    Start the Scheduler with enhanced tracking.
    """
    try:
        if not scheduler:
            return SchedulerActionResponse(
                success=False,
                message="Scheduler not initialized",
                status=_create_default_scheduler_status()
            )

        if not automation_lock:
            logger.error("Automation lock manager not available")
            return SchedulerActionResponse(
                success=False,
                message="Erreur de configuration du système de verrouillage",
                status=_create_default_scheduler_status()
            )

        # Generate unique session ID for this scheduler start attempt
        import uuid
        session_id = f"scheduler_{uuid.uuid4().hex[:8]}"

        # Attempt to acquire the lock to prevent concurrent scheduler starts
        lock_acquired = automation_lock.acquire_automation_lock(
            session_id=session_id,
            locked_by="api",
            automation_type="scheduler"
        )

        if not lock_acquired:
            lock_status = automation_lock.get_automation_lock_status()
            logger.warning(f"Scheduler start blocked - automation lock already held by session {lock_status.get('session_id')}")
            return SchedulerActionResponse(
                success=False,
                message=f"Une automatisation est déjà en cours (session: {lock_status.get('session_id')}). Veuillez l'arrêter d'abord ou attendre qu'elle se termine.",
                status=_create_default_scheduler_status()
            )

        try:
            if scheduler.is_running():
                # Release lock if scheduler is already running
                automation_lock.release_automation_lock(session_id)
                return SchedulerActionResponse(
                    success=False,
                    message="Scheduler is already running",
                    status=_create_default_scheduler_status()
                )

            # Initialize enhanced tracking in state
            state = scheduler.state_manager.get_state()
            state.session_id = session_id
            state.started_at = datetime.now().isoformat()
            state.articles_analyzed = 0
            state.articles_corrected = 0
            state.articles_error = 0
            state.current_article = None
            state.current_step = "Starting"
            scheduler.state_manager.save_state()

            # Emit scheduler start event
            if event_manager:
                try:
                    from wikipedia_maintenance.utils.event_manager import EventType
                    await event_manager.emit(
                        EventType.AUTOMATION_STARTED,
                        {
                            "session_id": session_id,
                            "automation_type": "scheduler",
                            "started_at": state.started_at
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit scheduler start event: {e}")

            # Start the scheduler and wait for it to actually start
            import asyncio
            logger.info("Starting scheduler via API...")
            await scheduler.start()

            # Wait a moment and verify scheduler is actually running
            await asyncio.sleep(2.0)  # Wait 2 seconds to allow scheduler to initialize

            # Verify scheduler is running
            if not scheduler.is_running():
                logger.error("Scheduler failed to start - verification failed")
                # Release lock on failure
                automation_lock.release_automation_lock(session_id)
                return SchedulerActionResponse(
                    success=False,
                    message="Scheduler failed to start - verification failed"
                )

            # Also verify state file if available
            try:
                state = scheduler.state_manager.get_state()
                if not state.is_active:
                    logger.error("Scheduler state file shows not active after start")
                    # Release lock on failure
                    automation_lock.release_automation_lock(session_id)
                    return SchedulerActionResponse(
                        success=False,
                        message="Scheduler state verification failed"
                    )
            except Exception as e:
                logger.warning(f"Could not verify scheduler state: {e}")

            # Update state to reflect successful start
            state.current_step = "Running"
            scheduler.state_manager.save_state()

            logger.info("Scheduler started and verified successfully via API")

            # Note: We keep the lock acquired while scheduler is running
            # The lock will be released when scheduler is stopped

            # Get current status for response
            status = scheduler.state_manager.get_state()
            return SchedulerActionResponse(
                success=True,
                message="Scheduler started and verified",
                session_id=session_id,
                status=SchedulerStatusResponse(
                    is_active=status.is_active,
                    is_paused=getattr(status, 'is_paused', False),
                    daily_published_count=status.daily_published_count,
                    queue_size=len(status.queue),
                    next_publish_time=status.next_publish_time,
                    statistics=status.statistics,
                    current_task=f"Processing {len(status.queue)} articles in queue" if len(status.queue) > 0 else "Waiting for articles",
                    next_execution=status.next_publish_time,
                    last_execution=None,
                    daily_limit=getattr(scheduler.config, 'daily_limit', 100),
                    session_id=getattr(status, 'session_id', None),
                    total_articles=len(status.queue) + status.daily_published_count,
                    processed_articles=status.daily_published_count,
                    current_article=getattr(status, 'current_article', None),
                    current_step=getattr(status, 'current_step', None),
                    progress_percentage=(status.daily_published_count / (len(status.queue) + status.daily_published_count)) * 100 if (len(status.queue) + status.daily_published_count) > 0 else 0.0,
                    articles_analyzed=getattr(status, 'articles_analyzed', 0),
                    articles_corrected=getattr(status, 'articles_corrected', 0),
                    articles_error=getattr(status, 'articles_error', 0),
                    started_at=getattr(status, 'started_at', None),
                    estimated_completion=getattr(status, 'estimated_completion', None)
                )
            )

        except Exception as e:
            # Release lock on any error
            automation_lock.release_automation_lock(session_id)
            logger.error(f"Failed to start scheduler: {e}", exc_info=True)
            return SchedulerActionResponse(
                success=False,
                message=f"Failed to start scheduler: {str(e)}",
                status=_create_default_scheduler_status()
            )

    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        return SchedulerActionResponse(
            success=False,
            message=f"Failed to start scheduler: {str(e)}",
            status=_create_default_scheduler_status()
        )


@router.post("/scheduler/pause", response_model=SchedulerActionResponse)
async def pause_scheduler(
    scheduler = Depends(get_scheduler),
    event_manager = Depends(get_event_manager)
):
    """
    Pause the Scheduler (preserves state for resume) with event emission.
    """
    try:
        if not scheduler:
            return SchedulerActionResponse(
                success=False,
                message="Scheduler not initialized",
                status=_create_default_scheduler_status()
            )

        if not scheduler.is_running():
            return SchedulerActionResponse(
                success=False,
                message="Scheduler is not running",
                status=_create_default_scheduler_status()
            )

        if scheduler.is_paused():
            return SchedulerActionResponse(
                success=False,
                message="Scheduler is already paused",
                status=_create_default_scheduler_status()
            )

        # Update state before pausing
        state = scheduler.state_manager.get_state()
        state.current_step = "Pausing"
        scheduler.state_manager.save_state()

        # Pause the scheduler (preserves state)
        logger.info("Pausing scheduler via API...")
        await scheduler.pause()

        # Wait a moment and verify scheduler is actually paused
        import asyncio
        await asyncio.sleep(1.0)  # Wait 1 second to allow scheduler to pause
        
        # Verify scheduler is paused
        if not scheduler.is_paused():
            logger.error("Scheduler failed to pause - verification failed")
            return SchedulerActionResponse(
                success=False,
                message="Scheduler failed to pause - verification failed",
                status=_create_default_scheduler_status()
            )

        # Update state after successful pause
        state.current_step = "Paused"
        scheduler.state_manager.save_state()

        # Emit pause event
        if event_manager:
            try:
                from wikipedia_maintenance.utils.event_manager import EventType
                await event_manager.emit(
                    EventType.AUTOMATION_PAUSED,
                    {
                        "session_id": getattr(state, 'session_id', None),
                        "automation_type": "scheduler"
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to emit scheduler pause event: {e}")

        logger.info("Scheduler paused successfully via API")

        # Get current status for response
        status = scheduler.state_manager.get_state()
        return SchedulerActionResponse(
            success=True,
            message="Scheduler paused (state preserved for resume)",
            session_id=getattr(status, 'session_id', None),
            status=SchedulerStatusResponse(
                is_active=status.is_active,
                is_paused=getattr(status, 'is_paused', False),
                daily_published_count=status.daily_published_count,
                queue_size=len(status.queue),
                next_publish_time=status.next_publish_time,
                statistics=status.statistics,
                current_task=f"Processing {len(status.queue)} articles in queue" if len(status.queue) > 0 else "Waiting for articles",
                next_execution=status.next_publish_time,
                last_execution=None,
                daily_limit=getattr(scheduler.config, 'daily_limit', 100),
                session_id=getattr(status, 'session_id', None),
                total_articles=len(status.queue) + status.daily_published_count,
                processed_articles=status.daily_published_count,
                current_article=getattr(status, 'current_article', None),
                current_step=getattr(status, 'current_step', None),
                progress_percentage=(status.daily_published_count / (len(status.queue) + status.daily_published_count)) * 100 if (len(status.queue) + status.daily_published_count) > 0 else 0.0,
                articles_analyzed=getattr(status, 'articles_analyzed', 0),
                articles_corrected=getattr(status, 'articles_corrected', 0),
                articles_error=getattr(status, 'articles_error', 0),
                started_at=getattr(status, 'started_at', None),
                estimated_completion=getattr(status, 'estimated_completion', None)
            )
        )

    except Exception as e:
        logger.error(f"Failed to pause scheduler: {e}", exc_info=True)
        return SchedulerActionResponse(
            success=False,
            message=f"Failed to pause scheduler: {str(e)}",
            status=_create_default_scheduler_status()
        )


@router.post("/scheduler/resume", response_model=SchedulerActionResponse)
async def resume_scheduler(
    scheduler = Depends(get_scheduler),
    event_manager = Depends(get_event_manager)
):
    """
    Resume the Scheduler (from paused state) or start if not running with event emission.
    """
    try:
        if not scheduler:
            return SchedulerActionResponse(
                success=False,
                message="Scheduler not initialized",
                status=_create_default_scheduler_status()
            )

        if scheduler.is_running():
            return SchedulerActionResponse(
                success=False,
                message="Scheduler is already running",
                status=_create_default_scheduler_status()
            )

        # Update state before resuming
        state = scheduler.state_manager.get_state()
        logger.info(f"Before resume - is_running: {scheduler.is_running()}, is_paused: {scheduler.is_paused()}")
        state.current_step = "Resuming"
        scheduler.state_manager.save_state()

        # Resume the scheduler
        import asyncio
        logger.info("Resuming scheduler via API...")
        await scheduler.resume()

        logger.info(f"After resume - is_running: {scheduler.is_running()}, is_paused: {scheduler.is_paused()}")

        # Wait a moment and verify scheduler is actually running
        await asyncio.sleep(2.0)  # Wait 2 seconds to allow scheduler to initialize
        
        # Verify scheduler is running
        if not scheduler.is_running():
            logger.error("Scheduler failed to resume - verification failed")
            return SchedulerActionResponse(
                success=False,
                message="Scheduler failed to resume - verification failed",
                status=_create_default_scheduler_status()
            )
        
        # Also verify state file if available
        try:
            state = scheduler.state_manager.get_state()
            if not state.is_active or state.is_paused:
                logger.error("Scheduler state file shows not active or still paused after resume")
                return SchedulerActionResponse(
                    success=False,
                    message="Scheduler state verification failed",
                    status=_create_default_scheduler_status()
                )
        except Exception as e:
            logger.warning(f"Could not verify scheduler state: {e}")

        # Update state after successful resume
        state.current_step = "Running"
        scheduler.state_manager.save_state()

        # Emit resume event
        if event_manager:
            try:
                from wikipedia_maintenance.utils.event_manager import EventType
                await event_manager.emit(
                    EventType.AUTOMATION_RESUMED,
                    {
                        "session_id": getattr(state, 'session_id', None),
                        "automation_type": "scheduler"
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to emit scheduler resume event: {e}")

        logger.info("Scheduler resumed and verified successfully via API")

        # Get current status for response
        status = scheduler.state_manager.get_state()
        return SchedulerActionResponse(
            success=True,
            message="Scheduler resumed from paused state",
            session_id=getattr(status, 'session_id', None),
            status=SchedulerStatusResponse(
                is_active=status.is_active,
                is_paused=getattr(status, 'is_paused', False),
                daily_published_count=status.daily_published_count,
                queue_size=len(status.queue),
                next_publish_time=status.next_publish_time,
                statistics=status.statistics,
                current_task=f"Processing {len(status.queue)} articles in queue" if len(status.queue) > 0 else "Waiting for articles",
                next_execution=status.next_publish_time,
                last_execution=None,
                daily_limit=getattr(scheduler.config, 'daily_limit', 100),
                session_id=getattr(status, 'session_id', None),
                total_articles=len(status.queue) + status.daily_published_count,
                processed_articles=status.daily_published_count,
                current_article=getattr(status, 'current_article', None),
                current_step=getattr(status, 'current_step', None),
                progress_percentage=(status.daily_published_count / (len(status.queue) + status.daily_published_count)) * 100 if (len(status.queue) + status.daily_published_count) > 0 else 0.0,
                articles_analyzed=getattr(status, 'articles_analyzed', 0),
                articles_corrected=getattr(status, 'articles_corrected', 0),
                articles_error=getattr(status, 'articles_error', 0),
                started_at=getattr(status, 'started_at', None),
                estimated_completion=getattr(status, 'estimated_completion', None)
            )
        )

    except Exception as e:
        logger.error(f"Failed to resume scheduler: {e}", exc_info=True)
        return SchedulerActionResponse(
            success=False,
            message=f"Failed to resume scheduler: {str(e)}"
        )


@router.post("/scheduler/stop", response_model=SchedulerActionResponse)
async def stop_scheduler(
    scheduler = Depends(get_scheduler),
    automation_lock = Depends(get_automation_lock),
    event_manager = Depends(get_event_manager)
):
    """
    Stop the Scheduler (terminates session, clears state) with event emission.
    """
    try:
        if not scheduler:
            return SchedulerActionResponse(
                success=False,
                message="Scheduler not initialized",
                status=_create_default_scheduler_status()
            )

        if not scheduler.is_running():
            return SchedulerActionResponse(
                success=False,
                message="Scheduler is not running",
                status=_create_default_scheduler_status()
            )

        # Get session ID before stopping
        state = scheduler.state_manager.get_state()
        session_id = getattr(state, 'session_id', None)

        # Update state before stopping
        state.current_step = "Stopping"
        scheduler.state_manager.save_state()

        # Stop the scheduler (terminates session)
        logger.info("Stopping scheduler via API...")
        await scheduler.stop()

        # Wait a moment and verify scheduler is actually stopped
        import asyncio
        await asyncio.sleep(1.0)  # Wait 1 second to allow scheduler to stop

        # Verify scheduler is stopped
        if scheduler.is_running():
            logger.error("Scheduler failed to stop - still running")
            return SchedulerActionResponse(
                success=False,
                message="Scheduler failed to stop - still running"
            )

        # Update state after successful stop
        state.current_step = "Stopped"
        state.is_active = False
        state.is_paused = False
        scheduler.state_manager.save_state()

        # Emit stop event
        if event_manager:
            try:
                from wikipedia_maintenance.utils.event_manager import EventType
                await event_manager.emit(
                    EventType.AUTOMATION_STOPPED,
                    {
                        "session_id": session_id,
                        "automation_type": "scheduler",
                        "status": "stopped"
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to emit scheduler stop event: {e}")

        logger.info("Scheduler stopped successfully via API")

        # Release the automation lock since scheduler is no longer running
        if automation_lock:
            try:
                lock_status = automation_lock.get_automation_lock_status()
                if lock_status.get('locked'):
                    lock_session_id = lock_status.get('session_id')
                    if lock_session_id and lock_session_id.startswith('scheduler_'):
                        automation_lock.release_automation_lock(lock_session_id)
                        logger.info(f"Released automation lock for scheduler session {lock_session_id}")
            except Exception as e:
                logger.warning(f"Failed to release automation lock: {e}")

        # Get current status for response
        status = scheduler.state_manager.get_state()
        return SchedulerActionResponse(
            success=True,
            message="Scheduler stopped (session terminated)",
            session_id=session_id,
            status=SchedulerStatusResponse(
                is_active=status.is_active,
                is_paused=getattr(status, 'is_paused', False),
                daily_published_count=status.daily_published_count,
                queue_size=len(status.queue),
                next_publish_time=status.next_publish_time,
                statistics=status.statistics,
                current_task="Stopped",
                next_execution=None,
                last_execution=None,
                daily_limit=getattr(scheduler.config, 'daily_limit', 100),
                session_id=getattr(status, 'session_id', None),
                total_articles=len(status.queue) + status.daily_published_count,
                processed_articles=status.daily_published_count,
                current_article=getattr(status, 'current_article', None),
                current_step=getattr(status, 'current_step', None),
                progress_percentage=(status.daily_published_count / (len(status.queue) + status.daily_published_count)) * 100 if (len(status.queue) + status.daily_published_count) > 0 else 0.0,
                articles_analyzed=getattr(status, 'articles_analyzed', 0),
                articles_corrected=getattr(status, 'articles_corrected', 0),
                articles_error=getattr(status, 'articles_error', 0),
                started_at=getattr(status, 'started_at', None),
                estimated_completion=getattr(status, 'estimated_completion', None)
            )
        )

    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}", exc_info=True)
        return SchedulerActionResponse(
            success=False,
            message=f"Failed to stop scheduler: {str(e)}"
        )


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
    kill_switch_manager = Depends(get_kill_switch),
    automation_lock = Depends(get_automation_lock)
):
    """
    Run automation orchestrator with current configuration - full workflow like Streamlit.
    This retrieves articles from Wikipedia, analyzes them, corrects them, and starts scheduler.
    
    Request body:
    - include_analyzed: bool - Include already analyzed articles (default: False)
    - lia_mode: bool - Use AI mode for analysis (default: False)
    """
    try:
        # Generate unique session ID for this automation attempt
        import uuid
        session_id = f"automation_{uuid.uuid4().hex[:8]}"
        
        # P1 CRITICAL FIX: Use database lock to prevent concurrent launches
        if not automation_lock:
            logger.error("Automation lock manager not available")
            return {
                "success": False,
                "message": "Erreur de configuration du système de verrouillage"
            }
        
        # Attempt to acquire the lock
        lock_acquired = automation_lock.acquire_automation_lock(
            session_id=session_id,
            locked_by="api",
            automation_type="manual"
        )
        
        if not lock_acquired:
            lock_status = automation_lock.get_automation_lock_status()
            logger.warning(f"Automation lock already held by session {lock_status.get('session_id')}")
            return {
                "success": False,
                "message": f"Une automatisation est déjà en cours (session: {lock_status.get('session_id')}). Veuillez l'arrêter d'abord ou attendre qu'elle se termine."
            }
        
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

        logger.info(f"Manual automation run requested - Category: {category}, Articles: {articles_to_process}, Dry-run: {dry_run}, Include analyzed: {include_analyzed}, LIA mode: {lia_mode}, Session: {session_id}")

        if not category:
            # Release lock before returning error
            automation_lock.release_automation_lock(session_id)
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

        # Store session ID in orchestrator for lock release
        orchestrator.session_id = session_id

        # Run automation as background task in FastAPI event loop
        async def run_automation_background():
            try:
                logger.info(f"Starting automation orchestrator in background (session: {session_id})...")
                await orchestrator.startup()
                logger.info(f"Automation orchestrator completed successfully (session: {session_id})")
            except Exception as e:
                logger.error(f"Automation failed (session: {session_id}): {e}", exc_info=True)
            finally:
                # Release database lock when automation completes or fails
                automation_lock.release_automation_lock(session_id)
                logger.info(f"Automation lock released for session {session_id}")

        # Create background task
        asyncio.create_task(run_automation_background())

        logger.info(f"Automation orchestrator started in background (session: {session_id})")

        return {
            "success": True,
            "message": f"Automation started: retrieving {articles_to_process} articles from category '{category}' (session: {session_id})"
        }
    
    except Exception as e:
        # Release database lock on any error
        try:
            automation_lock.release_automation_lock(session_id)
        except:
            pass
        logger.error(f"Failed to run automation: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to run automation: {str(e)}"
        }


# ============================================================================
# Automation Routes
# ============================================================================

@router.get("/automation/lock-status")
async def get_automation_lock_status(automation_lock = Depends(get_automation_lock)):
    """
    Get the current status of the automation lock.
    
    Returns information about whether an automation is currently locked and by whom.
    """
    try:
        if not automation_lock:
            return {
                "locked": False,
                "message": "Automation lock manager not available"
            }
        
        status = automation_lock.get_automation_lock_status()
        return status
        
    except Exception as e:
        logger.error(f"Failed to get automation lock status: {e}", exc_info=True)
        return {
            "locked": False,
            "error": str(e)
        }

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
async def stop_automation(
    automation_orchestrator = Depends(get_automation_orchestrator),
    automation_lock = Depends(get_automation_lock),
    automation_state = Depends(get_automation_state)
):
    """
    Stop the active automation orchestrator and release the automation lock.
    """
    try:
        if not automation_orchestrator:
            return {
                "success": False,
                "message": "No active automation orchestrator"
            }

        # Get session ID before stopping
        session_id = getattr(automation_orchestrator, 'session_id', None)

        result = automation_orchestrator.stop()
        if result:
            # Release the automation lock when automation is stopped
            if automation_lock:
                try:
                    if session_id:
                        automation_lock.release_automation_lock(session_id)
                        logger.info(f"Released automation lock for session {session_id}")
                    elif automation_state:
                        current_state = automation_state.get_state()
                        if current_state and current_state.session_id:
                            automation_lock.release_automation_lock(current_state.session_id)
                            logger.info(f"Released automation lock for session {current_state.session_id}")
                except Exception as e:
                    logger.warning(f"Failed to release automation lock: {e}")

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


# ============================================================================
# Events Routes (SSE Streaming)
# ============================================================================

@router.get("/events")
async def get_events_stream(event_manager = Depends(get_event_manager)):
    """
    Stream d'événements en temps réel via Server-Sent Events (SSE).
    
    Permet à React de recevoir les événements structurés pour l'observabilité:
    - AUTOMATION_STARTED
    - ARTICLE_DISCOVERED
    - ARTICLE_QUEUED
    - ANALYSIS_STARTED
    - ANALYSIS_COMPLETED
    - REPAIR_STARTED
    - REPAIR_COMPLETED
    - VALIDATION_STARTED
    - VALIDATION_FAILED
    - PUBLISHING_STARTED
    - PUBLISHED
    - ERROR
    - AUTOMATION_PAUSED
    - AUTOMATION_STOPPED
    """
    if not event_manager:
        raise HTTPException(status_code=503, detail="Event manager not available")
    
    async def event_stream():
        """Générateur async pour le streaming SSE."""
        subscriber_queue = await event_manager.subscribe()
        
        try:
            # Envoyer les événements récents au démarrage
            recent_events = event_manager.get_recent_events(limit=50)
            for event in recent_events:
                yield f"data: {json.dumps(event)}\n\n"
            
            # Envoyer un message de connexion réussie
            yield f"data: {json.dumps({'type': 'CONNECTED', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Continuer à envoyer les nouveaux événements
            while True:
                try:
                    # Attendre le prochain événement avec timeout
                    event = await asyncio.wait_for(subscriber_queue.get(), timeout=30.0)
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    # Envoyer un heartbeat pour maintenir la connexion
                    yield ": heartbeat\n\n"
                except Exception as e:
                    logger.error(f"Error in event stream: {e}")
                    break
        finally:
            await event_manager.unsubscribe(subscriber_queue)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Désactiver le buffering nginx
        }
    )


@router.get("/events/recent")
async def get_recent_events(event_manager = Depends(get_event_manager), limit: int = 100):
    """
    Récupère les événements récents (sans streaming).
    
    Args:
        limit: Nombre maximum d'événements à retourner (défaut: 100)
        
    Returns:
        Liste des événements récents
    """
    if not event_manager:
        raise HTTPException(status_code=503, detail="Event manager not available")
    
    try:
        events = event_manager.get_recent_events(limit=limit)
        return {
            "success": True,
            "count": len(events),
            "events": events
        }
    except Exception as e:
        logger.error(f"Failed to get recent events: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get events: {str(e)}")

