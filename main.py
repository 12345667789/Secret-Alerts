import os
import logging
import pandas as pd
import json
import threading
import time as time_module  # FIXED: Renamed to avoid conflict with datetime.time
from collections import deque, defaultdict
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from google.cloud import firestore
from datetime import datetime, timedelta
import pytz
import hashlib

# Import our modular components
from alerts.discord_client import DiscordClient
from alerts.templates import AlertTemplateManager
from alerts.enhanced_alert_manager import EnhancedAlertManager
from monitors.cboe_monitor import ShortSaleMonitor
from testing.time_travel_tester import run_time_travel_test, get_test_suggestions

# --- Smart Alert Batching System ---
class SmartAlertBatcher:
    """
    Intelligent alert batching to maximize double mint detection accuracy
    """
    
    def __init__(self, health_monitor, enhanced_alert_manager):
        self.health_monitor = health_monitor
        self.alert_manager = enhanced_alert_manager
        self.pending_alerts = defaultdict(list)
        self.batch_timers = {}
        self.cst = pytz.timezone('America/Chicago')
        
    def get_batch_window(self) -> int:
    """Get appropriate batch window based on market conditions"""
    
    # FIXED: Properly get CST time
    cst = pytz.timezone('America/Chicago')
    now_cst = datetime.now(cst)
    current_time = now_cst.time()
    
    # Import time class explicitly to avoid conflicts
    from datetime import time as dt_time
    
    # Rush hour: 9:20-10:00 AM (peak circuit breaker activity)
    rush_start = dt_time(9, 20)
    rush_end = dt_time(10, 0)
    
    # Market hours: 9:30 AM - 4:00 PM
    market_start = dt_time(9, 30)
    market_end = dt_time(16, 0)
    
    # Pre-market starts at 8:00 AM
    premarket_start = dt_time(8, 0)
    
    # Debug logging to see what's happening
    logging.info(f"Current CST time: {now_cst.strftime('%H:%M:%S')}")
    logging.info(f"Time check - Rush: {rush_start} <= {current_time} <= {rush_end}")
    
    if rush_start <= current_time <= rush_end:
        logging.info("🔥 RUSH HOUR MODE activated")
        return 90  # 90 seconds during rush hour
    elif market_start <= current_time <= market_end:
        logging.info("📈 MARKET HOURS MODE activated") 
        return 45  # 45 seconds during normal market hours
    elif premarket_start <= current_time < rush_start:
        logging.info("🌅 PRE-MARKET MODE activated")
        return 30  # 30 seconds during pre-market
    else:
        logging.info("🌙 AFTER HOURS MODE activated")
        return 15  # 15 seconds after hours
    
def should_bypass_batching(self, new_breakers_df) -> bool:
    """Check if alert should bypass batching (emergency situations)"""
    if new_breakers_df.empty:
        return False
    
    # FIXED: Properly get CST time
    cst = pytz.timezone('America/Chicago')
    now_cst = datetime.now(cst)
    current_time = now_cst.time()
    
    # Import time class explicitly
    from datetime import time as dt_time
    
    # Define after hours correctly
    after_hours_start = dt_time(20, 0)  # 8:00 PM
    after_hours_end = dt_time(8, 0)     # 8:00 AM
    
    # Check if truly after hours (8 PM to 8 AM)
    if current_time >= after_hours_start or current_time < after_hours_end:
        vip_symbols = ['TSLA', 'NVDA', 'AAPL', 'MSTR', 'GME', 'AMC']
        has_vip = any(symbol in vip_symbols for symbol in new_breakers_df['Symbol'])
        if has_vip:
            logging.info("🚨 VIP symbol detected after hours - bypassing batch")
            return True
    
    return False
    
    def queue_alert(self, new_breakers_df, ended_breakers_df, full_df):
        """
        Queue alert for intelligent batching instead of sending immediately
        """
        # Check if we should bypass batching for critical alerts
        if self.should_bypass_batching(new_breakers_df):
            logging.info("🚨 Critical alert detected - bypassing batching")
            success = self.alert_manager.send_intelligent_alert(
                new_breakers_df=new_breakers_df,
                ended_breakers_df=ended_breakers_df,
                full_df=full_df,
                health_monitor=self.health_monitor
            )
            return success
        
        batch_window = self.get_batch_window()
        current_time = datetime.now()
        
        # Create batch key based on time window
        batch_key = int(current_time.timestamp() // batch_window) * batch_window
        
        # Add to pending alerts
        self.pending_alerts[batch_key].append({
            'new_breakers': new_breakers_df,
            'ended_breakers': ended_breakers_df,
            'full_df': full_df,
            'timestamp': current_time
        })
        
        # Set timer for this batch if not already set
        if batch_key not in self.batch_timers:
            timer = threading.Timer(
                batch_window, 
                self._process_batch, 
                args=[batch_key]
            )
            timer.start()
            self.batch_timers[batch_key] = timer
            
            logging.info(f"🕐 Batching alert for {batch_window}s to detect double mints")
    
    def _process_batch(self, batch_key):
        """Process a batch of alerts after the wait period"""
        if batch_key not in self.pending_alerts:
            return
        
        alerts_in_batch = self.pending_alerts[batch_key]
        del self.pending_alerts[batch_key]
        del self.batch_timers[batch_key]
        
        if not alerts_in_batch:
            return
        
        logging.info(f"🃏 Processing batch of {len(alerts_in_batch)} alerts")
        
        # Combine all alerts in the batch
        all_new_breakers = pd.concat([alert['new_breakers'] for alert in alerts_in_batch if not alert['new_breakers'].empty], ignore_index=True)
        all_ended_breakers = pd.concat([alert['ended_breakers'] for alert in alerts_in_batch if not alert['ended_breakers'].empty], ignore_index=True)
        
        # Use the most recent full_df
        latest_full_df = alerts_in_batch[-1]['full_df']
        
        # Remove duplicates
        if not all_new_breakers.empty:
            all_new_breakers = all_new_breakers.drop_duplicates(subset=['Symbol', 'Trigger Date', 'Trigger Time'])
        if not all_ended_breakers.empty:
            all_ended_breakers = all_ended_breakers.drop_duplicates(subset=['Symbol', 'Trigger Date', 'Trigger Time'])
        
        # Send the combined intelligent alert
        if not all_new_breakers.empty or not all_ended_breakers.empty:
            success = self.alert_manager.send_intelligent_alert(
                new_breakers_df=all_new_breakers,
                ended_breakers_df=all_ended_breakers,
                full_df=latest_full_df,
                health_monitor=self.health_monitor
            )
            
            if success:
                batch_size = len(all_new_breakers) + len(all_ended_breakers)
                logging.info(f"✅ Batched intelligent alert sent successfully ({batch_size} total alerts)")
            else:
                logging.error("❌ Failed to send batched intelligent alert")

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

# --- Log Capturing Setup ---
recent_logs = deque(maxlen=20)
class CaptureLogsHandler(logging.Handler):
    def emit(self, record):
        recent_logs.append(self.format(record))

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
capture_handler = CaptureLogsHandler()
capture_handler.setFormatter(log_formatter)
root_logger.addHandler(capture_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# --- Configuration ---
app = Flask(__name__)
VIP_SYMBOLS = ['TSLA', 'AAPL', 'GOOG', 'TSLZ', 'ETQ', 'NVDA', 'MSTR', 'GME', 'AMC']
template_manager = AlertTemplateManager(vip_symbols=VIP_SYMBOLS)
health_monitor = EnhancedHealthMonitor()  # Enhanced version

# --- Firestore Config Functions ---
def get_config_from_firestore(doc_id, field_id):
    try:
        db = firestore.Client()
        doc_ref = db.collection('app_config').document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            value = doc.to_dict().get(field_id)
            if value: 
                logging.info(f"Retrieved {field_id} from Firestore successfully")
                return value
        logging.error(f"Field '{field_id}' not found in Firestore document 'app_config/{doc_id}'")
        return None
    except Exception as e:
        logging.error(f"Failed to access config from Firestore: {e}")
        return None

# --- Alert Manager (backwards compatibility) ---
class AlertManager:
    def __init__(self, discord_client, template_manager):
        self.discord_client = discord_client
        self.template_manager = template_manager
    
    def send_formatted_alert(self, alert_data):
        return self.discord_client.send_alert(
            title=alert_data['title'],
            message=alert_data['message'],
            color=alert_data['color']
        )

# --- Enhanced Dashboard Template ---
ENHANCED_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Secret_Alerts Intelligence Dashboard</title>
    <style>
        body { background: #121212; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; padding: 2rem; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 2rem; }
        .header h1 { color: #00d9ff; }
        .card { background: #1e1e1e; padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; border: 1px solid #333; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        h2 { color: #00d9ff; border-bottom: 2px solid #00d9ff; padding-bottom: 10px; }
        .trust-header h2 { color: #4CAF50; border-bottom: 2px solid #4CAF50;}
        .intelligence-header h2 { color: #FFD700; border-bottom: 2px solid #FFD700;}
        .batching-header h2 { color: #FF6B35; border-bottom: 2px solid #FF6B35;}
        .log-box { height: 300px; overflow-y: auto; background: #0a0e27; padding: 1rem; border-radius: 8px; font-family: monospace; }
        .btn { background: #0099ff; color: #fff; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block; margin: 0.25rem; border: none; cursor: pointer; }
        .btn:hover { background: #0077cc; }
        .time-travel-btn { background: #9c27b0; }
        .time-travel-btn:hover { background: #7b1fa2; }
        .intelligence-btn { background: #FFD700; color: #000; }
        .intelligence-btn:hover { background: #FFC107; }
        .batching-btn { background: #FF6B35; }
        .batching-btn:hover { background: #E55A2B; }
        .form-group { margin-bottom: 1rem; }
        input[type="password"] { background: #0a0e27; border: 1px solid #00d9ff; color: #fff; padding: 0.5rem; border-radius: 4px; }
        .success { color: #28a745; }
        .warning { color: #fca311; }
        .error { color: #e63946; }
        
        /* Trust Dashboard Styles */
        .trust-container { display: grid; grid-template-columns: repeat(12, 1fr); gap: 20px; margin-top: 2rem; }
        .data-freshness { grid-column: 1 / 4; }
        .batching-status { grid-column: 4 / 7; }
        .transaction-log { grid-column: 7 / -1; }
        .intelligence-summary { grid-column: 1 / 7; }
        .alert-ledger { grid-column: 1 / -1; margin-top: 1.5rem; }
        .status-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 10px; align-items: center; }
        .status-grid strong { color: #aaa; }
        .status-value { font-family: 'Courier New', monospace; font-size: 1.1em; word-wrap: break-word; }
        .status-good { color: #66bb6a; }
        .status-bad { color: #ef5350; }
        .status-vip { color: #FFD700; }
        .status-batching { color: #FF6B35; }
        .log-table, .ledger-table { width: 100%; border-collapse: collapse; font-family: 'Courier New', monospace; }
        .log-table th, .log-table td, .ledger-table th, .ledger-table td { padding: 12px; text-align: left; border-bottom: 1px solid #333; }
        .log-table th, .ledger-table th { background-color: #2a2a2a; }
        .log-level-SUCCESS { color: #66bb6a; }
        .log-level-ERROR { color: #ef5350; }
        .log-level-WARN { color: #ffa726; }
        .log-level-INFO { color: #42a5f5; }
        .table-container { max-height: 400px; overflow-y: auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>🚀 Secret_Alerts Intelligence Dashboard</h1></div>
        
        <div class="card">
            <h2>System Controls</h2>
            <form action="/report-open-alerts" method="post" style="display: inline;">
                <div class="form-group">
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="btn">📊 Report All Open Alerts</button>
            </form>
            <a href="/time-travel" class="btn time-travel-btn">🕐 Time Travel Test</a>
            <a href="/test-intelligence" class="btn intelligence-btn">🧠 Test Intelligence</a>
            <a href="/test-batching" class="btn batching-btn">🃏 Test Batching</a>
        </div>

        <div class="trust-container">
            <div class="card data-freshness trust-header">
                <h2>🛡️ 1. Data Freshness</h2>
                <div id="freshness-content">Loading...</div>
            </div>

            <div class="card batching-status batching-header">
                <h2>🃏 2. Smart Batching</h2>
                <div id="batching-content">
                    <div class="status-grid">
                        <strong>Status:</strong><span class="status-value status-batching">Active</span>
                        <strong>Mode:</strong><span class="status-value" id="batch-mode">Loading...</span>
                        <strong>Window:</strong><span class="status-value" id="batch-window">Loading...</span>
                        <strong>Purpose:</strong><span class="status-value">Double Mint Detection</span>
                    </div>
                </div>
            </div>

            <div class="card transaction-log trust-header">
                <h2>🛡️ 3. Recent Activity Log</h2>
                <div class="table-container">
                    <table class="log-table">
                        <thead><tr><th>Time</th><th>Level</th><th>Message</th></tr></thead>
                        <tbody id="log-content"><tr><td colspan="3">Loading...</td></tr></tbody>
                    </table>
                </div>
            </div>

            <div class="card intelligence-summary intelligence-header">
                <h2>🧠 4. Intelligence Summary</h2>
                <div id="intelligence-content">Loading...</div>
            </div>

            <div class="card alert-ledger trust-header">
                <h2>🛡️ 5. Alert Ledger (Confirmed Sent)</h2>
                <div class="table-container">
                    <table class="ledger-table">
                        <thead><tr><th>Alert ID</th><th>Time</th><th>Type</th><th>Symbol</th><th>Priority</th><th>Freq</th><th>🃏</th><th>Details</th></tr></thead>
                        <tbody id="ledger-content"><tr><td colspan="8">Loading...</td></tr></tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Legacy Log Viewer</h2>
            <div class="log-box">{{ logs_html|safe }}</div>
        </div>
    </div>

    {% raw %}
    <script>
        function updateBatchingStatus() {
            const now = new Date();
            const cst = new Date(now.toLocaleString("en-US", {timeZone: "America/Chicago"}));
            const currentTime = cst.getHours() * 100 + cst.getMinutes();
            
            let mode, window_seconds;
            if (currentTime >= 920 && currentTime <= 1000) {
                mode = "RUSH HOUR";
                window_seconds = 90;
            } else if (currentTime >= 930 && currentTime <= 1600) {
                mode = "MARKET HOURS";
                window_seconds = 45;
            } else {
                mode = "AFTER HOURS";
                window_seconds = 15;
            }
            
            document.getElementById('batch-mode').textContent = mode;
            document.getElementById('batch-window').textContent = window_seconds + "s";
        }
        
        function updateDashboard() {
            fetch('/api/health')
                .then(response => response.json())
                .then(data => {
                    const freshnessDiv = document.getElementById('freshness-content');
                    const lastCheck = data.last_check;
                    const successClass = lastCheck.successful ? 'status-good' : 'status-bad';
                    const successText = lastCheck.successful ? 'Success' : 'Failed';
                    freshnessDiv.innerHTML = `
                        <div class="status-grid">
                            <strong>Last Check:</strong><span class="status-value">${lastCheck.timestamp || 'N/A'}</span>
                            <strong>Status:</strong><span class="status-value ${successClass}">${successText}</span>
                            <strong>File Hash:</strong><span class="status-value">${lastCheck.file_hash}</span>
                            <strong>Details:</strong><span class="status-value">${lastCheck.error_message || 'OK'}</span>
                        </div>
                    `;
                    
                    const logBody = document.getElementById('log-content');
                    logBody.innerHTML = '';
                    if (data.transactions.length === 0) { 
                        logBody.innerHTML = '<tr><td colspan="3">No transactions logged yet.</td></tr>'; 
                    } else { 
                        data.transactions.forEach(log => {
                            const row = logBody.insertRow();
                            row.innerHTML = `<td>${log.timestamp}</td><td class="log-level-${log.level}">${log.level}</td><td>${log.message}</td>`;
                        });
                    }
                    
                    const ledgerBody = document.getElementById('ledger-content');
                    ledgerBody.innerHTML = '';
                    if (data.alerts.length === 0) { 
                        ledgerBody.innerHTML = '<tr><td colspan="8">No alerts sent yet.</td></tr>'; 
                    } else { 
                        data.alerts.forEach(alert => {
                            const row = ledgerBody.insertRow();
                            const priorityEmoji = alert.priority === 'VIP' ? '💎' : alert.priority === 'HIGH' ? '🔥' : '🔵';
                            const doubleMintIcon = alert.double_mint ? '🃏' : '';
                            row.innerHTML = `<td>${alert.alert_id}</td><td>${alert.timestamp}</td><td>${alert.alert_type}</td><td>${alert.symbol}</td><td>${priorityEmoji}</td><td>${alert.frequency || 1}x</td><td>${doubleMintIcon}</td><td>${alert.details}</td>`;
                        });
                    }
                })
                .catch(error => console.error('Failed to update dashboard:', error));

            // Update intelligence summary
            fetch('/api/intelligence')
                .then(response => response.json())
                .then(intData => {
                    const intelDiv = document.getElementById('intelligence-content');
                    if (intData.stats && Object.keys(intData.stats).length > 0) {
                        intelDiv.innerHTML = `
                            <div class="status-grid">
                                <strong>Total Alerts:</strong><span class="status-value">${intData.stats.total_alerts}</span>
                                <strong>VIP Alerts:</strong><span class="status-value status-vip">💎 ${intData.stats.vip_alerts}</span>
                                <strong>Double Mint:</strong><span class="status-value">🃏 ${intData.stats.double_mint_alerts}</span>
                                <strong>High Frequency:</strong><span class="status-value">🔥 ${intData.stats.high_frequency_alerts}</span>
                                <strong>Avg Frequency:</strong><span class="status-value">${intData.stats.average_frequency}x</span>
                                <strong>Status:</strong><span class="status-value status-good">${intData.message}</span>
                            </div>
                        `;
                    } else {
                        intelDiv.innerHTML = '<p>Intelligence system initializing...</p>';
                    }
                })
                .catch(error => {
                    console.error('Failed to update intelligence:', error);
                    document.getElementById('intelligence-content').innerHTML = '<p>Intelligence data unavailable</p>';
                });
            
            // Update batching status
            updateBatchingStatus();
        }
        
        document.addEventListener('DOMContentLoaded', () => {
            updateDashboard();
            setInterval(updateDashboard, 15000);
        });
    </script>
    {% endraw %}
</body>
</html>
"""

# --- Flask Routes ---

@app.route('/')
def dashboard():
    log_html = ""
    for log in reversed(recent_logs):
        css_class = "error" if any(level in log for level in ["ERROR", "CRITICAL"]) else "warning" if "WARNING" in log else "success"
        log_html += f'<div class="{css_class}">{log}</div>'
    return render_template_string(ENHANCED_DASHBOARD_TEMPLATE, logs_html=log_html)

@app.route('/api/health')
def health_api():
    """Serves the latest health data as JSON."""
    return jsonify(health_monitor.get_health_snapshot())

@app.route('/api/intelligence')
def intelligence_api():
    """Serve intelligence statistics"""
    try:
        intelligence_summary = health_monitor.get_intelligence_summary()
        return jsonify(intelligence_summary)
    except Exception as e:
        logging.error(f"Error getting intelligence stats: {e}")
        return jsonify({"error": "Failed to get intelligence stats"}), 500

@app.route('/test-intelligence')
def test_intelligence():
    """Test the intelligence system"""
    try:
        monitor = ShortSaleMonitor()
        full_df = monitor.fetch_data()
        
        if full_df is None or full_df.empty:
            return "No data available for intelligence testing", 400
        
        # Test with a sample symbol
        from alerts.alert_intelligence import quick_analyze
        
        # Get a sample symbol from the data
        sample_symbol = full_df.iloc[0]['Symbol']
        sample_date = full_df.iloc[0]['Trigger Date']
        
        result = quick_analyze(sample_symbol, sample_date, full_df, VIP_SYMBOLS)
        
        return f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f5f5;">
        <h2>🧠 Intelligence Test Results</h2>
        <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h3>Test Symbol: {sample_symbol}</h3>
            <pre style="background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto;">{json.dumps(result, indent=2)}</pre>
        </div>
        <p style="text-align: center; margin-top: 20px;">
            <a href="/" style="color: #2196F3; text-decoration: none; font-size: 16px;">← Back to Dashboard</a>
        </p>
        </body></html>
        """
        
    except Exception as e:
        return f"Intelligence test failed: {str(e)}", 500

@app.route('/test-batching')
def test_batching():
    """Test the smart batching system with correct timezone"""
    try:
        # FIXED: Proper CST timezone handling
        cst = pytz.timezone('America/Chicago')
        now_cst = datetime.now(cst)
        current_time = now_cst.time()
        
        # Import time class explicitly
        from datetime import time as dt_time
        
        rush_start = dt_time(9, 20)
        rush_end = dt_time(10, 0)
        market_start = dt_time(9, 30)
        market_end = dt_time(16, 0)
        premarket_start = dt_time(8, 0)
        after_hours_start = dt_time(20, 0)  # 8 PM
        
        # Determine correct mode
        if rush_start <= current_time <= rush_end:
            mode = "RUSH HOUR"
            batch_window = 90
            description = "Peak circuit breaker activity - maximum batching window"
        elif market_start <= current_time <= market_end:
            mode = "MARKET HOURS"
            batch_window = 45
            description = "Normal trading hours - balanced batching"
        elif premarket_start <= current_time < rush_start:
            mode = "PRE-MARKET"
            batch_window = 30
            description = "Pre-market preparation - moderate batching"
        else:
            mode = "AFTER HOURS"
            batch_window = 15
            description = "Minimal batching window - immediate VIP alerts"
        
        return f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f5f5;">
        <h2>🃏 Smart Batching System Test (TIMEZONE FIXED)</h2>
        <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;">
            <h3>✅ Configuration Test Successful</h3>
            <div style="background: #d4edda; padding: 15px; border-radius: 4px; border: 1px solid #c3e6cb;">
                <p><strong>Current Time (CST):</strong> {now_cst.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Raw Time:</strong> {current_time.strftime('%H:%M:%S')}</p>
                <p><strong>Market Mode:</strong> {mode}</p>
                <p><strong>Batch Window:</strong> {batch_window} seconds</p>
                <p><strong>Description:</strong> {description}</p>
                <p><strong>Status:</strong> Timezone corrected! ✅</p>
            </div>
        </div>
        
        <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px;">
            <h3>Corrected Schedule (CST)</h3>
            <div style="background: #e8f5e8; padding: 15px; border-radius: 4px;">
                <p><strong>🌙 After Hours (8:00 PM - 8:00 AM):</strong> 15 seconds</p>
                <p><strong>🌅 Pre-Market (8:00 AM - 9:20 AM):</strong> 30 seconds</p>
                <p><strong>🔥 Rush Hour (9:20 AM - 10:00 AM):</strong> 90 seconds</p>
                <p><strong>📈 Market Hours (9:30 AM - 4:00 PM):</strong> 45 seconds</p>
            </div>
        </div>
        
        <div style="background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h3>Debug Info</h3>
            <div style="background: #f8f9fa; padding: 15px; border-radius: 4px; font-family: monospace;">
                <p>Rush Start: {rush_start}</p>
                <p>Current Time: {current_time}</p>
                <p>Rush End: {rush_end}</p>
                <p>In Rush Hour: {rush_start <= current_time <= rush_end}</p>
                <p>In Pre-Market: {premarket_start <= current_time < rush_start}</p>
            </div>
        </div>
        
        <p style="text-align: center; margin-top: 20px;">
            <a href="/" style="color: #2196F3; text-decoration: none; font-size: 16px;">← Back to Dashboard</a>
        </p>
        </body></html>
        """
        
    except Exception as e:
        return f"Test failed: {str(e)}", 500

@app.route('/run-check', methods=['POST'])
def run_check_endpoint():
    logging.info("Check triggered by Cloud Scheduler for short sale breakers.")
    monitor = ShortSaleMonitor()
    try:
        # This is the main check. We assume the monitor handles its own data fetching.
        new_breakers_df, ended_breakers_df = monitor.check_for_new_and_ended_breakers()
        
        # If the check is successful, we record it.
        health_monitor.record_check_attempt(success=True)
        
        webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
        if not webhook_url: 
            raise ValueError("Webhook URL not found in Firestore")
        
        discord_client = DiscordClient(webhook_url=webhook_url)
        # Use Enhanced Alert Manager with intelligence
        alert_manager = EnhancedAlertManager(discord_client, template_manager, VIP_SYMBOLS)
        
        log_msg = f"Analysis complete. Found {len(new_breakers_df)} new, {len(ended_breakers_df)} ended."
        health_monitor.log_transaction(log_msg, "INFO")
        logging.info(log_msg)

        if not new_breakers_df.empty or not ended_breakers_df.empty:
            # Get the full dataset for intelligence analysis
            try:
                full_df = monitor.fetch_data()
                if full_df is not None:
                    full_df = monitor.process_data(full_df)
            except Exception as e:
                logging.warning(f"Could not get full dataset for intelligence: {e}")
                full_df = None
            
            # Initialize smart batcher if not already done
            if not hasattr(app, 'smart_batcher'):
                app.smart_batcher = SmartAlertBatcher(health_monitor, alert_manager)
            
            # Use smart batching for better double mint detection
            logging.info("Queueing alert for intelligent batching...")
            app.smart_batcher.queue_alert(
                new_breakers_df=new_breakers_df,
                ended_breakers_df=ended_breakers_df,
                full_df=full_df
            )
        else:
            logging.info("Check finished. No new or ended circuit breakers found.")
            
        return "Check completed successfully.", 200
    
    except KeyError as e:
        # This is the specific fix for the 'UniqueKey' error
        error_msg = f"Data structure error: A required column is missing. Details: {e}"
        logging.error(error_msg, exc_info=True)
        health_monitor.record_check_attempt(success=False, error=error_msg)
        return "An error occurred during the check due to a data structure issue.", 500
        
    except Exception as e:
        error_msg = f"An error occurred during the scheduled check: {e}"
        logging.error(error_msg, exc_info=True)
        health_monitor.record_check_attempt(success=False, error=str(e))
        return "An error occurred during the check.", 500

# --- Other Endpoints (Time Travel, Reports, etc.) ---
@app.route('/time-travel')
def time_travel_page():
    """Serve the time travel testing interface"""
    try:
        suggestions = get_test_suggestions(VIP_SYMBOLS)
    except Exception as e:
        logging.error(f"Error getting test suggestions: {e}")
        suggestions = []
    
    suggestions_html = ""
    if suggestions:
        for suggestion in suggestions:
            vip_badge = "⭐ VIP" if suggestion.get('is_vip') else ""
            suggestions_html += f"""
            <div class="suggestion-item" onclick="fillTestTime('{suggestion['test_time']}')">
                <strong>{suggestion['symbol']} {vip_badge}</strong><br>
                <small>{suggestion['description']}</small><br>
                <code>{suggestion['test_time']}</code>
            </div>
            """
    else:
        suggestions_html = '<p style="color: #666;">Loading suggestions...</p>'
    
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Time Travel Alert Testing</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
            .container { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
            .section { background: white; padding: 20px; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .suggestion-item { 
                background: #f9f9f9; margin: 10px 0; padding: 15px; border-radius: 6px; 
                border: 1px solid #ccc; cursor: pointer; transition: all 0.2s;
            }
            .suggestion-item:hover { background: #e8f4f8; border-color: #2196F3; }
            .form-group { margin: 15px 0; }
            .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
            .form-group input { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }
            .btn { 
                background: #2196F3; color: white; padding: 12px 24px; border: none; 
                border-radius: 6px; cursor: pointer; font-size: 16px; 
            }
            .btn:hover { background: #1976D2; }
            .header { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; 
            }
            .info { background: #e3f2fd; padding: 15px; border-radius: 6px; margin-bottom: 20px; }
            .back-link { text-align: center; margin-top: 30px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🕐 Time Travel Alert Testing</h1>
            <p>Test your alert detection by simulating historical state changes</p>
        </div>
        
        <div class="info">
            <strong>How it works:</strong> Select a time when an alert was triggered. The system will simulate 
            what the data looked like before that time, then show what alerts would have been generated.
        </div>
        
        <div class="container">
            <div class="section">
                <h2>🎯 Manual Time Test</h2>
                <form method="post" action="/time-travel-test">
                    <div class="form-group">
                        <label for="test_time">Test Time (YYYY-MM-DD HH:MM:SS):</label>
                        <input type="text" id="test_time" name="test_time" 
                               placeholder="2025-08-12 13:13:00" required>
                    </div>
                    <button type="submit" class="btn">🚀 Run Time Travel Test</button>
                </form>
                
                <p><strong>Perfect Test for ETQ Alert:</strong></p>
                <ul>
                    <li><code>2025-08-12 13:13:00</code> - Test the ETQ alert that just triggered!</li>
                </ul>
            </div>
            
            <div class="section">
                <h2>💡 Suggested Test Times</h2>
                <p>Based on recent CBOE data:</p>
                <div id="suggestions">
                    {{ suggestions_html|safe }}
                </div>
            </div>
        </div>
        
        <div class="back-link">
            <a href="/" style="color: #2196F3; text-decoration: none; font-size: 16px;">← Back to Dashboard</a>
        </div>
        
        <script>
            function fillTestTime(timeStr) {
                document.getElementById('test_time').value = timeStr;
            }
        </script>
    </body>
    </html>
    """, suggestions_html=suggestions_html)

@app.route('/time-travel-test', methods=['POST'])
def time_travel_test():
    """Handle time travel test requests"""
    try:
        test_time = request.form.get('test_time')
        
        if not test_time:
            return "No test time provided", 400
        
        # Run the test
        results = run_time_travel_test(test_time, VIP_SYMBOLS)
        
        if 'error' in results:
            return f"""
            <html><body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
            <h1 style="color: #f44336;">⏰ Time Travel Test Failed</h1>
            <p>Error: {results['error']}</p>
            <p><a href="/time-travel" style="color: #2196F3;">← Back to Time Travel Testing</a></p>
            </body></html>
            """
        
        # Format the results (abbreviated for space)
        new_alerts_html = ""
        for alert in results['detected_changes']['new_alert_details']:
            vip_badge = "⭐ VIP" if alert['is_vip'] else ""
            new_alerts_html += f"<li>{vip_badge} <strong>{alert['symbol']}</strong> - {alert['security_name']} (Triggered {alert['trigger_time']})</li>"
        
        discord_preview_html = ""
        if results.get('discord_preview'):
            discord_preview_html = f"""
            <div style="background: #36393f; color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #7289da; margin-top: 0;">📱 Discord Alert Preview</h3>
                <div style="border-left: 4px solid #ffa500; padding-left: 15px; background: #2f3136; border-radius: 4px; padding: 15px;">
                    <strong>{results['discord_preview']['title']}</strong><br><br>
                    <pre style="white-space: pre-wrap; margin: 0; font-family: Arial;">{results['discord_preview']['message']}</pre>
                </div>
            </div>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Time Travel Test Results</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
            <h1>🕐 Time Travel Test Results</h1>
            <div style="background: #e8f5e8; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center;">
                <h2>Simulation for {results['simulation_time']}</h2>
                <p><strong>Changes Detected:</strong> 
                    <span style="color: #28a745; font-weight: bold;">{results['detected_changes']['new_alerts']} New</span>, 
                    <span style="color: #17a2b8; font-weight: bold;">{results['detected_changes']['ended_alerts']} Ended</span>
                </p>
            </div>
            
            {discord_preview_html}
            
            <div style="background: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3>🔍 Detected Changes</h3>
                <h4>🆕 New Alerts ({results['detected_changes']['new_alerts']}):</h4>
                <ul>{new_alerts_html if new_alerts_html else '<li>No new alerts detected</li>'}</ul>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="/time-travel" style="color: #2196F3; text-decoration: none; margin-right: 20px; font-size: 16px;">🔄 Run Another Test</a>
                <a href="/" style="color: #2196F3; text-decoration: none; font-size: 16px;">← Back to Dashboard</a>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        logging.error(f"Time travel test error: {e}")
        return f"Test failed: {str(e)}", 500

@app.route('/report-open-alerts', methods=['POST'])
def report_open_alerts():
    logging.info("Open alerts report triggered by user.")
    
    submitted_password = request.form.get('password')
    correct_password = get_config_from_firestore('security', 'dashboard_password')
    
    if not correct_password or submitted_password != correct_password:
        logging.warning("Failed login attempt for open alerts report.")
        return "Invalid password.", 403

    try:
        webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
        if not webhook_url: 
            return "Webhook URL not configured in Firestore.", 500

        discord_client = DiscordClient(webhook_url=webhook_url)
        # Use enhanced alert manager for reports too
        alert_manager = EnhancedAlertManager(discord_client, template_manager, VIP_SYMBOLS)
        monitor = ShortSaleMonitor()
        
        current_df = monitor.fetch_data()
        if current_df is None or current_df.empty:
            error_alert = {
                'title': "Open Alerts Report",
                'message': "Could not retrieve current circuit breaker data.",
                'color': 0xfca311
            }
            alert_manager.send_formatted_alert(error_alert)
            return redirect(url_for('dashboard'))

        open_alerts = current_df[pd.isnull(current_df['End Time'])]
        
        formatter = template_manager.get_formatter('short_sale')
        alert_data = formatter.format_open_alerts_report(open_alerts)
        alert_manager.send_formatted_alert(alert_data)
        
        logging.info(f"Open alerts report sent: {len(open_alerts)} open breakers")
            
    except Exception as e:
        logging.error(f"Failed to generate open alerts report: {e}", exc_info=True)
    
    return redirect(url_for('dashboard'))

@app.route('/report-morning-summary', methods=['POST'])
def report_morning_summary():
    return _send_scheduled_report('morning')

@app.route('/report-premarket-summary', methods=['POST'])
def report_premarket_summary():
    return _send_scheduled_report('market_check')

@app.route('/report-night-summary', methods=['POST'])
def report_night_summary():
    return _send_scheduled_report('welcome')

def _send_scheduled_report(report_type):
    """Helper function for scheduled reports"""
    logging.info(f"Scheduled {report_type} report triggered.")
    try:
        webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
        if not webhook_url:
            return "Webhook URL not configured in Firestore.", 500

        discord_client = DiscordClient(webhook_url=webhook_url)
        # Use enhanced alert manager for scheduled reports
        alert_manager = EnhancedAlertManager(discord_client, template_manager, VIP_SYMBOLS)
        monitor = ShortSaleMonitor()
        
        current_df = monitor.fetch_data()
        open_alerts = current_df[pd.isnull(current_df['End Time'])] if current_df is not None else pd.DataFrame()
        
        cst = pytz.timezone('America/Chicago')
        today_str = datetime.now(cst).strftime('%Y-%m-%d')
        
        total_today = 0
        ended_today = 0
        if current_df is not None:
            total_today = len(current_df[current_df['Trigger Date'] == today_str])
            ended_today = len(current_df[
                (current_df['Trigger Date'] == today_str) & 
                pd.notnull(current_df['End Time'])
            ])
        
        formatter = template_manager.get_formatter('short_sale')
        alert_data = formatter.format_scheduled_report(
            report_type=report_type,
            open_alerts_df=open_alerts,
            total_today=total_today,
            ended_today=ended_today
        )
        
        success = alert_manager.send_formatted_alert(alert_data)
        
        if success:
            logging.info(f"{report_type} report sent successfully")
            return f"{report_type} report sent successfully.", 200
        else:
            logging.error(f"Failed to send {report_type} report")
            return f"Failed to send {report_type} report.", 500
            
    except Exception as e:
        logging.error(f"Error generating {report_type} report: {e}", exc_info=True)
        return f"Error occurred while generating {report_type} report.", 500

# --- Application Startup ---
if __name__ == '__main__':
    # Log that we're starting with intelligence and batching
    logging.info("🧠 Starting Secret_Alerts with Enhanced Intelligence System")
    logging.info(f"💎 VIP Symbols: {', '.join(VIP_SYMBOLS)}")
    logging.info("🃏 Double Mint Detection: Active")
    logging.info("📊 Frequency Analysis: Active")
    logging.info("🎯 Priority Classification: Active")
    logging.info("⏰ Smart Alert Batching: Active")
    logging.info("🔥 Market-aware batching windows enabled")
    logging.info("🛠️ FIXED: Time module conflict resolved")
    
    # FIXED: Use time_module.sleep instead of time.sleep to avoid conflicts
    time_module.sleep(1)  # Test the fix
    logging.info("✅ Time module fix confirmed working")
    
    # The Trust Dashboard is now part of the Flask app and doesn't need a separate server.
    # The main app will handle all routes.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
        