# services/speed_monitor.py
"""
Lightweight speed monitor that runs parallel to the main system
Focused purely on speed - 2-3 minute alerts
"""

import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from io import StringIO
from collections import deque
from alerts.discord_client import DiscordClient
from config.settings import get_config_from_firestore

class SpeedMonitor:
    """Ultra-fast parallel monitoring system"""
    
    def __init__(self):
        self.cboe_url = "https://www.cboe.com/us/equities/market_statistics/short_sale_circuit_breakers/downloads/BatsCircuitBreakers2025.csv"
        self.logger = logging.getLogger(__name__)
        self.last_check_data = None
        self.activity_log = deque(maxlen=50)  # Keep last 50 activities
        self.last_health_report = None
        self.check_count = 0
        self.error_count = 0
        
    def quick_check(self) -> bool:
        """
        Super fast check - just look for NEW entries since last check
        Returns True if new alerts found and sent
        """
        self.check_count += 1
        start_time = datetime.now()
        
        try:
            # Fast fetch with aggressive timeout
            current_data = self._fetch_fast()
            if current_data is None:
                self.error_count += 1
                self._log_activity("ERROR", "Failed to fetch CBOE data")
                return False
                
            # Quick comparison - just check if row count increased
            if self.last_check_data is not None:
                old_count = len(self.last_check_data)
                new_count = len(current_data)
                
                if new_count > old_count:
                    # New entries detected!
                    new_entries = current_data.tail(new_count - old_count)
                    symbols = new_entries['Symbol'].tolist()
                    self._send_speed_alert(new_entries)
                    self._log_activity("ALERT", f"Sent speed alert for: {', '.join(symbols)}")
                    self.logger.info(f"⚡ SPEED ALERT: {new_count - old_count} new entries detected")
                else:
                    self._log_activity("CHECK", f"No new entries ({len(current_data)} total)")
                    
            else:
                self._log_activity("INIT", f"Initial load: {len(current_data)} circuit breakers")
                
            self.last_check_data = current_data
            
            # Log performance
            duration = (datetime.now() - start_time).total_seconds()
            self._log_activity("PERF", f"Check completed in {duration:.2f}s")
            
            return True
            
        except Exception as e:
            self.error_count += 1
            self._log_activity("ERROR", f"Exception: {str(e)}")
            self.logger.error(f"Speed check failed: {e}")
            return False
    
    def _fetch_fast(self):
        """Aggressive fast fetch"""
        try:
            response = requests.get(
                self.cboe_url,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=3,  # Very short timeout
                stream=False
            )
            response.raise_for_status()
            return pd.read_csv(StringIO(response.text))
        except:
            return None
    
    def _log_activity(self, activity_type: str, message: str):
        """Log activity for health reporting"""
        timestamp = datetime.now()
        self.activity_log.append({
            'timestamp': timestamp,
            'type': activity_type,
            'message': message
        })
    
    def get_status(self) -> dict:
        """Get current status for dashboard"""
        now = datetime.now()
        last_check = self.activity_log[-1]['timestamp'] if self.activity_log else None
        
        # Get recent activity (last 15 minutes)
        fifteen_min_ago = now - timedelta(minutes=15)
        recent_activity = [
            activity for activity in self.activity_log 
            if activity['timestamp'] >= fifteen_min_ago
        ]
        
        return {
            'status': 'Running' if self.check_count > 0 else 'Not Started',
            'total_checks': self.check_count,
            'error_count': self.error_count,
            'success_rate': f"{((self.check_count - self.error_count) / max(self.check_count, 1) * 100):.1f}%",
            'last_check': last_check.strftime('%H:%M:%S') if last_check else 'Never',
            'recent_activity_count': len(recent_activity),
            'current_breaker_count': len(self.last_check_data) if self.last_check_data is not None else 0
        }
    
    def send_health_report(self) -> bool:
        """Send 15-minute health report to Discord"""
        try:
            now = datetime.now()
            
            # Don't send more than once per 15 minutes
            if (self.last_health_report and 
                now - self.last_health_report < timedelta(minutes=14)):
                return False
            
            # Get activity from last 15 minutes
            fifteen_min_ago = now - timedelta(minutes=15)
            recent_activity = [
                activity for activity in self.activity_log 
                if activity['timestamp'] >= fifteen_min_ago
            ]
            
            # Count different activity types
            alerts_sent = len([a for a in recent_activity if a['type'] == 'ALERT'])
            checks_made = len([a for a in recent_activity if a['type'] == 'CHECK'])
            errors = len([a for a in recent_activity if a['type'] == 'ERROR'])
            
            # Build health report message
            status_emoji = "🟢" if errors == 0 else "🟡" if errors < 3 else "🔴"
            
            message = f"""**Speed Monitor Health Report** {status_emoji}
            
**Last 15 Minutes:**
• Checks performed: {checks_made}
• Alerts sent: {alerts_sent}
• Errors: {errors}
• Current breakers: {len(self.last_check_data) if self.last_check_data is not None else 0}

**Overall Stats:**
• Total checks: {self.check_count}
• Success rate: {((self.check_count - self.error_count) / max(self.check_count, 1) * 100):.1f}%
• Status: Online and monitoring every 2 minutes

*{now.strftime('%Y-%m-%d %H:%M:%S')} CST*"""

            webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
            if webhook_url:
                discord = DiscordClient(webhook_url)
                success = discord.send_alert(
                    "📊 Speed Monitor Health", 
                    message, 
                    color=0x00FF00 if errors == 0 else 0xFFFF00 if errors < 3 else 0xFF0000
                )
                
                if success:
                    self.last_health_report = now
                    self._log_activity("HEALTH", "Health report sent")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to send health report: {e}")
            return False
        """Send immediate speed alert - no fancy formatting"""
        try:
            webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
            if not webhook_url:
                return False
                
            discord = DiscordClient(webhook_url)
            
            # Simple, fast alert format
            symbols = new_entries['Symbol'].tolist()
            message = f"⚡ **SPEED ALERT** ⚡\n**NEW CIRCUIT BREAKERS:** {', '.join(symbols)}\n*Detected at {datetime.now().strftime('%H:%M:%S')}*"
            
            return discord.send_alert(
                "🚨 Fast Detection System", 
                message, 
                color=0xFF4500  # Orange red for speed alerts
            )
        except Exception as e:
            self.logger.error(f"Failed to send speed alert: {e}")
            return False

# --- Flask Routes for Speed Monitor ---
# Add these to your main.py

# Global speed monitor instance
speed_monitor = SpeedMonitor()

@app.route('/speed-check', methods=['POST'])
def speed_check_endpoint():
    """New endpoint for 2-minute speed checks"""
    app.logger.info("⚡ Speed check triggered")
    
    try:
        success = speed_monitor.quick_check()
        
        if success:
            return "Speed check completed", 200
        else:
            return "Speed check failed", 500
            
    except Exception as e:
        app.logger.error(f"Speed check error: {e}")
        return "Speed check error", 500

@app.route('/speed-health', methods=['POST'])
def speed_health_endpoint():
    """Endpoint for 15-minute health reports"""
    app.logger.info("📊 Speed health report triggered")
    
    try:
        success = speed_monitor.send_health_report()
        return "Health report sent" if success else "Health report skipped", 200
            
    except Exception as e:
        app.logger.error(f"Speed health error: {e}")
        return "Speed health error", 500

@app.route('/api/speed-status')
def speed_status_api():
    """API endpoint for dashboard status"""
    try:
        status = speed_monitor.get_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500