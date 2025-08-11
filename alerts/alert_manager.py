# alerts/alert_manager.py
"""
Alert Manager - Handles the logic for when and how to send alerts.
Now formats detailed change alerts, including the underlying symbol.
"""

from config.settings import Config
from alerts.discord_client import DiscordClient
from datetime import datetime
import pytz

class AlertManager:
    """Handles the logic for when and how to send alerts."""

    def __init__(self, config: Config, discord_client: DiscordClient):
        self.config = config
        self.discord = discord_client
        print(f"✅ AlertManager initialized with Discord enabled: {self.discord.enabled}")

    def _format_breaker_line(self, breaker: dict, event_type: str) -> str:
        """Formats a single line for a circuit breaker event."""
        symbol = breaker.get('SYMBOL', 'N/A')
        underlying = breaker.get('underlying_symbol')
        security_name = breaker.get('SECURITY_NAME', breaker.get('SECURITY_NAME_new', 'N/A'))
        vip_label = " 💎" if breaker.get('is_vip') else ""
        
        # --- THIS IS THE FIX ---
        # Prioritize showing the underlying symbol first for readability.
        if underlying:
            symbol_display = f"**{underlying}** ({symbol})"
        else:
            symbol_display = f"**{symbol}**"

        if event_type == 'active':
            time_str = f"Halted at {breaker.get('TRIGGER_TIME', 'N/A')}"
        elif event_type == 'started':
            time_str = f"Started {breaker.get('TRIGGER_TIME', 'N/A')}"
        elif event_type == 'ended':
            time_str = f"Ended {breaker.get('END_TIME_new', 'N/A')}"
        else:
            time_str = ""

        return f"• {symbol_display}{vip_label} - _{security_name}_ ({time_str})"

    def process_circuit_breaker_matches(self, additional_data=None, **kwargs):
        """
        Process circuit breaker matches with detailed formatting for different scenarios.
        """
        additional_data = additional_data or {}
        
        # Scenario 1: Manual check for ACTIVE breakers
        if additional_data.get('manual_check'):
            print("✅ Formatting a manual check for active breakers.")
            active_breakers = additional_data.get('active_breakers_list', [])
            title = "🚨 Manual Check: Active Circuit Breakers"
            color = 0xffa500  # Orange

            if not active_breakers:
                message = "No actively halted tickers found at this time."
            else:
                message_lines = [f"**Found {len(active_breakers)} actively halted ticker(s):**\n"]
                message_lines.extend([self._format_breaker_line(b, 'active') for b in active_breakers])
                message = "\n".join(message_lines)
            
            return self.discord.send_alert(title, message, color)

        # Scenario 2: Automatic check with DETAILED changes (started/ended)
        elif 'started' in additional_data or 'ended' in additional_data:
            print("✅ Formatting a detailed change alert.")
            started_list = additional_data.get('started', [])
            ended_list = additional_data.get('ended', [])
            
            title = f"⚡ CBOE Changes: {len(started_list)} Started, {len(ended_list)} Ended"
            color = 0x00BFFF
            message_lines = [f"**CHANGES DETECTED** at {self.get_current_time()}\n"]

            if started_list:
                message_lines.append(f"**🆕 {len(started_list)} STARTED:**")
                message_lines.extend([self._format_breaker_line(item, 'started') for item in started_list])
                message_lines.append("")

            if ended_list:
                message_lines.append(f"**✅ {len(ended_list)} ENDED:**")
                message_lines.extend([self._format_breaker_line(item, 'ended') for item in ended_list])

            message = "\n".join(message_lines)
            return self.discord.send_alert(title, message, color)
            
        else:
            print("✅ No detailed changes to process.")
            return True

    def send_system_alert(self, title: str, message: str, color: int = 0x00FF00):
        """Send system status alerts (startup, shutdown, errors, etc.)"""
        print(f"🔍 DEBUG: send_system_alert called - Title: {title}")
        return self.discord.send_alert(title, message, color)

    def get_current_time(self) -> str:
        """Get current time formatted for alerts"""
        return datetime.now(pytz.timezone('America/Chicago')).strftime('%-I:%M:%S %p CST')
