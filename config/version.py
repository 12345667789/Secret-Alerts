"""
Version and build information for the Secret_Alerts Trading System
"""

VERSION = "4.1"
BUILD_DATE = "2025-08-06"
ARCHITECTURE = "Modular"
DESCRIPTION = "Professional Trading Intelligence System with Multi-Source Monitoring and Market Hours Detection"

# Module versions for tracking
MODULE_VERSIONS = {
    "cboe_monitor": "1.0",
    "alert_manager": "1.0",
    "discord_client": "1.0", 
    "market_scheduler": "1.0",
    "logger": "1.0"
}

def get_version_string() -> str:
    """Get formatted version string"""
    return f"Secret_Alerts v{VERSION} (Built: {BUILD_DATE})"

def get_full_version_info() -> dict:
    """Get complete version information"""
    return {
        "version": VERSION,
        "build_date": BUILD_DATE,
        "architecture": ARCHITECTURE,
        "description": DESCRIPTION,
        "modules": MODULE_VERSIONS
    }