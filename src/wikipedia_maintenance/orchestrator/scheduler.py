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

from .scheduler_state import StateManager, SchedulerState
from .timing_manager import TimingManager, PauseSchedule
from .telegram_bot import TelegramBot, create_telegram_bot
from wikipedia_maintenance.utils.published_tracker import PublishedTracker
from wikipedia_maintenance.utils.analyzed_tracker import AnalyzedTracker, AnalysisStatus
from wikipedia_maintenance.utils.edit_summaries import get_random_summary

logger = logging.getLogger(__name__)


@dataclass
class SchedulerConfig:
    """Configuration for the scheduler."""
    state_file: str = "data/scheduler_state.json"
    telegram_bot_token: Optional[str] = None
    telegram_admin_ids: List[int] = None
    dry_run: bool = True
    daily_limit: int = 100
    stop_on_empty_queue: bool = True  # Stop scheduler when queue is empty
    site: Optional[Any] = None  # Pywikibot site object


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
    """

    def __init__(self, config: SchedulerConfig, publisher, published_tracker: Optional[PublishedTracker] = None, analyzed_tracker: Optional[AnalyzedTracker] = None):
        """
        Initialize scheduler.

        Args:
            config: SchedulerConfig with settings.
            publisher: Publisher instance for publishing to Wikipedia.
            published_tracker: PublishedTracker instance for tracking published articles.
            analyzed_tracker: AnalyzedTracker instance for tracking analyzed articles.
        """
        self.config = config
        self.publisher = publisher
        self.published_tracker = published_tracker
        self.analyzed_tracker = analyzed_tracker

        # Initialize components
        self.state_manager = StateManager(config.state_file)
        self.timing_manager = TimingManager()
        self.telegram_bot: Optional[TelegramBot] = None

        # Runtime state
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_pauses: List[PauseSchedule] = []

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
        self._running = True

        # Set state to active immediately
        self.state_manager.set_active(True)

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

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._running:
            logger.warning("Scheduler not running")
            return

        logger.info("Stopping scheduler...")
        self._running = False

        # Set state to inactive immediately
        self.state_manager.set_active(False)

        # Cancel scheduler task immediately
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            except Exception as e:
                logger.error(f"Error awaiting scheduler task shutdown: {e}")
            finally:
                self._task = None

        # Stop Telegram bot
        if self.telegram_bot:
            try:
                await self.telegram_bot.stop()
            except Exception as e:
                logger.error(f"Error stopping Telegram bot: {e}")

        # Save state
        self.state_manager.update_state(
            next_publish_time=None,
            next_pause_start=None,
            next_pause_end=None
        )

        logger.info("Scheduler stopped immediately")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop with P0 CRITICAL FIX: Enhanced Kill Switch."""
        logger.info("Scheduler loop started")

        try:
            # Reset daily counters if needed
            logger.info("Resetting daily counters...")
            self.state_manager.reset_daily_counters()
            logger.info("Daily counters reset")
        except Exception as e:
            logger.error(f"Error resetting daily counters: {e}", exc_info=True)

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
            try:
                # P0 CRITICAL FIX: Enhanced Kill Switch check at loop start
                state = self.state_manager.get_state()
                if not state.is_active:
                    logger.warning("KILL SWITCH ACTIVATED - EXITING SCHEDULER LOOP")
                    break
                    
                logger.info("=== Scheduler loop iteration ===")
                logger.info(f"Kill Switch status: is_active={state.is_active}")
                logger.info(f"Queue size: {len(state.queue)}, Daily published: {state.daily_published_count}")

                # Check if queue is empty and stop if configured
                if len(state.queue) == 0 and self.config.stop_on_empty_queue:
                    logger.info("Queue is empty and stop_on_empty_queue is enabled, stopping scheduler")
                    self._running = False
                    break

                # P0 CRITICAL FIX: Don't auto-activate if Kill Switch is off
                if not state.is_active:
                    logger.warning("KILL SWITCH ACTIVATED - Scheduler inactive, not auto-activating")
                    await asyncio.sleep(10)  # Wait before checking again
                    continue

                # Reset daily counters if day changed
                self.state_manager.reset_daily_counters()
                state = self.state_manager.get_state()

                # Check working hours
                current_time = datetime.now()
                logger.info(f"Current time: {current_time.strftime('%H:%M')}")
                logger.info(f"Working hours: {self.timing_manager.WORKING_HOUR_START}:00 - {self.timing_manager.WORKING_HOUR_END}:00")
                logger.info(f"Within working hours: {self.timing_manager.is_within_working_hours(current_time)}")

                # P0 CRITICAL FIX: Check Kill Switch before any operation
                if not self.state_manager.get_state().is_active:
                    logger.warning("KILL SWITCH ACTIVATED - STOPPING SCHEDULER LOOP")
                    break

                if not self.timing_manager.is_within_working_hours(current_time):
                    next_working = self.timing_manager.get_next_working_hour_start(current_time)
                    wait_time = (next_working - current_time).total_seconds()
                    logger.info(f"Outside working hours, waiting until {next_working.strftime('%H:%M')}")
                    self.state_manager.update_state(next_publish_time=next_working.isoformat())
                    # Sleep in short intervals to allow cancellation with Kill Switch check
                    while wait_time > 0 and self._running:
                        # P0 CRITICAL FIX: Check Kill Switch during wait
                        if not self.state_manager.get_state().is_active:
                            logger.warning("KILL SWITCH ACTIVATED - ABORTING WAIT")
                            break
                        sleep_time = min(wait_time, 30)  # Sleep max 30 seconds at a time
                        await asyncio.sleep(sleep_time)
                        wait_time -= sleep_time
                    if not self.state_manager.get_state().is_active:
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
                        # P0 CRITICAL FIX: Check Kill Switch during wait
                        if not self.state_manager.get_state().is_active:
                            logger.warning("KILL SWITCH ACTIVATED - ABORTING WAIT")
                            break
                        sleep_time = min(wait_time, 30)  # Sleep max 30 seconds at a time
                        await asyncio.sleep(sleep_time)
                        wait_time -= sleep_time
                    if not self.state_manager.get_state().is_active:
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
                        # P0 CRITICAL FIX: Check Kill Switch during wait
                        if not self.state_manager.get_state().is_active:
                            logger.warning("KILL SWITCH ACTIVATED - ABORTING WAIT")
                            break
                        sleep_time = min(wait_time, 30)  # Sleep max 30 seconds at a time
                        await asyncio.sleep(sleep_time)
                        wait_time -= sleep_time
                    if not self.state_manager.get_state().is_active:
                        break
                    continue

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

    async def _process_next_article(self) -> None:
        """Process the next article from the queue."""
        logger.info("=== _process_next_article called ===")
        state = self.state_manager.get_state()

        logger.info(f"Queue size before processing: {len(state.queue)}")

        # Check if queue is empty
        if not state.queue:
            logger.info("Queue is empty, deactivating scheduler")
            self.state_manager.update_state(is_active=False)
            self._running = False
            return

        # Get next article
        article = self.state_manager.pop_from_queue()
        if not article:
            logger.warning("Failed to pop article from queue")
            return

        title = article.get('title', 'unknown')
        corrected_content = article.get('corrected_content')
        summary = article.get('summary', get_random_summary())
        stored_changes_count = article.get('changes_count', 0)

        logger.info(f"Processing article: {title}")
        logger.info(f"Article has corrected_content: {corrected_content is not None}")
        logger.info(f"Summary: {summary}")
        logger.info(f"Stored changes count: {stored_changes_count}")

        if not corrected_content:
            logger.error(f"Article '{title}' has no corrected_content, skipping to avoid a broken publish/diff")
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
                        summary=summary
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
                    corrected_content=corrected_content
                )
            return

        # Check if there are actual changes (no changes = skip publication)
        if actual_changes_count == 0:
            logger.info(f"Article '{title}' has no changes, skipping publication")
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
                    corrected_content=corrected_content
                )
            return

        # P0 CRITICAL FIX: Enhanced Kill Switch check before publication
        if not self.state_manager.get_state().is_active:
            logger.warning("KILL SWITCH ACTIVATED - ABORTING PUBLICATION")
            return

        # Publish the article
        start_time = datetime.now()
        success, message = self.publisher.publish(title, corrected_content, summary)
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Publish result: success={success}, message={message}")

        # Update statistics
        stats = state.statistics.copy()
        if success:
            self.state_manager.increment_daily_published()
            stats['total_published'] += 1

            # Update average processing time
            current_avg = stats['avg_processing_time']
            n = stats['total_published']
            stats['avg_processing_time'] = (current_avg * (n - 1) + processing_time) / n

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
                    corrected_content=corrected_content  # Preserve corrected content
                )

            logger.info(f"Successfully published: {title}")
        else:
            stats['total_errors'] += 1
            logger.error(f"Failed to publish {title}: {message}")

            # Update analyzed tracker status for error
            # Fixed: previously referenced an undefined `changes_count`
            # variable here (NameError), which silently aborted error
            # tracking for every failed publish. Now uses the computed
            # `actual_changes_count`, matching the success branch above.
            if self.analyzed_tracker:
                self.analyzed_tracker.record_analysis(
                    title=title,
                    page_id=article.get('page_id', 0),
                    revision_id=article.get('revision_id', 0),
                    status=AnalysisStatus.ERROR,
                    decision='error',
                    mode=article.get('mode', 'regex'),
                    changes_count=actual_changes_count,
                    summary=summary
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
        self.state_manager.add_to_queue(article_data)
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
            'queue_size': len(state.queue),
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