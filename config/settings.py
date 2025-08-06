# config/settings.py

"""
Configuration management for the Secret_Alerts Trading System
"""
import os
from dataclasses import dataclass, field
from typing import List, Tuple

# --- These classes MUST be defined BEFORE the main Config class ---
@dataclass
class Timezone:
    """Represents timezone settings for market hours."""
    local: str = "America/New_York"
    utc: str = "UTC"

@dataclass
class TradingHours:
    """Represents the trading hours for the market."""
    pre_market_start: int = 4
    market_open: int = 9
    market_close: int = 16
    after_hours_end: int = 20
    rush_hour_windows: List[Tuple[int, int]] = field(default_factory=lambda: [(9, 10), (15, 16)])
    # --- THIS IS THE FIX ---
    # Adding the missing time attributes that market_schedule.py needs.
    rush_start: str = "08:20"
    rush_end: str = "10:00"
    market_end: str = "15:30"

# --- This is the correct Config class that main.py expects ---
@dataclass
class Config:
    """Main configuration for the Secret_Alerts system."""
    discord_webhook: str = os.environ.get("DISCORD_WEBHOOK", "")
    cboe_url: str = "https://www.cboe.com/us/options/market_statistics/daily_options_volume/csv"
    vip_tickers: List[str] = field(default_factory=lambda: ["SPY", "QQQ", "TSLA", "AAPL", "AMZN", "GOOGL"])
    keywords: List[str] = field(default_factory=lambda: ["BLOCK", "TRADE", "SWEEP", "UNUSUAL"])
    trading_hours: TradingHours = field(default_factory=TradingHours)
    timezone: Timezone = field(default_factory=Timezone)

def get_config() -> Config:
    """
    Initializes and returns the main application configuration.
    This function MUST return an instance of the 'Config' class.
    """
    return Config()
