"""
Timing and scheduling logic for Wikipedia maintenance scheduler.

Handles:
- Random delays between publications
- Periodic pauses (every 25 publications)
- Long daily pauses (2-4 per day, 30-90 minutes)
- Working hours (08:00-23:00)
- Daily limits (100 publications/day)
"""

import random
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Tuple, List
from dataclasses import dataclass
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


@dataclass
class PauseSchedule:
    """Represents a scheduled pause."""
    start_time: datetime
    end_time: datetime
    pause_type: str  # 'periodic' or 'long'


class TimingManager:
    """
    Manages all timing-related logic for the scheduler.
    """
    
    # Configuration constants
    MIN_DELAY_MINUTES = 2
    MAX_DELAY_MINUTES = 4
    
    PUBLICATIONS_PER_PERIODIC_PAUSE = 25
    MIN_PERIODIC_PAUSE_MINUTES = 2
    MAX_PERIODIC_PAUSE_MINUTES = 5
    
    MIN_LONG_PAUSES_PER_DAY = 2
    MAX_LONG_PAUSES_PER_DAY = 4
    MIN_LONG_PAUSE_MINUTES = 15
    MAX_LONG_PAUSE_MINUTES = 30
    
    WORKING_HOUR_START = 0  # 00:00 (24/7 operation)
    WORKING_HOUR_END = 24  # 24:00 (24/7 operation - treated as midnight next day)
    MAX_DAILY_PUBLICATIONS = 100
    
    def __init__(self):
        """Initialize timing manager."""
        self._publications_since_last_pause = 0
        self._load_config()
    
    def _load_config(self) -> None:
        """Load publication delay settings from config.yaml."""
        try:
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "config.yaml"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    if config and 'publication_delays' in config:
                        delay_config = config['publication_delays']
                        if 'min_delay_minutes' in delay_config:
                            self.MIN_DELAY_MINUTES = delay_config['min_delay_minutes']
                        if 'max_delay_minutes' in delay_config:
                            self.MAX_DELAY_MINUTES = delay_config['max_delay_minutes']
                        logger.info(f"Loaded publication delay config: min={self.MIN_DELAY_MINUTES}min, max={self.MAX_DELAY_MINUTES}min")
        except Exception as e:
            logger.warning(f"Failed to load publication delay config: {e}")
    
    def generate_random_delay(self) -> timedelta:
        """
        Generate a random delay between publications (2-4 minutes).
        
        Returns:
            Random delay as timedelta.
        """
        delay_minutes = random.uniform(self.MIN_DELAY_MINUTES, self.MAX_DELAY_MINUTES)
        delay = timedelta(minutes=delay_minutes)
        logger.debug(f"Generated random delay: {delay}")
        return delay
    
    def should_trigger_periodic_pause(self) -> bool:
        """
        Check if a periodic pause should be triggered (every 25 publications).
        
        Returns:
            True if periodic pause should trigger.
        """
        self._publications_since_last_pause += 1
        should_pause = self._publications_since_last_pause >= self.PUBLICATIONS_PER_PERIODIC_PAUSE
        
        if should_pause:
            logger.info(f"Periodic pause triggered after {self._publications_since_last_pause} publications")
            self._publications_since_last_pause = 0
        
        return should_pause
    
    def generate_periodic_pause(self) -> PauseSchedule:
        """
        Generate a periodic pause (5-15 minutes).
        
        Returns:
            PauseSchedule for the pause.
        """
        now = datetime.now()
        duration_minutes = random.uniform(self.MIN_PERIODIC_PAUSE_MINUTES, self.MAX_PERIODIC_PAUSE_MINUTES)
        duration = timedelta(minutes=duration_minutes)
        
        pause = PauseSchedule(
            start_time=now,
            end_time=now + duration,
            pause_type='periodic'
        )
        
        logger.info(f"Generated periodic pause: {duration_minutes:.1f} minutes")
        return pause
    
    def generate_daily_long_pauses(self, current_date: datetime) -> List[PauseSchedule]:
        """
        Generate 2-4 long pauses for the day (30-90 minutes each).
        
        Args:
            current_date: Current date/time.
            
        Returns:
            List of PauseSchedule objects for today's long pauses.
        """
        num_pauses = random.randint(self.MIN_LONG_PAUSES_PER_DAY, self.MAX_LONG_PAUSES_PER_DAY)
        pauses = []
        
        # Generate pauses distributed throughout the working day
        working_start = current_date.replace(
            hour=self.WORKING_HOUR_START,
            minute=0,
            second=0,
            microsecond=0
        )
        # Handle WORKING_HOUR_END = 24 as midnight next day
        if self.WORKING_HOUR_END == 24:
            working_end = (current_date + timedelta(days=1)).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0
            )
        else:
            working_end = current_date.replace(
                hour=self.WORKING_HOUR_END,
                minute=0,
                second=0,
                microsecond=0
            )
        working_duration = (working_end - working_start).total_seconds()
        
        # Divide working day into segments and place pauses randomly
        segment_duration = working_duration / (num_pauses + 1)
        
        for i in range(num_pauses):
            # Random offset within segment
            offset = random.uniform(0, segment_duration * 0.8)
            pause_start = working_start + timedelta(seconds=(i + 1) * segment_duration + offset)
            
            # Ensure pause is within working hours
            if pause_start >= working_end:
                pause_start = working_end - timedelta(minutes=60)
            
            duration_minutes = random.uniform(self.MIN_LONG_PAUSE_MINUTES, self.MAX_LONG_PAUSE_MINUTES)
            pause_end = pause_start + timedelta(minutes=duration_minutes)
            
            # Ensure pause doesn't exceed working hours
            if pause_end > working_end:
                pause_end = working_end
                duration_minutes = (pause_end - pause_start).total_seconds() / 60
            
            if pause_end > pause_start:
                pauses.append(PauseSchedule(
                    start_time=pause_start,
                    end_time=pause_end,
                    pause_type='long'
                ))
                logger.info(f"Scheduled long pause {i+1}/{num_pauses}: {pause_start.strftime('%H:%M')} - {pause_end.strftime('%H:%M')}")
        
        return pauses
    
    def is_within_working_hours(self, current_time: Optional[datetime] = None) -> bool:
        """
        Check if current time is within working hours (08:00-23:00).
        
        Args:
            current_time: Time to check (defaults to now).
            
        Returns:
            True if within working hours.
        """
        if current_time is None:
            current_time = datetime.now()
        
        current_hour = current_time.hour
        # Handle WORKING_HOUR_END = 24 as always within working hours for current hour
        if self.WORKING_HOUR_END == 24:
            is_working = current_hour >= self.WORKING_HOUR_START
        else:
            is_working = self.WORKING_HOUR_START <= current_hour < self.WORKING_HOUR_END
        
        if not is_working:
            logger.debug(f"Outside working hours: {current_time.strftime('%H:%M')}")
        
        return is_working
    
    def get_next_working_hour_start(self, current_time: Optional[datetime] = None) -> datetime:
        """
        Get the next working hour start time.
        
        Args:
            current_time: Current time (defaults to now).
            
        Returns:
            Next working hour start datetime.
        """
        if current_time is None:
            current_time = datetime.now()
        
        # If currently before 08:00, next start is today at 08:00
        if current_time.hour < self.WORKING_HOUR_START:
            return current_time.replace(
                hour=self.WORKING_HOUR_START,
                minute=0,
                second=0,
                microsecond=0
            )
        # If currently after working hour end, next start is tomorrow at start
        elif current_time.hour >= self.WORKING_HOUR_END or (self.WORKING_HOUR_END == 24 and current_time.hour == 23):
            tomorrow = current_time + timedelta(days=1)
            return tomorrow.replace(
                hour=self.WORKING_HOUR_START,
                minute=0,
                second=0,
                microsecond=0
            )
        # Already within working hours
        else:
            return current_time
    
    def has_reached_daily_limit(self, daily_count: int) -> bool:
        """
        Check if daily publication limit has been reached.
        
        Args:
            daily_count: Number of publications today.
            
        Returns:
            True if limit reached.
        """
        reached = daily_count >= self.MAX_DAILY_PUBLICATIONS
        if reached:
            logger.warning(f"Daily limit reached: {daily_count}/{self.MAX_DAILY_PUBLICATIONS}")
        return reached
    
    def is_in_pause(self, current_time: Optional[datetime] = None, 
                   pause_schedules: Optional[List[PauseSchedule]] = None) -> Tuple[bool, Optional[PauseSchedule]]:
        """
        Check if currently in a scheduled pause.
        
        Args:
            current_time: Current time (defaults to now).
            pause_schedules: List of active pause schedules.
            
        Returns:
            Tuple of (is_in_pause, active_pause_schedule).
        """
        if current_time is None:
            current_time = datetime.now()
        
        if not pause_schedules:
            return False, None
        
        for pause in pause_schedules:
            if pause.start_time <= current_time < pause.end_time:
                logger.debug(f"Currently in {pause.pause_type} pause until {pause.end_time.strftime('%H:%M')}")
                return True, pause
        
        return False, None
    
    def get_next_pause(self, current_time: Optional[datetime] = None,
                      pause_schedules: Optional[List[PauseSchedule]] = None) -> Optional[PauseSchedule]:
        """
        Get the next upcoming pause.
        
        Args:
            current_time: Current time (defaults to now).
            pause_schedules: List of active pause schedules.
            
        Returns:
            Next pause schedule or None if no upcoming pauses.
        """
        if current_time is None:
            current_time = datetime.now()
        
        if not pause_schedules:
            return None
        
        # Filter for future pauses
        future_pauses = [p for p in pause_schedules if p.start_time > current_time]
        
        if future_pauses:
            return min(future_pauses, key=lambda p: p.start_time)
        
        return None
