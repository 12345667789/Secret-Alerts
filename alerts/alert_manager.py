# alerts/alert_manager.py

from config.settings import Config
from alerts.discord_client import DiscordClient

class AlertManager:
    """Handles the logic for when and how to send alerts."""

    # --- THIS IS THE FIX ---
    # The __init__ method now correctly accepts both the config
    # and the discord_client as arguments.
    def __init__(self, config: Config, discord_client: DiscordClient):
        """
        Initializes the AlertManager.

        Args:
            config: The main application configuration object.
            discord_client: The client for sending Discord notifications.
        """
        self.config = config
        self.discord = discord_client

    def process_matches(self, matches: list, vip_matches: list, mode: str):
        """
        Processes found matches and sends the appropriate alerts.

        Args:
            matches: A list of standard tickers that were matched.
            vip_matches: A list of VIP tickers that were matched.
            mode: The current market mode (e.g., 'RUSH_HOUR').
        """
        if vip_matches:
            print(f"🔥 VIP Match Found: {', '.join(vip_matches)}")
            self.discord.send_vip_alert(vip_matches, mode)
        
        elif matches:
            print(f"📊 Standard Match Found: {', '.join(matches)}")
            self.discord.send_standard_alert(matches, mode)
            
        else:
            print("✅ No new alerts to send.")

