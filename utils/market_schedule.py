# utils/market_schedule.py

from datetime import datetime
import pytz
from config.settings import Config

class MarketScheduler:
    """Handles market open/close times and check intervals."""

    def __init__(self, config: Config):
        self.config = config
        self.timezone = pytz.timezone(config.timezone.local)

    def get_current_time(self) -> datetime:
        """Gets the current time in the market's timezone."""
        return datetime.now(self.timezone)

    def get_current_mode(self) -> str:
        """Determines the current market mode."""
        now = self.get_current_time()
        
        # Note: This logic assumes config times are in 24-hour format HH:MM
        rush_start_time = self.timezone.localize(now.replace(hour=int(self.config.trading_hours.rush_start.split(':')[0]), minute=int(self.config.trading_hours.rush_start.split(':')[1]), second=0, microsecond=0))
        rush_end_time = self.timezone.localize(now.replace(hour=int(self.config.trading_hours.rush_end.split(':')[0]), minute=int(self.config.trading_hours.rush_end.split(':')[1]), second=0, microsecond=0))
        market_open_time = self.timezone.localize(now.replace(hour=self.config.trading_hours.market_open, minute=0, second=0, microsecond=0))
        market_close_time = self.timezone.localize(now.replace(hour=self.config.trading_hours.market_close, minute=0, second=0, microsecond=0))

        if rush_start_time <= now < rush_end_time:
            return 'RUSH_HOUR'
        if market_open_time <= now < market_close_time:
            return 'NORMAL_HOURS'
        
        # Simplified pre/post market logic for this example
        if now < market_open_time:
            return 'PRE_MARKET'
        if now > market_close_time:
            return 'AFTER_HOURS'

        return 'CLOSED'

    def should_monitor(self) -> bool:
        """Determines if the system should be actively monitoring."""
        # For now, we monitor during all market phases except closed.
        return self.get_current_mode() != 'CLOSED'

    def get_check_interval(self) -> int:
        """
        Gets the appropriate check interval based on the current market mode.
        """
        # --- THIS IS THE FIX ---
        # The 'check_interval' and 'rush_interval' are now accessed as direct
        # attributes of the config object, not as methods.
        if self.get_current_mode() == 'RUSH_HOUR':
            return self.config.rush_interval
        return self.config.check_interval

    def get_current_status(self) -> tuple[str, str]:
        """Returns a tuple of the current mode and a human-readable status."""
        mode = self.get_current_mode()
        if self.should_monitor():
            status = f"Active & Monitoring (Interval: {self.get_check_interval()}s)"
        else:
            status = "Inactive - Market Closed"
        return mode, status
        
    def get_status_dict(self) -> dict:
        """Returns a dictionary with current market status."""
        mode, status_text = self.get_current_status()
        return {
            "mode": mode,
            "status_text": status_text,
            "should_monitor": self.should_monitor(),
            "check_interval_seconds": self.get_check_interval(),
            "current_time_local": self.get_current_time().isoformat()
        }

