# utils/market_schedule.py

from datetime import datetime, time
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
        try:
            now = self.get_current_time()
            today = now.date()
            
            # Create naive time objects from strings/ints in config
            rush_start_t = time.fromisoformat(self.config.trading_hours.rush_start)
            rush_end_t = time.fromisoformat(self.config.trading_hours.rush_end)
            market_open_t = time(self.config.trading_hours.market_open)
            market_close_t = time(self.config.trading_hours.market_close)
            
            # Create naive datetime objects
            rush_start_dt = datetime.combine(today, rush_start_t)
            rush_end_dt = datetime.combine(today, rush_end_t)
            market_open_dt = datetime.combine(today, market_open_t)
            market_close_dt = datetime.combine(today, market_close_t)
            
            # FIXED: Use replace instead of localize to avoid timezone conflicts
            # Convert timezone-aware 'now' to naive for comparison
            naive_now = now.replace(tzinfo=None)
            
            # Compare with naive datetime objects (much safer)
            if rush_start_dt <= naive_now < rush_end_dt:
                return 'RUSH_HOUR'
            if market_open_dt <= naive_now < market_close_dt:
                return 'NORMAL_HOURS'
            if naive_now < market_open_dt:
                return 'PRE_MARKET'
            if naive_now > market_close_dt:
                return 'AFTER_HOURS'
                
            return 'CLOSED'
            
        except Exception as e:
            # Fallback to prevent crashes
            print(f"⚠️ WARNING: Market mode detection failed: {e}")
            print("🔧 Using fallback mode: NORMAL_HOURS")
            return 'NORMAL_HOURS'
    
    def should_monitor(self) -> bool:
        """Determines if the system should be actively monitoring."""
        try:
            mode = self.get_current_mode()
            return mode in ['RUSH_HOUR', 'NORMAL_HOURS', 'PRE_MARKET', 'AFTER_HOURS']
        except Exception:
            # Safe fallback - always monitor if there's an error
            return True
    
    def get_check_interval(self) -> int:
        """
        Gets the appropriate check interval based on the current market mode.
        """
        try:
            if self.get_current_mode() == 'RUSH_HOUR':
                return self.config.rush_interval
            return self.config.check_interval
        except Exception:
            # Safe fallback interval
            return getattr(self.config, 'check_interval', 300)
    
    def get_current_status(self) -> tuple[str, str]:
        """Returns a tuple of the current mode and a human-readable status."""
        try:
            mode = self.get_current_mode()
            if self.should_monitor():
                status = f"Active & Monitoring (Interval: {self.get_check_interval()}s)"
            else:
                status = "Inactive - Market Closed"
            return mode, status
        except Exception as e:
            # Safe fallback status
            return "NORMAL_HOURS", f"Fallback mode - Error: {str(e)[:50]}"
    
    def get_status_dict(self) -> dict:
        """Returns a dictionary with current market status."""
        try:
            mode, status_text = self.get_current_status()
            return {
                "mode": mode,
                "status_text": status_text,
                "should_monitor": self.should_monitor(),
                "check_interval_seconds": self.get_check_interval(),
                "current_time_local": self.get_current_time().isoformat()
            }
        except Exception as e:
            # Safe fallback dictionary
            return {
                "mode": "NORMAL_HOURS",
                "status_text": f"Error mode - {str(e)[:50]}",
                "should_monitor": True,
                "check_interval_seconds": 300,
                "current_time_local": datetime.now().isoformat()
            }