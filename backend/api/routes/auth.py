"""
OVIX Backend API - Authentication Routes

Handles Wikipedia authentication and session management.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import pywikibot
import os
import sys
from pathlib import Path
import threading

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Models
# ============================================================================

class WikipediaLoginRequest(BaseModel):
    """Wikipedia login request."""
    lang: str = "fr"
    family: str = "wikipedia"
    username: Optional[str] = None
    password: Optional[str] = None
    remember: bool = False


class WikipediaLoginResponse(BaseModel):
    """Wikipedia login response."""
    success: bool
    authenticated: bool
    lang: str
    family: str
    username: Optional[str] = None
    message: str


class AuthStatusResponse(BaseModel):
    """Authentication status response."""
    authenticated: bool
    lang: Optional[str] = None
    family: Optional[str] = None
    username: Optional[str] = None


# ============================================================================
# Session Management
# ============================================================================

# Global session state (module-level for simplicity, could be enhanced with Redis)
_wikipedia_session = {
    "site": None,
    "publisher": None,
    "lang": None,
    "family": None,
    "username": None,
    "authenticated": False
}

# Lock to protect session access from concurrent threads
_session_lock = threading.RLock()


def get_wikipedia_session():
    """Get current Wikipedia session (thread-safe)."""
    with _session_lock:
        return _wikipedia_session  # Return reference, protected by lock


# ============================================================================
# Routes
# ============================================================================

@router.post("/login", response_model=WikipediaLoginResponse)
async def wikipedia_login(request: WikipediaLoginRequest):
    """
    Authenticate with Wikipedia.

    This endpoint creates a pywikibot site for retrieval and a Publisher
    for publishing (if credentials are provided).

    Session persistence: The connection is reused if the same parameters
    (lang, family, username) are provided, matching Streamlit behavior.
    """
    try:
        # Set PYWIKIBOT_DIR to project root
        project_root = Path(__file__).parent.parent.parent.parent
        os.environ['PYWIKIBOT_DIR'] = str(project_root)
        sys.path.insert(0, str(project_root))

        # Check if already connected with same parameters (matching Streamlit behavior)
        if (_wikipedia_session["authenticated"] and
            _wikipedia_session["lang"] == request.lang and
            _wikipedia_session["family"] == request.family):
            # If credentials provided, check if they match
            if request.username:
                if _wikipedia_session["username"] == request.username:
                    logger.info("Already connected to Wikipedia with same credentials, reusing existing connection")
                    return WikipediaLoginResponse(
                        success=True,
                        authenticated=True,
                        lang=request.lang,
                        family=request.family,
                        username=_wikipedia_session["username"],
                        message="Already connected"
                    )
                else:
                    # Different username, need to reconnect
                    logger.info("Different username provided, reconnecting to Wikipedia")
            else:
                # No new credentials, reuse existing connection
                logger.info("Already connected to Wikipedia, reusing existing connection")
                return WikipediaLoginResponse(
                    success=True,
                    authenticated=True,
                    lang=request.lang,
                    family=request.family,
                    username=_wikipedia_session["username"],
                    message="Already connected"
                )

        # Create pywikibot site for retrieval
        site = pywikibot.Site(request.lang, request.family)

        # Configure pywikibot rate limiting
        pywikibot.config.put_throttle = 0  # Disable default throttling
        pywikibot.config.maxlag = 5

        # Apply our throttler to pywikibot
        from wikipedia_maintenance.utils.api_throttler import get_global_throttler
        api_throttler = get_global_throttler()

        try:
            original_request = site._simple_request
            def throttled_request(**kwargs):
                api_throttler.wait_if_needed()
                try:
                    result = original_request(**kwargs)
                    api_throttler.report_success()
                    return result
                except Exception as e:
                    if '429' in str(e) or 'Too Many Requests' in str(e):
                        api_throttler.report_429()
                    raise

            site._simple_request = throttled_request
        except AttributeError:
            logger.info("Using pywikibot built-in rate limiting")

        # Create Publisher if credentials provided
        publisher = None
        authenticated = False
        username = None

        if request.username and request.password:
            from wikipedia_maintenance.utils.publisher import Publisher

            publisher = Publisher(
                username=request.username,
                password=request.password,
                dry_run=True,  # Default to dry-run for safety
                lang=request.lang
            )

            authenticated = publisher.authenticate()
            username = request.username if authenticated else None

            if not authenticated:
                logger.warning("Wikipedia authentication failed")
                return WikipediaLoginResponse(
                    success=False,
                    authenticated=False,
                    lang=request.lang,
                    family=request.family,
                    message="Authentication failed"
                )
        else:
            # No credentials provided, create publisher without auth
            from wikipedia_maintenance.utils.publisher import Publisher
            publisher = Publisher(dry_run=True, lang=request.lang)
            authenticated = True  # Connected for retrieval only

        # Store session
        _wikipedia_session.update({
            "site": site,
            "publisher": publisher,
            "lang": request.lang,
            "family": request.family,
            "username": username,
            "authenticated": authenticated
        })

        logger.info(f"Successfully connected to Wikipedia ({request.lang}.{request.family})")

        return WikipediaLoginResponse(
            success=True,
            authenticated=authenticated,
            lang=request.lang,
            family=request.family,
            username=username,
            message="Connected successfully"
        )

    except Exception as e:
        logger.error(f"Wikipedia login failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.get("/user")
async def get_current_user():
    """
    Get current authenticated user information.
    
    Returns the username and authentication status of the current session.
    """
    try:
        return {
            "authenticated": _wikipedia_session.get("authenticated", False),
            "username": _wikipedia_session.get("username"),
            "lang": _wikipedia_session.get("lang"),
            "family": _wikipedia_session.get("family")
        }
    except Exception as e:
        logger.error(f"Failed to get current user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get current user: {str(e)}")


@router.post("/logout", response_model=dict)
async def wikipedia_logout():
    """
    Logout from Wikipedia.
    
    Clears the current Wikipedia session.
    """
    try:
        _wikipedia_session.update({
            "site": None,
            "publisher": None,
            "lang": None,
            "family": None,
            "username": None,
            "authenticated": False
        })
        
        logger.info("Wikipedia session cleared")
        
        return {"success": True, "message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")


@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status():
    """
    Get current authentication status (thread-safe).
    """
    try:
        with _session_lock:
            return AuthStatusResponse(
                authenticated=_wikipedia_session["authenticated"],
                lang=_wikipedia_session["lang"],
                family=_wikipedia_session["family"],
                username=_wikipedia_session["username"]
            )
        
    except Exception as e:
        logger.error(f"Failed to get auth status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/account")
async def get_account_info():
    """
    Get Wikipedia account information.
    
    Returns information about the currently authenticated Wikipedia account.
    """
    try:
        if not _wikipedia_session["authenticated"]:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        if not _wikipedia_session["site"]:
            raise HTTPException(status_code=500, detail="Wikipedia site not initialized")
        
        site = _wikipedia_session["site"]
        
        # Get user info
        user = site.user()
        
        return {
            "success": True,
            "username": user.name if user else None,
            "groups": list(user.groups()) if user else [],
            "editcount": user.editcount if user else 0,
            "registration": str(user.registration) if user and user.registration else None,
            "lang": _wikipedia_session["lang"],
            "family": _wikipedia_session["family"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get account info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get account info: {str(e)}")


@router.get("/validate")
async def validate_session():
    """
    Validate the current Wikipedia session by making a test API call.
    
    This endpoint checks if the session is still valid by attempting to fetch
    the current user information. If the session has expired or the connection
    has been lost, it will return authenticated=False.
    """
    try:
        with _session_lock:
            if not _wikipedia_session["authenticated"]:
                return {
                    "valid": False,
                    "authenticated": False,
                    "message": "Session not authenticated"
                }
            
            if not _wikipedia_session["site"]:
                return {
                    "valid": False,
                    "authenticated": False,
                    "message": "Wikipedia site not initialized"
                }
            
            site = _wikipedia_session["site"]
            
            # Test the connection by trying to get the current user
            try:
                user = site.user()
                if user:
                    logger.info(f"Session validation successful for user: {user.name}")
                    return {
                        "valid": True,
                        "authenticated": True,
                        "username": user.name,
                        "message": "Session is valid"
                    }
                else:
                    logger.warning("Session validation failed: user is None")
                    return {
                        "valid": False,
                        "authenticated": False,
                        "message": "Unable to retrieve user information"
                    }
            except Exception as e:
                logger.warning(f"Session validation failed with error: {e}")
                # Session appears to be invalid, mark as not authenticated
                _wikipedia_session["authenticated"] = False
                return {
                    "valid": False,
                    "authenticated": False,
                    "message": f"Session validation failed: {str(e)}"
                }
        
    except Exception as e:
        logger.error(f"Failed to validate session: {e}", exc_info=True)
        return {
            "valid": False,
            "authenticated": False,
            "message": f"Validation error: {str(e)}"
        }
