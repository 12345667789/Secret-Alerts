# config/settings.py

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
    rush_start: str = "08:20"
    rush_end: str = "10:00"
    market_end: str = "15:30"

# --- This is the correct and COMPLETE Config class ---
@dataclass
class Config:
    """Main configuration for the Secret_Alerts system."""
    discord_webhook: str = os.environ.get("DISCORD_WEBHOOK", "")
    
    # --- THIS IS THE FIX ---
    # Updated to the correct URL for CBOE short sale circuit breaker data.
    cboe_url: str = "https://www.cboe.com/us/equities/market_statistics/short_sale_circuit_breakers/downloads/BatsCircuitBreakers2025.csv"
    
    vip_tickers: List[str] = field(default_factory=lambda: ["TSLA", "HOOD", "RBLX", "UVXY", "TEM", "GOOGL"])
    keywords: List[str] = field(default_factory=lambda: ["BLOCK", "TRADE", "SWEEP", "UNUSUAL"])
    
    # Adding the missing interval attributes back into the config.
    check_interval: int = int(os.environ.get('CHECK_INTERVAL', 300))  # 5 minutes
    rush_interval: int = int(os.environ.get('RUSH_INTERVAL', 60))     # 1 minute

    trading_hours: TradingHours = field(default_factory=TradingHours)
    timezone: Timezone = field(default_factory=Timezone)

def get_config() -> Config:
    """
    Initializes and returns the main application configuration.
    """
    return Config()
