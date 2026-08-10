"""
Kill Switch Manager with persistent state and multiple trigger sources.

This provides a robust kill switch mechanism with:
- Persistent state (survives process restarts)
- Multiple trigger sources (dashboard, talk page, auto-safety)
- Final verification in Publisher before each edit
- Deterministic commands via talk page
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class KillSwitchTrigger(Enum):
    """Sources of kill switch activation."""
    DASHBOARD = "dashboard"
    TALK_PAGE = "talk_page"
    AUTO_SAFETY = "auto_safety"
    MANUAL = "manual"


@dataclass
class KillSwitchState:
    """Persistent kill switch state."""
    enabled: bool = False
    reason: str = ""
    trigger_source: str = ""
    requested_by: str = ""
    requested_at: Optional[str] = None
    last_checked: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KillSwitchState':
        """Create from dictionary."""
        return cls(**data)


class KillSwitchManager:
    """
    Centralized kill switch manager with persistent state.
    
    This is the authoritative source for whether the bot should be stopped.
    All components (Scheduler, Publisher, Workers) must check this state.
    """
    
    def __init__(self, state_file: Optional[str] = None):
        """
        Initialize the kill switch manager.
        
        Args:
            state_file: Path to state file (default: .kill_switch_state.json)
        """
        if state_file is None:
            state_file = ".kill_switch_state.json"
        
        self.state_file = Path(state_file)
        self._state = self._load_state()
        
        logger.info(f"Kill Switch Manager initialized - State: {'ENABLED' if self._state.enabled else 'DISABLED'}")
    
    def _load_state(self) -> KillSwitchState:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    state = KillSwitchState.from_dict(data)
                    logger.info(f"Loaded kill switch state from file: {state.to_dict()}")
                    return state
            except Exception as e:
                logger.error(f"Failed to load kill switch state: {e}")
        
        # Default state
        return KillSwitchState()
    
    def _save_state(self) -> None:
        """Save state to file."""
        try:
            self._state.last_checked = datetime.now().isoformat()
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self._state.to_dict(), f, indent=2)
            logger.debug(f"Saved kill switch state: {self._state.to_dict()}")
        except Exception as e:
            logger.error(f"Failed to save kill switch state: {e}")
    
    def is_enabled(self) -> bool:
        """
        Check if kill switch is enabled.
        
        Returns:
            True if kill switch is enabled
        """
        # Reload from file to ensure we have latest state
        self._state = self._load_state()
        return self._state.enabled
    
    def enable(
        self,
        reason: str,
        trigger_source: KillSwitchTrigger,
        requested_by: str = "system"
    ) -> None:
        """
        Enable the kill switch.
        
        Args:
            reason: Reason for enabling
            trigger_source: Source of the trigger
            requested_by: Who requested the stop
        """
        self._state.enabled = True
        self._state.reason = reason
        self._state.trigger_source = trigger_source.value
        self._state.requested_by = requested_by
        self._state.requested_at = datetime.now().isoformat()
        
        self._save_state()
        
        logger.warning(
            f"🛑 KILL SWITCH ENABLED - Source: {trigger_source.value}, "
            f"Reason: {reason}, By: {requested_by}"
        )
    
    def disable(
        self,
        reason: str,
        requested_by: str = "system"
    ) -> None:
        """
        Disable the kill switch.
        
        Args:
            reason: Reason for disabling
            requested_by: Who requested the resume
        """
        self._state.enabled = False
        self._state.reason = reason
        self._state.requested_by = requested_by
        self._state.requested_at = datetime.now().isoformat()
        
        self._save_state()
        
        logger.info(
            f"✅ KILL SWITCH DISABLED - Reason: {reason}, By: {requested_by}"
        )
    
    def get_state(self) -> KillSwitchState:
        """
        Get current state.
        
        Returns:
            Current kill switch state
        """
        self._state = self._load_state()
        return self._state
    
    def check_and_raise(self) -> None:
        """
        Check if kill switch is enabled and raise exception if so.
        
        This is the FINAL verification that must be called before ANY edit.
        
        Raises:
            RuntimeError: If kill switch is enabled
        """
        if self.is_enabled():
            state = self.get_state()
            error_msg = (
                f"Publication blocked: Kill switch enabled\n"
                f"Source: {state.trigger_source}\n"
                f"Reason: {state.reason}\n"
                f"Requested by: {state.requested_by}\n"
                f"Requested at: {state.requested_at}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)


# Global instance
_kill_switch_manager: Optional[KillSwitchManager] = None


def get_kill_switch_manager(state_file: Optional[str] = None) -> KillSwitchManager:
    """
    Get the global kill switch manager instance.
    
    Args:
        state_file: Optional state file path
        
    Returns:
        KillSwitchManager instance
    """
    global _kill_switch_manager
    
    if _kill_switch_manager is None:
        _kill_switch_manager = KillSwitchManager(state_file)
    
    return _kill_switch_manager