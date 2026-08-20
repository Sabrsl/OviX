"""
Kill Switch Manager with persistent state and multiple trigger sources.

This provides a robust kill switch mechanism with:
- Persistent state (survives process restarts)
- Multiple trigger sources (dashboard, talk page, auto-safety)
- Final verification in Publisher before each edit
- Deterministic commands via talk page
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

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


class KillSwitchManager:
    """
    Centralized kill switch manager with persistent state in database.

    This is the authoritative source for whether the bot should be stopped.
    All components (Scheduler, Publisher, Workers) must check this state.
    """

    def __init__(self, database=None):
        """
        Initialize the kill switch manager.

        Args:
            database: DatabaseManager instance (optional, will try to get from global)
        """
        self._database = database
        if self._database is None:
            try:
                from wikipedia_maintenance.utils.database import get_database
                self._database = get_database()
            except Exception as e:
                logger.warning(f"Could not get database for kill switch: {e}")

        # Initialize state from database
        self._state = self._load_state()

        logger.info(f"Kill Switch Manager initialized - State: {'ENABLED' if self._state.enabled else 'DISABLED'}")

    def _load_state(self) -> KillSwitchState:
        """Load state from database."""
        if not self._database:
            logger.warning("No database available, using default disabled state")
            return KillSwitchState()

        try:
            cursor = self._database.conn.cursor()
            cursor.execute("""
                SELECT enabled, reason, trigger_source, requested_by, requested_at, last_checked
                FROM kill_switch_state
                WHERE id = 1
            """)
            row = cursor.fetchone()

            if row:
                enabled = bool(row[0])
                reason = row[1] or ""
                trigger_source = row[2] or ""
                requested_by = row[3] or ""
                requested_at = row[4]
                last_checked = row[5]

                logger.info(f"Loaded kill switch state from database: enabled={enabled}")
                return KillSwitchState(
                    enabled=enabled,
                    reason=reason,
                    trigger_source=trigger_source,
                    requested_by=requested_by,
                    requested_at=requested_at,
                    last_checked=last_checked
                )
            else:
                logger.warning("No kill switch state found in database, using default")
                return KillSwitchState()
        except Exception as e:
            logger.error(f"Failed to load kill switch state from database: {e}")
            return KillSwitchState()

    def _save_state(self) -> None:
        """Save state to database."""
        if not self._database:
            logger.error("No database available, cannot save kill switch state")
            return

        try:
            cursor = self._database.conn.cursor()
            cursor.execute("""
                UPDATE kill_switch_state
                SET enabled = ?,
                    reason = ?,
                    trigger_source = ?,
                    requested_by = ?,
                    requested_at = ?,
                    last_checked = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """, (
                1 if self._state.enabled else 0,
                self._state.reason,
                self._state.trigger_source,
                self._state.requested_by,
                self._state.requested_at,
                datetime.now().isoformat()
            ))
            self._database.conn.commit()
            logger.debug(f"Saved kill switch state to database: enabled={self._state.enabled}")
        except Exception as e:
            logger.error(f"Failed to save kill switch state to database: {e}")

    def is_enabled(self) -> bool:
        """
        Check if kill switch is enabled.

        Returns:
            True if kill switch is enabled
        """
        # Reload from database to ensure we have latest state
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


def get_kill_switch_manager(state_file: Optional[str] = None, database=None) -> KillSwitchManager:
    """
    Get the global kill switch manager instance.

    Args:
        state_file: Optional state file path (deprecated, now uses database)
        database: Optional DatabaseManager instance

    Returns:
        KillSwitchManager instance
    """
    global _kill_switch_manager

    if _kill_switch_manager is None:
        _kill_switch_manager = KillSwitchManager(database=database)

    return _kill_switch_manager