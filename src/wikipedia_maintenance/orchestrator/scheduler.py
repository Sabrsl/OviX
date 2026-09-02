"""
Main scheduler for Wikipedia maintenance automation.

Orchestrates the publication queue with timing logic, pauses, working hours,
and daily limits. Integrates with Telegram bot for remote control.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from threading import Lock

from .scheduler_state_sqlite import SQLiteStateManager, SchedulerState
from .timing_manager import TimingManager, PauseSchedule
from .telegram_bot import TelegramBot, create_telegram_bot
from .daily_article_collector import DailyArticleCollector, DailyCollectionConfig
from wikipedia_maintenance.utils.publisher import Publisher
from wikipedia_maintenance.utils.published_tracker import PublishedTracker
from wikipedia_maintenance.utils.analyzed_tracker import AnalyzedTracker, AnalysisStatus
from wikipedia_maintenance.utils.kill_switch_manager import get_kill_switch_manager
from wikipedia_maintenance.utils.event_manager import get_event_manager, EventType
from wikipedia_maintenance.utils.edit_summaries import get_random_summary
from wikipedia_maintenance.utils.talk_page_monitor import TalkPageCommandHandler

logger = logging.getLogger(__name__)


@dataclass
class SchedulerConfig:
    """Configuration for the scheduler."""
    state_file: str = "data/scheduler_state.json"
    telegram_bot_token: Optional[str] = None
    telegram_admin_ids: List[int] = None
    dry_run: bool = True
    daily_limit: Optional[int] = None  # P0 FIX: Load from config via TimingManager, not hardcoded
    stop_on_empty_queue: bool = True  # Stop scheduler when queue is empty
    site: Optional[Any] = None  # Pywikibot site object
    category: Optional[str] = None  # Wikipedia category for manual runs
    articles_to_process: int = 10  # Number of articles to process in manual run
    bot_username: str = "OviXCore"  # Wikipedia username of the bot for talk page monitoring


class Scheduler:
    """
    Main scheduler for automated Wikipedia maintenance.

    Manages:
    - Publication queue
    - Timing delays and pauses
    - Working hours enforcement
    - Daily limits
    - Telegram bot integration
    - State persistence
    - Kill Switch integration
    """

    def __init__(self, config: SchedulerConfig, publisher, published_tracker: Optional[PublishedTracker] = None, analyzed_tracker: Optional[AnalyzedTracker] = None, kill_switch_manager=None, database=None):
        """
        Initialize scheduler.

        Args:
            config: SchedulerConfig with settings.
            publisher: Publisher instance for publishing to Wikipedia.
            published_tracker: PublishedTracker instance for tracking published articles.
            analyzed_tracker: AnalyzedTracker instance for tracking analyzed articles.
            kill_switch_manager: KillSwitchManager instance for emergency stop.
            database: DatabaseManager instance for SQLite queue synchronization (P1-4).
        """
        self.config = config
        self.publisher = publisher
        self.published_tracker = published_tracker
        self.analyzed_tracker = analyzed_tracker
        self.kill_switch_manager = kill_switch_manager
        self.database = database  # P1-4: SQLite database for queue synchronization

        # Initialize TalkPageCommandHandler for Wikipedia talk page monitoring
        self.talk_page_handler: Optional[TalkPageCommandHandler] = None
        if self.kill_switch_manager and self.config.site:
            try:
                self.talk_page_handler = TalkPageCommandHandler(
                    bot_username=config.bot_username,
                    kill_switch_manager=self.kill_switch_manager
                )
                logger.info(f"TalkPageCommandHandler initialized for bot {config.bot_username}")
            except Exception as e:
                logger.warning(f"Failed to initialize TalkPageCommandHandler: {e}")

        # Initialize components - SQLite as single source of truth
        if self.database:
            self.state_manager = SQLiteStateManager(self.database)
        else:
            # Fallback to JSON if database not provided (should not happen in production)
            from .scheduler_state import StateManager
            self.state_manager = StateManager(config.state_file)
            logger.warning("Using JSON-based state manager - SQLite database not provided")
        self.timing_manager = TimingManager()
        self.event_manager = get_event_manager()
        self.telegram_bot: Optional[TelegramBot] = None

        # Runtime state
        self._running = False
        self._paused = False  # NEW: Track pause state
        self._task: Optional[asyncio.Task] = None
        self._active_pauses: List[PauseSchedule] = []
        self._state_lock = Lock()  # Lock to prevent race conditions on _paused/_running

        # Initialize DailyArticleCollector for automatic daily article collection
        self.daily_collector: Optional[DailyArticleCollector] = None
        if self.database:
            try:
                # Load daily collection config from timing_manager or use defaults
                daily_collection_config = DailyCollectionConfig(
                    enabled=True,
                    category=getattr(self.timing_manager, 'daily_collection_category', "Article à wikifier/Liste complète"),
                    max_articles=getattr(self.timing_manager, 'daily_collection_max_articles', 500),
                    batch_size=getattr(self.timing_manager, 'daily_collection_batch_size', 100),
                    exclude_published=True,
                    exclude_analyzed=True,
                    lang='fr',
                    family='wikipedia'
                )
                self.daily_collector = DailyArticleCollector(
                    config=daily_collection_config,
                    database=self.database,
                    site=self.config.site,
                    published_tracker=self.published_tracker,
                    analyzed_tracker=self.analyzed_tracker
                )
                logger.info("DailyArticleCollector initialized for automatic daily collection")
            except Exception as e:
                logger.warning(f"Failed to initialize DailyArticleCollector: {e}")

        # Initialize Telegram bot if configured
        if config.telegram_bot_token and config.telegram_admin_ids:
            self.telegram_bot = create_telegram_bot(
                config.telegram_bot_token,
                config.telegram_admin_ids,
                self.state_manager,
                self.timing_manager
            )

        logger.info("Scheduler initialized")

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting scheduler...")
        self._paused = False  # Clear pause flag on fresh start
        self._running = True

        # Set state to active immediately
        self.state_manager.set_active(True)
        self.state_manager.set_paused(False)  # Clear paused state on fresh start

        # Verify is_active was set
        state = self.state_manager.get_state()
        logger.info(f"Scheduler state after set_active: is_active={state.is_active}")

        # Start Telegram bot if configured
        if self.telegram_bot:
            await self.telegram_bot.start()

        # Start main scheduler loop as a background task
        logger.info("Starting scheduler loop...")
        self._task = asyncio.create_task(self._scheduler_loop())
        # Surface unexpected loop crashes instead of failing silently
        self._task.add_done_callback(self._on_loop_done)
        logger.info("Scheduler loop task created")
        logger.info("Scheduler started")

    def _on_loop_done(self, task: asyncio.Task) -> None:
        """Callback invoked when the scheduler loop task finishes."""
        self._running = False
        if task.cancelled():
            logger.info("Scheduler loop task was cancelled")
            return
        exc = task.exception()
        if exc:
            logger.error(f"Scheduler loop terminated unexpectedly: {exc}", exc_info=exc)
            try:
                self.state_manager.set_active(False)
            except Exception as e:
                logger.error(f"Failed to persist inactive state after crash: {e}")

    def is_running(self) -> bool:
        """Check if the scheduler is currently running."""
        return self._running

    def is_paused(self) -> bool:
        """Check if the scheduler is currently paused."""
        return hasattr(self, '_paused') and self._paused

    async def pause(self) -> None:
        """Pause the scheduler (completes current operation, preserves state)."""
        with self._state_lock:
            if not self._running:
                logger.warning("Cannot pause: scheduler not running")
                return

            if self._paused:
                logger.warning("Cannot pause: scheduler already paused")
                return

            logger.info("=== PAUSE REQUESTED ===")
            logger.info("PAUSING - waiting for current operation to complete...")

            # Set paused flag first - this prevents NEW operations from starting
            self._paused = True
        
        # Wait for current operation to complete naturally
        # The scheduler loop will check _paused flag and stop after current iteration
        # We don't cancel the task - we let it finish the current article
        logger.info("Waiting for current operation to complete (max 30 seconds)...")

        
        # Wait up to 30 seconds for the current operation to complete
        max_wait = 30
        waited = 0
        while waited < max_wait:
            # Check if scheduler loop has stopped processing
            if not self._task or self._task.done():
                break
            await asyncio.sleep(1)
            waited += 1
        
        if waited >= max_wait:
            logger.warning(f"Current operation did not complete within {max_wait}s, forcing pause")
            # Force cancel if operation didn't complete
            if self._task:
                self._task.cancel()
                try:
                    await asyncio.wait_for(self._task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception as e:
                    logger.error(f"Error forcing scheduler task cancellation: {e}")
                finally:
                    self._task = None
        else:
            logger.info(f"Current operation completed in {waited}s")
        
        # Set state to paused (not inactive - preserves queue and state)
        self.state_manager.set_paused(True)
        
        # Pause Telegram bot if configured
        if self.telegram_bot:
            try:
                # Check if pause method exists, otherwise just stop
                if hasattr(self.telegram_bot, 'pause'):
                    await self.telegram_bot.pause()
                else:
                    await self.telegram_bot.stop()
            except Exception as e:
                logger.error(f"Error pausing Telegram bot: {e}")

        # Keep state file as-is (preserves queue, counters, etc.)
        logger.info("=== SCHEDULER PAUSED (atomic operation completed, state preserved) ===")
        
        # Émettre AUTOMATION_PAUSED
        await self.event_manager.emit(
            EventType.AUTOMATION_PAUSED,
            {
                "queue_size": self.state_manager.get_queue_size(),
                "daily_published": self.state_manager.get_state().daily_published_count
            }
        )

    async def resume(self) -> None:
        """Resume a paused scheduler or start if not running."""
        with self._state_lock:
            logger.info(f"=== resume() called - _paused={self._paused}, _running={self._running} ===")
            
            if not self._paused and self._running:
                logger.warning("Scheduler already running, cannot resume")
                return

            logger.info("Resuming scheduler...")
            self._paused = False
            self._running = True

            # Set state back to active
            self.state_manager.set_paused(False)
            self.state_manager.set_active(True)

            # Resume Telegram bot if configured
            if self.telegram_bot:
                try:
                    # Check if resume method exists, otherwise just start
                    if hasattr(self.telegram_bot, 'resume'):
                        await self.telegram_bot.resume()
                    else:
                        await self.telegram_bot.start()
                except Exception as e:
                    logger.error(f"Error resuming Telegram bot: {e}")

            # Restart scheduler loop
            logger.info("Restarting scheduler loop...")
            self._task = asyncio.create_task(self._scheduler_loop())
            self._task.add_done_callback(self._on_loop_done)
            logger.info("Scheduler resumed successfully - loop task created")

    async def stop(self) -> None:
        """
        Stop the scheduler gracefully.
        
        P0 CRITICAL FIX: Graceful shutdown with queue/state preservation.
        - STOP requested → STOPPING → fin opération courante → queue sauvegardée → état sauvegardé → STOPPED
        - Waits for current atomic operation to complete
        - Preserves queue and state
        - Clean shutdown
        """
        if not self._running:
            logger.warning("Scheduler not running")
            return

        logger.info("=== STOP REQUESTED ===")
        logger.info("STOPPING - waiting for current operation to complete...")
        
        # Set running flag to false first - this prevents NEW operations from starting
        self._running = False
        
        # Wait for current operation to complete naturally
        # The scheduler loop will check _running flag and stop after current iteration
        logger.info("Waiting for current operation to complete (max 30 seconds)...")
        
        # Wait up to 30 seconds for the current operation to complete
        max_wait = 30
        waited = 0
        while waited < max_wait:
            # Check if scheduler loop has stopped processing
            if not self._task or self._task.done():
                break
            await asyncio.sleep(1)
            waited += 1
        
        if waited >= max_wait:
            logger.warning(f"Current operation did not complete within {max_wait}s, forcing stop")
            # Force cancel if operation didn't complete
            if self._task:
                self._task.cancel()
                try:
                    await asyncio.wait_for(self._task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception as e:
                    logger.error(f"Error forcing scheduler task cancellation: {e}")
                finally:
                    self._task = None
        else:
            logger.info(f"Current operation completed in {waited}s")
        
        # Set state to inactive (queue preserved in database)
        logger.info("Setting scheduler state to inactive (queue preserved)...")
        self.state_manager.set_active(False)
        
        # Stop Telegram bot
        if self.telegram_bot:
            try:
                await self.telegram_bot.stop()
            except Exception as e:
                logger.error(f"Error stopping Telegram bot: {e}")

        # Save state (queue is already preserved in SQLite database)
        logger.info("Saving scheduler state...")
        self.state_manager.update_state(
            next_publish_time=None,
            next_pause_start=None,
            next_pause_end=None
        )

        logger.info("=== SCHEDULER STOPPED (operation completed, queue preserved, state saved) ===")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop with P0 CRITICAL FIX: Enhanced Kill Switch."""
        logger.info("=== SCHEDULER LOOP STARTED ===")
        logger.info(f"Scheduler loop started - _running={self._running}, _paused={self._paused}")

        try:
            # Reset daily counters if needed
            logger.info("Resetting daily counters...")
            self.state_manager.reset_daily_counters()
            logger.info("Daily counters reset")
        except Exception as e:
            logger.error(f"Error resetting daily counters: {e}", exc_info=True)

        # Check Wikipedia talk page for kill switch commands on startup
        await self._check_talk_page()

        # Generate daily long pauses if not already set or if day changed
        logger.info("Checking daily long pauses...")
        state = self.state_manager.get_state()
        today = datetime.now().date()

        # Check if we need to regenerate pauses (new day or no pauses set)
        regenerate_pauses = False
        if not state.long_pauses_today:
            regenerate_pauses = True
            logger.info("No long pauses set, will regenerate")
        else:
            # Check if any pause is from today
            has_today_pause = False
            for pause_data in state.long_pauses_today:
                pause_date = datetime.fromisoformat(pause_data['start']).date()
                if pause_date == today:
                    has_today_pause = True
                    break
            if not has_today_pause:
                regenerate_pauses = True
                logger.info("No pauses from today, will regenerate")

        if regenerate_pauses:
            logger.info("Generating daily long pauses...")
            long_pauses = self.timing_manager.generate_daily_long_pauses(datetime.now())
            state.long_pauses_today = [
                {
                    'start': p.start_time.isoformat(),
                    'end': p.end_time.isoformat(),
                    'type': p.pause_type
                }
                for p in long_pauses
            ]
            self.state_manager.update_state(long_pauses_today=state.long_pauses_today)
            logger.info(f"Regenerated {len(long_pauses)} long pauses for today")

        # Clean up expired pauses from state
        current_time = datetime.now()
        cleaned_pauses = [
            pause for pause in state.long_pauses_today
            if datetime.fromisoformat(pause['end']) > current_time
        ]
        if len(cleaned_pauses) != len(state.long_pauses_today):
            logger.info(f"Cleaned {len(state.long_pauses_today) - len(cleaned_pauses)} expired pauses from state")
            self.state_manager.update_state(long_pauses_today=cleaned_pauses)

        first_iteration = True
        logger.info("Starting main scheduler loop with first_iteration=True")

        while self._running:
            logger.info("=== Scheduler loop iteration ===")
            try:
                # Check Wikipedia talk page for kill switch commands (every iteration)
                await self._check_talk_page()

                # P1 CRITICAL FIX: Check Kill Switch from database (authoritative source)
                if self.kill_switch_manager and self.kill_switch_manager.is_enabled():
                    logger.warning("KILL SWITCH ENABLED (from database) - EXITING SCHEDULER LOOP")
                    self.state_manager.set_active(False)  # Also update state file
                    break
                
                # Also check state file for backward compatibility
                state = self.state_manager.get_state()
                if not state.is_active:
                    logger.warning("KILL SWITCH ACTIVATED (from state file) - EXITING SCHEDULER LOOP")
                    break
                    
                logger.info(f"Kill Switch status: is_active={state.is_active}")
                queue_size = self.state_manager.get_queue_size()
                logger.info(f"Queue size: {queue_size}, Daily published: {state.daily_published_count}")

                # Check if queue is empty and stop if configured
                if queue_size == 0 and self.config.stop_on_empty_queue:
                    logger.info("Queue is empty and stop_on_empty_queue is enabled, stopping scheduler")
                    self.state_manager.set_active(False)
                    self._running = False
                    break

                # P1 CRITICAL FIX: Don't auto-activate if Kill Switch is off
                if not state.is_active or (self.kill_switch_manager and self.kill_switch_manager.is_enabled()):
                    logger.warning("KILL SWITCH ACTIVATED - Scheduler inactive, not auto-activating")
                    await asyncio.sleep(10)  # Wait before checking again
                    continue

                # Reset daily counters if day changed
                self.state_manager.reset_daily_counters()
                
                # Trigger daily article collection if enabled and not yet collected today
                if self.daily_collector and first_iteration:
                    logger.info("Checking if daily article collection is needed...")
                    try:
                        collection_result = self.daily_collector.collect_articles()
                        if collection_result.get('skipped'):
                            logger.info(f"Daily collection skipped: {collection_result.get('reason')}")
                        elif collection_result.get('success'):
                            logger.info(f"Daily collection completed: {collection_result.get('articles_added', 0)} articles added")
                        else:
                            logger.warning(f"Daily collection failed: {collection_result.get('error')}")
                    except Exception as e:
                        logger.error(f"Error during daily article collection: {e}", exc_info=True)
                
                # Cleanup stale queue items (crash recovery)
                if self.database:
                    try:
                        cleaned = self.database.cleanup_stale_queue_items(timeout_seconds=300, max_retries=3)
                        if cleaned > 0:
                            logger.info(f"Cleaned up {cleaned} stale queue items")
                    except Exception as e:
                        logger.error(f"Error cleaning up stale queue items: {e}")
                
                state = self.state_manager.get_state()

                # Check working hours
                current_time = datetime.now()
                logger.info(f"Current time: {current_time.strftime('%H:%M')}")
                logger.info(f"Working hours: {self.timing_manager.WORKING_HOUR_START}:00 - {self.timing_manager.WORKING_HOUR_END}:00")
                logger.info(f"Within working hours: {self.timing_manager.is_within_working_hours(current_time)}")

                # P1 CRITICAL FIX: Check Kill Switch before any operation (both sources)
                if not self.state_manager.get_state().is_active or (self.kill_switch_manager and self.kill_switch_manager.is_enabled()):
                    logger.warning("KILL SWITCH ACTIVATED - STOPPING SCHEDULER LOOP")
                    break

                if not self.timing_manager.is_within_working_hours(current_time):
                    next_working = self.timing_manager.get_next_working_hour_start(current_time)
                    wait_time = (next_working - current_time).total_seconds()
                    logger.info(f"Outside working hours, waiting until {next_working.strftime('%H:%M')}")
                    self.state_manager.update_state(next_publish_time=next_working.isoformat())
                    # Sleep in short intervals to allow cancellation with Kill Switch check
                    while wait_time > 0 and self._running:
                        # P1 CRITICAL FIX: Check Kill Switch during wait (both sources)
                        if not self.state_manager.get_state().is_active or (self.kill_switch_manager and self.kill_switch_manager.is_enabled()):
                            logger.warning("KILL SWITCH ACTIVATED - ABORTING WAIT")
                            break
                        sleep_time = min(wait_time, 1)  # P0 CRITICAL FIX: Sleep max 1 second for immediate Kill Switch response
                        await asyncio.sleep(sleep_time)
                        wait_time -= sleep_time
                    if not self.state_manager.get_state().is_active or (self.kill_switch_manager and self.kill_switch_manager.is_enabled()):
                        break
                    continue

                # Check daily limit
                if self.timing_manager.has_reached_daily_limit(state.daily_published_count):
                    logger.info("Daily limit reached, waiting until tomorrow")
                    next_working = self.timing_manager.get_next_working_hour_start(current_time)
                    wait_time = (next_working - current_time).total_seconds()

                    # Send Telegram notification if configured
                    if self.telegram_bot:
                        # Note: This would require adding a notification method to TelegramBot
                        logger.info("Daily limit reached - notification would be sent here")

                    # Sleep in short intervals to allow cancellation with Kill Switch check
                    while wait_time > 0 and self._running:
                        # P1 CRITICAL FIX: Check Kill Switch during wait (both sources)
                        if not self.state_manager.get_state().is_active or (self.kill_switch_manager and self.kill_switch_manager.is_enabled()):
                            logger.warning("KILL SWITCH ACTIVATED - ABORTING WAIT")
                            break
                        sleep_time = min(wait_time, 1)  # P0 CRITICAL FIX: Sleep max 1 second for immediate Kill Switch response
                        await asyncio.sleep(sleep_time)
                        wait_time -= sleep_time
                    if not self.state_manager.get_state().is_active or (self.kill_switch_manager and self.kill_switch_manager.is_enabled()):
                        break
                    continue

                # Check if in pause (skip for first iteration)
                self._load_active_pauses()
                in_pause, active_pause = self.timing_manager.is_in_pause(current_time, self._active_pauses)
                if in_pause and active_pause and not first_iteration:
                    wait_time = (active_pause.end_time - current_time).total_seconds()
                    logger.info(f"In {active_pause.pause_type} pause, waiting {wait_time/60:.1f} minutes until {active_pause.end_time.strftime('%H:%M')}")
                    # Sleep in short intervals to allow cancellation with Kill Switch check
                    while wait_time > 0 and self._running:
                        # P1 CRITICAL FIX: Check Kill Switch during wait (both sources)
                        if not self.state_manager.get_state().is_active or (self.kill_switch_manager and self.kill_switch_manager.is_enabled()):
                            logger.warning("KILL SWITCH ACTIVATED - ABORTING WAIT")
                            break
                        sleep_time = min(wait_time, 1)  # P0 CRITICAL FIX: Sleep max 1 second for immediate Kill Switch response
                        await asyncio.sleep(sleep_time)
                        wait_time -= sleep_time
                    if not self.state_manager.get_state().is_active:
                        break
                    continue

                # Transfer articles from articles_to_analyze to scheduler_queue if needed
                await self._transfer_articles_to_queue()

                # Process next article from queue
                logger.info(f"Processing next article (first_iteration={first_iteration})")
                await self._process_next_article()

                # Add random delay between publications (except for first article)
                if not first_iteration:
                    delay = self.timing_manager.generate_random_delay()
                    logger.info(f"Waiting {delay.total_seconds()/60:.1f} minutes before next publication...")
                    self.state_manager.update_state(next_publish_time=(current_time + delay).isoformat())
                    await asyncio.sleep(delay.total_seconds())
                else:
                    first_iteration = False
                    logger.info("First article processed immediately")

            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retrying

    def _load_active_pauses(self) -> None:
        """Load active pauses from state."""
        state = self.state_manager.get_state()
        current_time = datetime.now()

        self._active_pauses = []

        # Load long pauses from state - only include pauses that haven't ended yet
        for pause_data in state.long_pauses_today:
            start = datetime.fromisoformat(pause_data['start'])
            end = datetime.fromisoformat(pause_data['end'])
            # Only include pauses that are currently active or future (not past)
            if end > current_time and start <= current_time:
                self._active_pauses.append(PauseSchedule(
                    start_time=start,
                    end_time=end,
                    pause_type=pause_data['type']
                ))
                logger.debug(f"Loaded active long pause: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}")

        # Add periodic pause if scheduled and currently active
        if state.next_pause_start and state.next_pause_end:
            start = datetime.fromisoformat(state.next_pause_start)
            end = datetime.fromisoformat(state.next_pause_end)
            if end > current_time and start <= current_time:
                self._active_pauses.append(PauseSchedule(
                    start_time=start,
                    end_time=end,
                    pause_type='periodic'
                ))
                logger.debug(f"Loaded active periodic pause: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}")

    async def _heartbeat_loop(self, article_id: int, interval_seconds: int = 60) -> None:
        """
        Periodically update heartbeat timestamp for a processing article.

        Args:
            article_id: Queue item ID
            interval_seconds: Heartbeat interval in seconds
        """
        try:
            while self._running:
                if self.database:
                    self.database.update_queue_heartbeat(article_id)
                await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            logger.debug(f"Heartbeat loop cancelled for article {article_id}")
        except Exception as e:
            logger.error(f"Error in heartbeat loop for article {article_id}: {e}")

    async def _check_talk_page(self) -> None:
        """
        Check Wikipedia talk page for kill switch commands.

        Reads the bot's talk page and processes any STOP/RESUME commands.
        This is called periodically to allow emergency control via Wikipedia.
        """
        if not self.talk_page_handler or not self.config.site:
            return

        try:
            # Get the bot's talk page
            talk_page_title = f"Discussion utilisateur:{self.config.bot_username}"
            logger.info(f"Checking talk page: {talk_page_title}")

            # Get the page content
            page = self.config.site.page(talk_page_title)
            page_content = page.text

            if not page_content:
                logger.debug(f"Talk page {talk_page_title} is empty or not accessible")
                return

            # Process the talk page content
            self.talk_page_handler.process_talk_page(page_content, user="Wikipedia")

            logger.info(f"Talk page {talk_page_title} checked successfully")

        except Exception as e:
            logger.error(f"Error checking talk page: {e}", exc_info=True)

    async def _transfer_articles_to_queue(self) -> None:
        """
        Transfer ready-to-publish articles from analysis_results to scheduler_queue.
        This adds articles that have been analyzed and have corrections to the publication queue.
        """
        if not self.database:
            logger.warning("Database not available, cannot transfer articles")
            return

        state = self.state_manager.get_state()
        
        try:
            logger.info("=== _transfer_articles_to_queue called ===")
            
            # Get articles with corrections from analysis_results (ready to publish)
            # Check if they're not already in scheduler_queue
            cursor = self.database.conn.cursor()
            cursor.execute("""
                SELECT ar.article_title, ar.corrected_content, ar.original_content, ar.summary, 
                       ar.corrected_links_count, ar.page_id, ar.revision_id, ar.character_count, 
                       ar.total_links, ar.dead_links_count, ar.changes_count, ar.mode
                FROM analysis_results ar
                WHERE ar.corrected_links_count > 0
                AND NOT EXISTS (
                    SELECT 1 FROM scheduler_queue sq 
                    WHERE sq.title = ar.article_title 
                    AND sq.status NOT IN ('completed', 'error')
                )
                ORDER BY ar.analysis_date DESC
                LIMIT 20
            """)
            rows = cursor.fetchall()

            logger.info(f"Query returned {len(rows)} rows from analysis_results")

            if not rows:
                logger.debug("No ready-to-publish articles in analysis_results")
                return

            logger.info(f"Found {len(rows)} ready-to-publish articles, adding to scheduler_queue")

            for row in rows:
                (title, corrected_content, original_content, summary, corrected_links_count, 
                 page_id, revision_id, character_count, total_links, dead_links_count, 
                 changes_count, mode) = row
                
                logger.info(f"Adding ready-to-publish article: {title}")
                state.current_article = title
                state.current_step = "Adding to queue"
                state.articles_corrected += 1
                self.state_manager.save_state()

                try:
                    article_data = {
                        'title': title,
                        'page_id': page_id,
                        'revision_id': revision_id,
                        'corrected_content': corrected_content,
                        'summary': summary or "Dead link corrections via OVIX",
                        'changes_count': changes_count,
                        'original_content': original_content,
                        'character_count': character_count,
                        'total_links': total_links,
                        'dead_links_count': dead_links_count,
                        'corrected_links_count': corrected_links_count,
                        'mode': mode
                    }

                    queue_added = self.database.add_to_scheduler_queue(article_data)
                    if queue_added:
                        logger.info(f"Article {title} added to scheduler_queue successfully")
                    else:
                        logger.error(f"Failed to add article {title} to scheduler_queue")
                        state.articles_error += 1

                except Exception as e:
                    logger.error(f"Error adding article {title} to queue: {e}", exc_info=True)
                    state.articles_error += 1

            # Reset current tracking
            state.current_article = None
            state.current_step = "Waiting"
            self.state_manager.save_state()

        except Exception as e:
            logger.error(f"Error transferring articles to queue: {e}", exc_info=True)

    async def _process_next_article(self) -> None:
        """Process the next article from the queue."""
        logger.info("=== _process_next_article called ===")
        state = self.state_manager.get_state()
        queue_size = self.state_manager.get_queue_size()

        logger.info(f"Queue size before processing: {queue_size}")

        # Check if queue is empty - but don't deactivate immediately
        # _transfer_articles_to_queue() is called before this and may fill the queue
        if queue_size == 0:
            logger.info("Queue is empty, waiting for articles to transfer")
            # Don't deactivate - let the loop continue and try to transfer articles
            return

        # Get next article (transitions to 'processing' with heartbeat)
        article = self.state_manager.pop_from_queue()
        if not article:
            logger.warning("Failed to pop article from queue")
            return

        article_id = article.get('id')
        title = article.get('article_title', article.get('title', 'unknown'))
        corrected_content = article.get('corrected_content')
        summary = article.get('summary', get_random_summary())
        stored_changes_count = article.get('changes_count', 0)
        character_count = len(corrected_content) if corrected_content else 0

        logger.info(f"Processing article: {title} (ID: {article_id})")
        logger.info(f"Article has corrected_content: {corrected_content is not None}")
        logger.info(f"Summary: {summary}")
        logger.info(f"Stored changes count: {stored_changes_count}")

        # Start heartbeat task for this article
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(article_id))

        if not corrected_content:
            logger.error(f"Article '{title}' has no corrected_content, skipping to avoid a broken publish/diff")
            heartbeat_task.cancel()
            if self.database:
                self.database.transition_queue_item(article_id, 'error')
                self.database.conn.execute(
                    "UPDATE scheduler_queue SET error_message = 'No corrected_content' WHERE id = ?",
                    (article_id,)
                )
                self.database.conn.commit()
            if self.analyzed_tracker:
                try:
                    self.analyzed_tracker.record_analysis(
                        title=title,
                        page_id=article.get('page_id', 0),
                        revision_id=article.get('revision_id', 0),
                        status=AnalysisStatus.ERROR,
                        decision='error',
                        mode=article.get('mode', 'regex'),
                        changes_count=stored_changes_count,
                        summary=summary,
                        character_count=character_count
                    )
                except Exception as e:
                    logger.error(f"Failed to record analysis for missing content: {e}")
            return

        # Calculate actual changes count by comparing with current Wikipedia content
        actual_changes_count = stored_changes_count
        try:
            import pywikibot
            # Use site from config if available, otherwise create default
            site = self.config.site if self.config.site else pywikibot.Site('fr', 'wikipedia')
            page = pywikibot.Page(site, title)
            if page.exists():
                current_content = page.get()
                import difflib
                diff = list(difflib.unified_diff(
                    current_content.splitlines(keepends=True),
                    corrected_content.splitlines(keepends=True),
                    fromfile='original',
                    tofile='corrected',
                    lineterm=''
                ))
                actual_changes_count = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                logger.info(f"Actual changes count (calculated): {actual_changes_count}")
            else:
                logger.warning(f"Article {title} does not exist, using stored changes count")
        except Exception as e:
            logger.warning(f"Failed to calculate actual changes count: {e}, using stored value")
            actual_changes_count = stored_changes_count

        # Check if changes count exceeds threshold (200)
        if actual_changes_count > 200:
            logger.warning(f"Article '{title}' has {actual_changes_count} changes (threshold: 200), skipping publication")
            logger.info(f"Marked '{title}' as 'to validate manually'")
            heartbeat_task.cancel()
            if self.database:
                self.database.transition_queue_item(article_id, 'error')
                self.database.conn.execute(
                    "UPDATE scheduler_queue SET error_message = 'Changes count exceeds threshold' WHERE id = ?",
                    (article_id,)
                )
                self.database.conn.commit()
            # Update analyzed tracker status
            if self.analyzed_tracker:
                self.analyzed_tracker.record_analysis(
                    title=title,
                    page_id=article.get('page_id', 0),
                    revision_id=article.get('revision_id', 0),
                    status=AnalysisStatus.IGNORED,
                    decision='manual_validation_required',
                    mode=article.get('mode', 'regex'),
                    changes_count=actual_changes_count,
                    summary=summary,
                    corrected_content=corrected_content,
                    character_count=character_count
                )
            return

        # Check if there are actual changes (no changes = skip publication)
        if actual_changes_count == 0:
            logger.info(f"Article '{title}' has no changes, skipping publication")
            heartbeat_task.cancel()
            if self.database:
                self.database.transition_queue_item(article_id, 'published')
            # Update analyzed tracker status
            if self.analyzed_tracker:
                self.analyzed_tracker.record_analysis(
                    title=title,
                    page_id=article.get('page_id', 0),
                    revision_id=article.get('revision_id', 0),
                    status=AnalysisStatus.IGNORED,
                    decision='no_changes',
                    mode=article.get('mode', 'regex'),
                    changes_count=0,
                    summary=summary,
                    corrected_content=corrected_content,
                    character_count=character_count
                )
            return

        # P0 CRITICAL FIX: Complete publication pre-checks (Kill Switch, Scheduler, Article, Revision, Diff, Limits, Hours, Throttling)
        logger.info(f"=== PUBLICATION PRE-CHECKS FOR '{title}' ===")
        
        # 1. Kill Switch check (BOTH sources - database and state file)
        if not self.state_manager.get_state().is_active or (self.kill_switch_manager and self.kill_switch_manager.is_enabled()):
            logger.warning("KILL SWITCH ACTIVATED - ABORTING PUBLICATION (pre-check)")
            heartbeat_task.cancel()
            if self.database:
                self.database.transition_queue_item(article_id, 'retry')
            return
        logger.info("✓ Kill Switch check passed")
        
        # 2. Scheduler active check
        if not self._running:
            logger.warning("Scheduler not active - ABORTING PUBLICATION")
            heartbeat_task.cancel()
            if self.database:
                self.database.transition_queue_item(article_id, 'retry')
            return
        logger.info("✓ Scheduler active check passed")
        
        # 3. Article validity check (already done above, but verify again)
        if not corrected_content:
            logger.error(f"Article '{title}' has no corrected_content - ABORTING PUBLICATION")
            heartbeat_task.cancel()
            if self.database:
                self.database.transition_queue_item(article_id, 'error')
            return
        logger.info("✓ Article validity check passed")
        
        # 4. Revision ID check (will be validated by publisher, but verify we have it)
        revision_id = article.get('revision_id')
        if not revision_id:
            logger.warning(f"Article '{title}' has no revision_id - proceeding without conflict detection")
        else:
            logger.info(f"✓ Revision ID check passed (revision_id={revision_id})")
        
        # 5. Diff validity check (already done above - changes count threshold)
        if actual_changes_count > 200:
            logger.error(f"Article '{title}' exceeds diff threshold - ABORTING PUBLICATION")
            heartbeat_task.cancel()
            if self.database:
                self.database.transition_queue_item(article_id, 'error')
            return
        logger.info(f"✓ Diff validity check passed (changes={actual_changes_count})")
        
        # 6. Daily limit check
        state = self.state_manager.get_state()
        if self.timing_manager.has_reached_daily_limit(state.daily_published_count):
            logger.warning(f"Daily limit reached - ABORTING PUBLICATION")
            heartbeat_task.cancel()
            if self.database:
                self.database.transition_queue_item(article_id, 'retry')
            return
        logger.info(f"✓ Daily limit check passed (published={state.daily_published_count})")
        
        # 7. Working hours check
        current_time = datetime.now()
        if not self.timing_manager.is_within_working_hours(current_time):
            logger.warning(f"Outside working hours - ABORTING PUBLICATION")
            heartbeat_task.cancel()
            if self.database:
                self.database.transition_queue_item(article_id, 'retry')
            return
        logger.info(f"✓ Working hours check passed (time={current_time.strftime('%H:%M')})")
        
        # 8. Throttling check (will be applied by publisher, but log here)
        logger.info("✓ Throttling will be applied by publisher")
        
        logger.info(f"=== ALL PUBLICATION PRE-CHECKS PASSED FOR '{title}' ===")

        # P0 CRITICAL FIX: Re-validation before publication - fetch fresh content and recalculate diff
        logger.info(f"Re-validating article '{title}' before publication...")
        try:
            import pywikibot
            site = self.config.site if self.config.site else pywikibot.Site('fr', 'wikipedia')
            page = pywikibot.Page(site, title)
            if page.exists():
                current_content = page.get()
                import difflib
                diff = list(difflib.unified_diff(
                    current_content.splitlines(keepends=True),
                    corrected_content.splitlines(keepends=True),
                    fromfile='original',
                    tofile='corrected',
                    lineterm=''
                ))
                fresh_changes_count = len([line for line in diff if line.startswith('+') or line.startswith('-')])
                logger.info(f"Fresh changes count (pre-publication validation): {fresh_changes_count}")
                
                # Check if changes count still within threshold
                if fresh_changes_count > 200:
                    logger.warning(f"Article '{title}' has {fresh_changes_count} changes after re-validation (threshold: 200), skipping publication")
                    heartbeat_task.cancel()
                    if self.database:
                        self.database.transition_queue_item(article_id, 'error')
                        self.database.conn.execute(
                            "UPDATE scheduler_queue SET error_message = 'Changes count exceeds threshold after re-validation' WHERE id = ?",
                            (article_id,)
                        )
                        self.database.conn.commit()
                    if self.analyzed_tracker:
                        self.analyzed_tracker.record_analysis(
                            title=title,
                            page_id=article.get('page_id', 0),
                            revision_id=article.get('revision_id', 0),
                            status=AnalysisStatus.IGNORED,
                            decision='manual_validation_required',
                            mode=article.get('mode', 'regex'),
                            changes_count=fresh_changes_count,
                            summary=summary,
                            corrected_content=corrected_content,
                            character_count=character_count
                        )
                    return
                
                # Check if changes count matches expected (within reasonable tolerance)
                if abs(fresh_changes_count - actual_changes_count) > 10:
                    logger.warning(f"Article '{title}' changes count mismatch: expected {actual_changes_count}, calculated {fresh_changes_count}. Page may have been modified.")
                    heartbeat_task.cancel()
                    if self.database:
                        self.database.transition_queue_item(article_id, 'retry')
                        self.database.conn.execute(
                            "UPDATE scheduler_queue SET error_message = 'Changes count mismatch - page modified' WHERE id = ?",
                            (article_id,)
                        )
                        self.database.conn.commit()
                    if self.analyzed_tracker:
                        self.analyzed_tracker.record_analysis(
                            title=title,
                            page_id=article.get('page_id', 0),
                            revision_id=article.get('revision_id', 0),
                            status=AnalysisStatus.ERROR,
                            decision='content_changed_requeue',
                            mode=article.get('mode', 'regex'),
                            changes_count=fresh_changes_count,
                            summary=summary,
                            character_count=character_count
                        )
                    return
                
                logger.info(f"Re-validation successful for '{title}' - changes count: {fresh_changes_count}")
            else:
                logger.warning(f"Article {title} no longer exists, skipping publication")
                heartbeat_task.cancel()
                if self.database:
                    self.database.transition_queue_item(article_id, 'error')
                    self.database.conn.execute(
                        "UPDATE scheduler_queue SET error_message = 'Article no longer exists' WHERE id = ?",
                        (article_id,)
                    )
                    self.database.conn.commit()
                return
        except Exception as e:
            logger.warning(f"Failed to re-validate article '{title}' before publication: {e}, proceeding with caution")
            # Continue with publication but log the warning

        # Transition to 'publishing' state
        if self.database:
            self.database.transition_queue_item(article_id, 'publishing')

        # Émettre PUBLISHING_STARTED
        await self.event_manager.emit(
            EventType.PUBLISHING_STARTED,
            {
                "title": title,
                "changes_count": actual_changes_count
            }
        )

        # Publish the article with revision freshness check
        start_time = datetime.now()
        revision_id = article.get('revision_id')
        success, message = self.publisher.publish(title, corrected_content, summary, expected_revision_id=revision_id)
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Publish result: success={success}, message={message}")

        # Handle revision conflict - requeue for reanalysis
        if not success and "Revision conflict" in message:
            logger.warning(f"Revision conflict detected for '{title}', requeueing for reanalysis")
            if self.database:
                # Re-add to queue with same data for reanalysis
                requeue_data = {
                    'title': title,
                    'page_id': article.get('page_id', 0),
                    'revision_id': article.get('revision_id', 0),
                    'corrected_content': corrected_content,
                    'summary': summary,
                    'changes_count': article.get('changes_count', 0),
                    'original_content': article.get('original_content'),
                    'character_count': article.get('character_count', 0),
                    'total_links': article.get('total_links', 0),
                    'dead_links_count': article.get('dead_links_count', 0),
                    'corrected_links_count': article.get('corrected_links_count', 0),
                    'mode': article.get('mode', 'regex')
                }
                self.database.add_to_scheduler_queue(requeue_data)
                logger.info(f"Requeued '{title}' for reanalysis due to revision conflict")
            # Mark as error in tracker
            state = self.state_manager.get_state()
            stats = state.statistics.copy()
            stats['total_errors'] += 1
            if self.analyzed_tracker:
                self.analyzed_tracker.record_analysis(
                    title=title,
                    page_id=article.get('page_id', 0),
                    revision_id=article.get('revision_id', 0),
                    status=AnalysisStatus.ERROR,
                    decision='revision_conflict_requeued',
                    mode=article.get('mode', 'regex'),
                    changes_count=actual_changes_count,
                    summary=summary,
                    corrected_content=corrected_content,
                    character_count=character_count
                )
            return

        # Cancel heartbeat task
        heartbeat_task.cancel()

        # Update statistics
        stats = state.statistics.copy()
        if success:
            self.state_manager.increment_daily_published()
            stats['total_published'] += 1

            # Update average processing time
            current_avg = stats['avg_processing_time']
            n = stats['total_published']
            stats['avg_processing_time'] = (current_avg * (n - 1) + processing_time) / n

            # Transition to 'published' state
            if self.database:
                self.database.transition_queue_item(article_id, 'published')

            # Mark article as published in tracker if not in dry-run mode
            if not self.config.dry_run and self.published_tracker:
                # Determine mode from queue item metadata
                mode = article.get('mode', 'regex')
                self.published_tracker.mark_as_published(title, category="category", mode=mode, summary=summary)
                logger.info(f"Marked '{title}' as published in tracker (mode: {mode})")

            # Update analyzed tracker status
            if self.analyzed_tracker:
                self.analyzed_tracker.record_analysis(
                    title=title,
                    page_id=article.get('page_id', 0),
                    revision_id=article.get('revision_id', 0),
                    status=AnalysisStatus.PUBLISHED if success else AnalysisStatus.ERROR,
                    decision='published' if success else 'error',
                    mode=article.get('mode', 'regex'),
                    changes_count=actual_changes_count,
                    summary=summary,
                    corrected_content=corrected_content,
                    character_count=character_count
                )
            
            # Émettre PUBLISHED ou ERROR selon le résultat
            if success:
                await self.event_manager.emit(
                    EventType.PUBLISHED,
                    {
                        "title": title,
                        "changes_count": actual_changes_count,
                        "processing_time": processing_time
                    }
                )
            else:
                await self.event_manager.emit(
                    EventType.ERROR,
                    {
                        "title": title,
                        "error": message,
                        "error_type": "publication_failed"
                    }
                )

            logger.info(f"Successfully published: {title}")
        else:
            stats['total_errors'] += 1
            logger.error(f"Failed to publish {title}: {message}")

            # Check retry count for failed publications
            if self.database:
                cursor = self.database.conn.cursor()
                cursor.execute("SELECT retry_count FROM scheduler_queue WHERE id = ?", (article_id,))
                row = cursor.fetchone()
                retry_count = row['retry_count'] if row else 0
                max_publish_retries = 1  # Allow at least 1 retry for failed publications

                if retry_count < max_publish_retries:
                    # Increment retry count and requeue for retry
                    new_retry_count = retry_count + 1
                    logger.info(f"Retrying publication for '{title}' (attempt {new_retry_count}/{max_publish_retries + 1})")
                    self.database.transition_queue_item(article_id, 'retry')
                    self.database.conn.execute(
                        "UPDATE scheduler_queue SET retry_count = ?, error_message = ? WHERE id = ?",
                        (new_retry_count, message, article_id)
                    )
                    self.database.conn.commit()

                    # Re-add to queue for retry with incremented retry_count
                    requeue_data = {
                        'title': title,
                        'page_id': article.get('page_id', 0),
                        'revision_id': article.get('revision_id', 0),
                        'corrected_content': corrected_content,
                        'summary': summary,
                        'changes_count': article.get('changes_count', 0),
                        'original_content': article.get('original_content'),
                        'character_count': article.get('character_count', 0),
                        'total_links': article.get('total_links', 0),
                        'dead_links_count': article.get('dead_links_count', 0),
                        'corrected_links_count': article.get('corrected_links_count', 0),
                        'mode': article.get('mode', 'regex'),
                        'retry_count': new_retry_count  # Pass incremented retry count
                    }
                    self.database.add_to_scheduler_queue(requeue_data)
                    logger.info(f"Requeued '{title}' for publication retry (retry_count={new_retry_count})")

                    # Update analyzed tracker status for retry
                    if self.analyzed_tracker:
                        self.analyzed_tracker.record_analysis(
                            title=title,
                            page_id=article.get('page_id', 0),
                            revision_id=article.get('revision_id', 0),
                            status=AnalysisStatus.ERROR,
                            decision='publication_retry',
                            mode=article.get('mode', 'regex'),
                            changes_count=actual_changes_count,
                            summary=summary,
                            character_count=character_count
                        )
                else:
                    # Max retries exceeded - mark as error
                    logger.error(f"Max publication retries exceeded for '{title}' (retry_count={retry_count})")
                    self.database.transition_queue_item(article_id, 'error')
                    self.database.conn.execute(
                        "UPDATE scheduler_queue SET error_message = ? WHERE id = ?",
                        (f"Max retries exceeded: {message}", article_id)
                    )
                    self.database.conn.commit()

                    # Update analyzed tracker status for error
                    if self.analyzed_tracker:
                        self.analyzed_tracker.record_analysis(
                            title=title,
                            page_id=article.get('page_id', 0),
                            revision_id=article.get('revision_id', 0),
                            status=AnalysisStatus.ERROR,
                            decision='publication_failed_max_retries',
                            mode=article.get('mode', 'regex'),
                            changes_count=actual_changes_count,
                            summary=summary,
                            character_count=character_count
                        )

        self.state_manager.update_state(statistics=stats)

        # Check if periodic pause should trigger
        if self.timing_manager.should_trigger_periodic_pause():
            pause = self.timing_manager.generate_periodic_pause()
            self.state_manager.update_state(
                next_pause_start=pause.start_time.isoformat(),
                next_pause_end=pause.end_time.isoformat()
            )
            logger.info(f"Scheduled periodic pause: {pause.start_time} - {pause.end_time}")

        # Calculate next publish time with random delay (but don't wait here - loop handles it)
        delay = self.timing_manager.generate_random_delay()
        next_publish = datetime.now() + delay

        # Update average publish delay
        stats = self.state_manager.get_state().statistics.copy()
        current_avg = stats['avg_publish_delay']
        n = stats['total_published']
        if n > 0:
            stats['avg_publish_delay'] = (current_avg * (n - 1) + delay.total_seconds() / 60) / n
        self.state_manager.update_state(
            next_publish_time=next_publish.isoformat(),
            statistics=stats
        )

        # Don't wait here - the main loop handles the waiting
        logger.info(f"Next publication scheduled in {delay.total_seconds()/60:.1f} minutes")

    def add_article_to_queue(self, title: str, corrected_content: str, summary: str = None, changes_count: int = 0, mode: str = "regex", page_id: int = 0, revision_id: int = 0) -> None:
        """
        Add an article to the publication queue.

        P1-4 FIX: Now synchronizes with SQLite analysis_results table as single source of truth.
        JSON queue is kept for backward compatibility but SQLite is authoritative.

        Args:
            title: Article title.
            corrected_content: Corrected wikicode.
            summary: Edit summary (if None, will use random summary).
            changes_count: Number of changes made to the article.
            mode: Mode of correction ("regex" or "IA").
            page_id: Wikipedia page ID.
            revision_id: Wikipedia revision ID.
        """
        # Use random summary if none provided
        if summary is None:
            summary = get_random_summary()
        
        article_data = {
            'title': title,
            'corrected_content': corrected_content,
            'summary': summary,
            'changes_count': changes_count,
            'mode': mode,
            'page_id': page_id,
            'revision_id': revision_id,
            'added_at': datetime.now().isoformat()
        }
        
        # Add to JSON queue (backward compatibility)
        self.state_manager.add_to_queue(article_data)
        
        # P1-4 FIX: Also add to SQLite as single source of truth
        if self.database:
            try:
                import uuid
                result_id = str(uuid.uuid4())
                cursor = self.database.conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO analysis_results
                    (id, job_id, article_title, page_id, revision_id, status, mode,
                     changes_count, summary, corrected_content, character_count,
                     analysis_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result_id,
                    f"scheduler_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    title,
                    page_id,
                    revision_id,
                    'pending',  # Status: pending publication
                    mode,
                    changes_count,
                    summary,
                    corrected_content,
                    len(corrected_content) if corrected_content else 0,
                    datetime.now().isoformat()
                ))
                self.database.conn.commit()
                logger.info(f"Added article to SQLite queue (analysis_results): {title}")
            except Exception as e:
                logger.error(f"Failed to add article to SQLite queue: {e}")
        
        logger.info(f"Added article to queue: {title}")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current scheduler status.

        Returns:
            Dictionary with status information.
        """
        state = self.state_manager.get_state()
        current_time = datetime.now()

        return {
            'is_active': state.is_active,
            'queue_size': self.state_manager.get_queue_size(),
            'daily_published': state.daily_published_count,
            'daily_limit': self.timing_manager.MAX_DAILY_PUBLICATIONS,
            'total_published': state.statistics['total_published'],
            'total_analyzed': state.statistics['total_analyzed'],
            'total_errors': state.statistics['total_errors'],
            'total_ignored': state.statistics['total_ignored'],
            'is_within_working_hours': self.timing_manager.is_within_working_hours(current_time),
            'next_publish_time': state.next_publish_time,
            'next_pause_start': state.next_pause_start,
            'next_pause_end': state.next_pause_end,
            'statistics': state.statistics
        }