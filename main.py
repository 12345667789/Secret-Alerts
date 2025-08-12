import os
import logging
import pandas as pd
from collections import deque
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from google.cloud import firestore
from datetime import datetime
import pytz
import hashlib
import threading

# Import our modular components
from alerts.discord_client import DiscordClient
from alerts.templates import AlertTemplateManager
from monitors.cboe_monitor import ShortSaleMonitor
from testing.time_travel_tester import run_time_travel_test, get_test_suggestions

# --- Health Monitor Class ---
class HealthMonitor:
    """
    A thread-safe class to track the health and activity of the monitoring system.
    """
    def __init__(self, max_log_size=100, max_ledger_size=200):
        self.lock = threading.Lock()
        self.cst = pytz.timezone('America/Chicago')
        self.last_check_status = {"timestamp": None, "successful": False, "file_hash": "N/A", "error_message": "No checks run yet."}
        self.transaction_log = deque(maxlen=max_log_size)
        self.alert_ledger = deque(maxlen=max_ledger_size)
        self.log_transaction("System Initialized", "INFO")

    def _get_current_time_str(self):
        return datetime.now(self.cst).strftime('%Y-%m-%d %H:%M:%S CST')

    def record_check_attempt(self, success: bool, file_hash: str = "N/A", error: str = None):
        with self.lock:
            self.last_check_status = {"timestamp": self._get_current_time_str(), "successful": success, "file_hash": file_hash if success else "FAILED", "error_message": error}
        if success:
            self.log_transaction(f"Data fetch and analysis successful.", "SUCCESS")
        else:
            self.log_transaction(f"Data fetch FAILED. Reason: {error}", "ERROR")

    def log_transaction(self, message: str, level: str = "INFO"):
        with self.lock:
            self.transaction_log.appendleft({"timestamp": self._get_current_time_str(), "message": message, "level": level})

    def record_alert_sent(self, alert_id: str, alert_type: str, symbol: str, details: str):
        """Records a sent alert with a unique, persistent ID."""
        with self.lock:
            self.alert_ledger.appendleft({
                "alert_id": alert_id,
                "timestamp": self._get_current_time_str(),
                "alert_type": alert_type,
                "symbol": symbol,
                "details": details
            })
        self.log_transaction(f"Alert Sent (ID: {alert_id}) for {symbol}", "SUCCESS")

    def get_health_snapshot(self):
        with self.lock:
            return {"last_check": self.last_check_status.copy(), "transactions": list(self.transaction_log), "alerts": list(self.alert_ledger)}

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
VIP_SYMBOLS = ['TSLA', 'AAPL', 'GOOG', 'TSLZ', 'ETQ']
template_manager = AlertTemplateManager(vip_symbols=VIP_SYMBOLS)
health_monitor = HealthMonitor() # Create a single, shared instance

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

# --- Alert Manager ---
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

# --- Unified Dashboard Template ---
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Secret_Alerts Unified Dashboard</title>
    <style>
        body { background: #121212; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; padding: 2rem; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 2rem; }
        .header h1 { color: #00d9ff; }
        .card { background: #1e1e1e; padding: 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; border: 1px solid #333; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        h2 { color: #00d9ff; border-bottom: 2px solid #00d9ff; padding-bottom: 10px; }
        .trust-header h2 { color: #4CAF50; border-bottom: 2px solid #4CAF50;}
        .log-box { height: 300px; overflow-y: auto; background: #0a0e27; padding: 1rem; border-radius: 8px; font-family: monospace; }
        .btn { background: #0099ff; color: #fff; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block; margin: 0.25rem; border: none; cursor: pointer; }
        .btn:hover { background: #0077cc; }
        .time-travel-btn { background: #9c27b0; }
        .time-travel-btn:hover { background: #7b1fa2; }
        .form-group { margin-bottom: 1rem; }
        input[type="password"] { background: #0a0e27; border: 1px solid #00d9ff; color: #fff; padding: 0.5rem; border-radius: 4px; }
        .success { color: #28a745; }
        .warning { color: #fca311; }
        .error { color: #e63946; }
        
        /* Trust Dashboard Styles */
        .trust-container { display: grid; grid-template-columns: repeat(12, 1fr); gap: 20px; margin-top: 2rem; }
        .data-freshness { grid-column: 1 / 5; }
        .transaction-log { grid-column: 5 / -1; }
        .alert-ledger { grid-column: 1 / -1; margin-top: 1.5rem; }
        .status-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 10px; align-items: center; }
        .status-grid strong { color: #aaa; }
        .status-value { font-family: 'Courier New', monospace; font-size: 1.1em; word-wrap: break-word; }
        .status-good { color: #66bb6a; }
        .status-bad { color: #ef5350; }
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
        <div class="header"><h1>🚀 Secret_Alerts Unified Dashboard</h1></div>
        
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
        </div>

        <div class="trust-container">
            <div class="card data-freshness trust-header">
                <h2>🛡️ 1. Data Freshness</h2>
                <div id="freshness-content">Loading...</div>
            </div>

            <div class="card transaction-log trust-header">
                <h2>🛡️ 2. Recent Activity Log</h2>
                <div class="table-container">
                    <table class="log-table">
                        <thead><tr><th>Time</th><th>Level</th><th>Message</th></tr></thead>
                        <tbody id="log-content"><tr><td colspan="3">Loading...</td></tr></tbody>
                    </table>
                </div>
            </div>

            <div class="card alert-ledger trust-header">
                <h2>🛡️ 3. Alert Ledger (Confirmed Sent)</h2>
                <div class="table-container">
                    <table class="ledger-table">
                        <thead><tr><th>Alert ID</th><th>Time</th><th>Type</th><th>Symbol</th><th>Details</th></tr></thead>
                        <tbody id="ledger-content"><tr><td colspan="5">Loading...</td></tr></tbody>
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
                    if (data.transactions.length === 0) { logBody.innerHTML = '<tr><td colspan="3">No transactions logged yet.</td></tr>'; }
                    else { data.transactions.forEach(log => {
                        const row = logBody.insertRow();
                        row.innerHTML = `<td>${log.timestamp}</td><td class="log-level-${log.level}">${log.level}</td><td>${log.message}</td>`;
                    });}
                    const ledgerBody = document.getElementById('ledger-content');
                    ledgerBody.innerHTML = '';
                    if (data.alerts.length === 0) { ledgerBody.innerHTML = '<tr><td colspan="5">No alerts sent yet.</td></tr>'; }
                    else { data.alerts.forEach(alert => {
                        const row = ledgerBody.insertRow();
                        row.innerHTML = `<td>${alert.alert_id}</td><td>${alert.timestamp}</td><td>${alert.alert_type}</td><td>${alert.symbol}</td><td>${alert.details}</td>`;
                    });}
                })
                .catch(error => console.error('Failed to update dashboard:', error));
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
    return render_template_string(DASHBOARD_TEMPLATE, logs_html=log_html)

@app.route('/api/health')
def health_api():
    """Serves the latest health data as JSON."""
    return jsonify(health_monitor.get_health_snapshot())

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
        alert_manager = AlertManager(discord_client, template_manager)
        
        log_msg = f"Analysis complete. Found {len(new_breakers_df)} new, {len(ended_breakers_df)} ended."
        health_monitor.log_transaction(log_msg, "INFO")
        logging.info(log_msg)

        if not new_breakers_df.empty or not ended_breakers_df.empty:
            formatter = template_manager.get_formatter('short_sale')
            alert_data = formatter.format_changes_alert(new_breakers_df, ended_breakers_df)
            
            logging.info("Sending Discord alert...")
            success = alert_manager.send_formatted_alert(alert_data)
            
            if success:
                logging.info("Alert sent successfully")
                for _, row in new_breakers_df.iterrows():
                    # Generate persistent ID
                    alert_id = f"{row['Symbol']}-{row['Trigger Date']}-{row['Trigger Time']}".replace(' ', '_').replace(':', '')
                    health_monitor.record_alert_sent(
                        alert_id=alert_id,
                        alert_type="NEW_BREAKER", 
                        symbol=row['Symbol'], 
                        details=f"Trigger: {row['Trigger Time']}"
                    )
                for _, row in ended_breakers_df.iterrows():
                    # Generate persistent ID
                    alert_id = f"{row['Symbol']}-{row['Trigger Date']}-{row['Trigger Time']}".replace(' ', '_').replace(':', '')
                    health_monitor.record_alert_sent(
                        alert_id=alert_id,
                        alert_type="ENDED_BREAKER", 
                        symbol=row['Symbol'], 
                        details=f"Ended: {row['End Time']}"
                    )
            else:
                logging.error("Failed to send alert")
                health_monitor.log_transaction("Discord alert failed to send.", "ERROR")
        else:
            logging.info("Check finished. No new or ended circuit breakers found.")
            
        return "Check completed successfully.", 200
        
    except Exception as e:
        error_msg = f"An error occurred during the scheduled check: {e}"
        logging.error(error_msg, exc_info=True)
        health_monitor.record_check_attempt(success=False, error=str(e))
        return "An error occurred during the check.", 500

# --- Other Endpoints (Unchanged) ---
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
            <h1 style="color: #f44336;">❌ Time Travel Test Failed</h1>
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
        alert_manager = AlertManager(discord_client, template_manager)
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
        alert_manager = AlertManager(discord_client, template_manager)
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
    # The Trust Dashboard is now part of the Flask app and doesn't need a separate server.
    # The main app will handle all routes.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
