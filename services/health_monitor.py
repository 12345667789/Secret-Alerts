# services/health_monitor.py

import threading
import pytz
from collections import deque
from datetime import datetime

# --- Enhanced Health Monitor Class ---
class EnhancedHealthMonitor:
    """
    Enhanced health monitor with intelligence tracking
    Backwards compatible with existing HealthMonitor interface
    """
    def __init__(self, max_log_size=100, max_ledger_size=200):
        self.lock = threading.Lock()
        self.cst = pytz.timezone('America/Chicago')
        self.last_check_status = {
            "timestamp": None,
            "successful": False,
            "file_hash": "N/A",
            "error_message": "No checks run yet."
        }
        self.transaction_log = deque(maxlen=max_log_size)
        self.alert_ledger = deque(maxlen=max_ledger_size)
        self.log_transaction("Enhanced System Initialized", "INFO")

    def _get_current_time_str(self):
        return datetime.now(self.cst).strftime('%Y-%m-%d %H:%M:%S CST')

    def record_check_attempt(self, success: bool, file_hash: str = "N/A", error: str = None):
        """Record check attempt (unchanged for backwards compatibility)"""
        with self.lock:
            self.last_check_status = {
                "timestamp": self._get_current_time_str(),
                "successful": success,
                "file_hash": file_hash if success else "FAILED",
                "error_message": error
            }
        if success:
            self.log_transaction(f"Data fetch and analysis successful.", "SUCCESS")
        else:
            self.log_transaction(f"Data fetch FAILED. Reason: {error}", "ERROR")

    def log_transaction(self, message: str, level: str = "INFO"):
        """Log transaction (unchanged for backwards compatibility)"""
        with self.lock:
            self.transaction_log.appendleft({
                "timestamp": self._get_current_time_str(),
                "message": message,
                "level": level
            })

    def record_alert_sent(self, alert_id: str, alert_type: str, symbol: str, details: str):
        """
        Original method for backwards compatibility
        Calls enhanced version with default values
        """
        return self.record_alert_sent_enhanced(
            alert_id=alert_id,
            alert_type=alert_type,
            symbol=symbol,
            details=details,
            frequency=1,
            double_mint=False,
            priority="STANDARD"
        )

    def record_alert_sent_enhanced(self, alert_id: str, alert_type: str, symbol: str, details: str,
                                 frequency: int = 1, double_mint: bool = False, priority: str = "STANDARD"):
        """
        Enhanced alert recording with intelligence data
        """
        with self.lock:
            self.alert_ledger.appendleft({
                "alert_id": alert_id,
                "timestamp": self._get_current_time_str(),
                "alert_type": alert_type,
                "symbol": symbol,
                "details": details,
                "frequency": frequency,
                "double_mint": double_mint,
                "priority": priority
            })

        # Enhanced logging message
        priority_emoji = "💎" if priority == "VIP" else "🔥" if priority == "HIGH" else "🔵"
        mint_indicator = " 🃏" if double_mint else ""
        log_message = f"Alert Sent (ID: {alert_id}) {priority_emoji} {symbol} ({frequency}x){mint_indicator}"

        self.log_transaction(log_message, "SUCCESS")

    def get_health_snapshot(self):
        """Get health snapshot (enhanced with intelligence data)"""
        with self.lock:
            # Calculate intelligence stats
            alerts = list(self.alert_ledger)
            intelligence_stats = {
                "total_alerts": len(alerts),
                "vip_alerts": len([a for a in alerts if a.get('priority') == 'VIP']),
                "double_mint_alerts": len([a for a in alerts if a.get('double_mint', False)]),
                "high_frequency_alerts": len([a for a in alerts if a.get('frequency', 1) >= 15])
            }

            return {
                "last_check": self.last_check_status.copy(),
                "transactions": list(self.transaction_log),
                "alerts": alerts,
                "intelligence_stats": intelligence_stats
            }

    def get_intelligence_summary(self):
        """Get summary of intelligence data"""
        with self.lock:
            alerts = list(self.alert_ledger)

            if not alerts:
                return {
                    "message": "No alerts recorded yet",
                    "stats": {}
                }

            # Calculate statistics
            vip_count = len([a for a in alerts if a.get('priority') == 'VIP'])
            double_mint_count = len([a for a in alerts if a.get('double_mint', False)])
            high_freq_count = len([a for a in alerts if a.get('frequency', 1) >= 15])
            avg_frequency = sum(a.get('frequency', 1) for a in alerts) / len(alerts)

            return {
                "message": f"Intelligence tracking active",
                "stats": {
                    "total_alerts": len(alerts),
                    "vip_alerts": vip_count,
                    "double_mint_alerts": double_mint_count,
                    "high_frequency_alerts": high_freq_count,
                    "average_frequency": round(avg_frequency, 1)
                }
            }