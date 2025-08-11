# alerts/discord_client.py

import json
import requests
from datetime import datetime
from typing import Optional

class DiscordClient:
    """Handles sending alerts to a Discord webhook."""

    def __init__(self, webhook_url: str):
        """
        Initializes the DiscordClient.

        Args:
            webhook_url: The Discord webhook URL.
        """
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)

    def send_alert(self, title: str, message: str, color: int = 0xFF0000) -> bool:
        """
        Sends a formatted alert to the configured Discord webhook.

        Args:
            title: The title of the embed.
            message: The main content of the alert.
            color: The color of the embed's side strip (in hex).

        Returns:
            True if the alert was sent successfully, False otherwise.
        """
        if not self.enabled:
            print("⚠️ Discord notifications are disabled (no webhook URL).")
            return False

        payload = {
            "embeds": [{
                "title": title,
                "description": message,
                "color": color,
                "footer": {
                    "text": f"Secret_Alerts | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            }]
        }

        # --- THIS IS THE FIX: Log the exact payload before sending ---
        print(f"🔍 DEBUG: Sending Discord payload:\n{json.dumps(payload, indent=2)}")

        try:
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()  # Raise an exception for bad status codes
            print("✅ Discord alert sent successfully.")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to send Discord alert: {e}")
            return False

    def send_vip_alert(self, tickers: list, mode: str) -> bool:
        """
        Sends a high-priority VIP alert for matched tickers.

        Args:
            tickers: A list of VIP tickers that were matched.
            mode: The current market mode (e.g., 'RUSH_HOUR').

        Returns:
            True if the alert was sent successfully, False otherwise.
        """
        title = f"🚨💎 VIP ALERT: {', '.join(tickers)} 💎🚨"
        message = (
            f"**High-priority match detected for VIP ticker(s):** `{', '.join(tickers)}`\n\n"
            f"**Market Mode:** `{mode}`\n\n"
            "This is a high-priority notification. Immediate attention may be required."
        )
        # A gold/yellow color for VIP alerts
        return self.send_alert(title, message, color=0xFFD700)

    def send_standard_alert(self, tickers: list, mode: str, additional_info: Optional[str] = None) -> bool:
        """
        Sends a standard alert for matched tickers.

        Args:
            tickers: A list of tickers that were matched.
            mode: The current market mode.
            additional_info: Optional additional context.

        Returns:
            True if the alert was sent successfully, False otherwise.
        """
        title = f"📈 Standard Alert: {', '.join(tickers)}"
        message = (
            f"**Match detected for ticker(s):** `{', '.join(tickers)}`\n\n"
            f"**Market Mode:** `{mode}`"
        )
        if additional_info:
            message += f"\n\n**Context:** {additional_info}"

        # A blue color for standard alerts
        return self.send_alert(title, message, color=0x00BFFF)