"""
VIP Ticker Management - Special handling for priority stocks
"""

from typing import Dict
from utils.logger import logger

class VIPManager:
    """Special handling for VIP tickers"""
    
    def __init__(self, config):
        self.config = config
        self.alert_manager = None  # Will be set by main system
        self.analyst = None        # Will be set by main system
        
        # VIP-specific rules
        self.vip_rules = {
            'TSLA': {'priority': 'HIGHEST', 'analysis_depth': 'FULL'},
            'NVDA': {'priority': 'HIGHEST', 'analysis_depth': 'FULL'},
            'AAPL': {'priority': 'HIGH', 'analysis_depth': 'STANDARD'},
            'GME': {'priority': 'HIGH', 'analysis_depth': 'MOMENTUM'},
            'AMC': {'priority': 'HIGH', 'analysis_depth': 'MOMENTUM'}
        }
    
    def handle_vip_event(self, match_data: Dict):
        """Handle VIP ticker events with special processing"""
        symbol = match_data['symbol']
        vip_rule = self.vip_rules.get(symbol, {})
        
        logger.info(f"Handling VIP event for {symbol}", "VIP_MANAGER")
        
        # Enhanced VIP alert
        self._send_vip_alert(match_data, vip_rule)
        
        # Trigger analysis if analyst is available
        if self.analyst:
            analysis_depth = vip_rule.get('analysis_depth', 'STANDARD')
            # self.analyst.analyze_vip_ticker(symbol, analysis_depth)
    
    def _send_vip_alert(self, match_data: Dict, vip_rule: Dict):
        """Send enhanced VIP alert"""
        symbol = match_data['symbol']
        priority = vip_rule.get('priority', 'HIGH')
        
        vip_message = f"💎 **VIP CIRCUIT BREAKER ALERT**\n\n"
        vip_message += f"🚀 **Symbol:** {symbol} ({priority} Priority)\n"
        vip_message += f"📊 **Security:** {match_data['security_name']}\n"
        vip_message += f"⏰ **Trigger:** {match_data['trigger_time']}\n"
        vip_message += f"🎯 **Status:** VIP ticker detected\n"
        vip_message += f"📈 **Action:** Enhanced monitoring activated\n"
        
        if self.alert_manager:
            self.alert_manager.discord.send_alert(
                f"💎 VIP Alert: {symbol}",
                vip_message,
                color=0xFFD700  # Gold color for VIP
            )
