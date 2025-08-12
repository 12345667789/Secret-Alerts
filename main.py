import os
import logging
import pandas as pd
from collections import deque
from flask import Flask, render_template_string, request, redirect, url_for
from google.cloud import firestore
from datetime import datetime
import pytz

# Import our modular components
from alerts.discord_client import DiscordClient
from alerts.templates import AlertTemplateManager
from monitors.cboe_monitor import ShortSaleMonitor

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
VIP_SYMBOLS = ['TSLA', 'AAPL', 'GOOG', 'TSLZ']

# Initialize template manager
template_manager = AlertTemplateManager(vip_symbols=VIP_SYMBOLS)

# --- Firestore Config Functions ---
def get_config_from_firestore(doc_id, field_id):
    """Fetches a specific config value from Firestore."""
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
        """Send a pre-formatted alert"""
        return self.discord_client.send_alert(
            title=alert_data['title'],
            message=alert_data['message'],
            color=alert_data['color']
        )

# --- Web Dashboard Template ---
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Secret_Alerts Dashboard</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body { background: #1a1a2e; color: #e0e0e0; font-family: monospace; margin: 0; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 2rem; }
        .card { background: #16213e; padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #00d9ff; }
        h1, h2 { color: #00d9ff; }
        .log-box { height: 400px; overflow-y: auto; background: #0a0e27; padding: 1rem; border-radius: 8px; }
        .btn { background: #0099ff; color: #fff; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block; margin: 0.25rem; border: none; cursor: pointer; }
        .btn:hover { background: #0077cc; }
        .time-travel-btn { background: #9c27b0; }
        .time-travel-btn:hover { background: #7b1fa2; }
        .form-group { margin-bottom: 1rem; }
        input[type="password"] { background: #0a0e27; border: 1px solid #00d9ff; color: #fff; padding: 0.5rem; border-radius: 4px; }
        .success { color: #28a745; }
        .warning { color: #fca311; }
        .error { color: #e63946; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>🚀 Secret_Alerts Dashboard</h1></div>
        <div class="card">
            <h2>System Controls</h2>
            <form action="/report-open-alerts" method="post">
                <div class="form-group">
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="btn">📊 Report All Open Alerts</button>
            </form>
            <a href="/test-alert" class="btn">🧪 Test Alert System</a>
            <a href="/time-travel" class="btn time-travel-btn">🕐 Time Travel Test</a>
        </div>
        <div class="card">
            <h2>Recent Activity (Live)</h2>
            <div class="log-box">{{ logs_html|safe }}</div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    log_html = ""
    for log in reversed(recent_logs):
        css_class = "error" if any(level in log for level in ["ERROR", "CRITICAL"]) else \
                   "warning" if "WARNING" in log else "success"
        log_html += f'<div class="{css_class}">{log}</div>'
    return render_template_string(DASHBOARD_TEMPLATE, logs_html=log_html)

# --- NEW: Time Travel Testing Routes ---
@app.route('/time-travel')
def time_travel_page():
    """Serve the time travel testing interface"""
    try:
        from testing.time_travel_tester import get_test_suggestions
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
        
        # Import the time travel tester
        from testing.time_travel_tester import run_time_travel_test
        
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
        before_alerts_html = ""
        for alert in results['before_state']['sample_alerts']:
            vip_badge = "⭐" if alert['is_vip'] else ""
            before_alerts_html += f"<li>{vip_badge} <strong>{alert['symbol']}</strong> - {alert['security_name']} (Started {alert['trigger_time']})</li>"
        
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

# --- Main Check Endpoint (UNCHANGED) ---
@app.route('/run-check', methods=['POST'])
def run_check_endpoint():
    logging.info("Check triggered by Cloud Scheduler for short sale breakers.")
    try:
        # Get webhook URL
        webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
        if not webhook_url: 
            logging.error("Webhook URL not found in Firestore")
            return "Webhook URL not configured in Firestore.", 500
        
        # Initialize components
        discord_client = DiscordClient(webhook_url=webhook_url)
        alert_manager = AlertManager(discord_client, template_manager)
        monitor = ShortSaleMonitor()
        
        # Check for changes
        logging.info("Checking for new and ended breakers...")
        new_breakers_df, ended_breakers_df = monitor.check_for_new_and_ended_breakers()
        
        logging.info(f"Found {len(new_breakers_df)} new breakers and {len(ended_breakers_df)} ended breakers")

        # Send alert if there are changes
        if not new_breakers_df.empty or not ended_breakers_df.empty:
            formatter = template_manager.get_formatter('short_sale')
            alert_data = formatter.format_changes_alert(new_breakers_df, ended_breakers_df)
            
            logging.info("Sending Discord alert...")
            success = alert_manager.send_formatted_alert(alert_data)
            
            if success:
                logging.info("Alert sent successfully")
            else:
                logging.error("Failed to send alert")
        else:
            logging.info("Check finished. No new or ended circuit breakers found.")
            
        return "Check completed successfully.", 200
        
    except Exception as e:
        logging.error(f"An error occurred during the scheduled check: {e}", exc_info=True)
        return "An error occurred during the check.", 500

# --- Manual Report Endpoint (UNCHANGED) ---
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
        
        # Get current data
        current_df = monitor.fetch_data()
        if current_df is None or current_df.empty:
            error_alert = {
                'title': "Open Alerts Report",
                'message': "Could not retrieve current circuit breaker data.",
                'color': 0xfca311
            }
            alert_manager.send_formatted_alert(error_alert)
            return redirect(url_for('dashboard'))

        # Filter for open alerts
        open_alerts = current_df[pd.isnull(current_df['End Time'])]
        
        # Format and send report
        formatter = template_manager.get_formatter('short_sale')
        alert_data = formatter.format_open_alerts_report(open_alerts)
        alert_manager.send_formatted_alert(alert_data)
        
        logging.info(f"Open alerts report sent: {len(open_alerts)} open breakers")
            
    except Exception as e:
        logging.error(f"Failed to generate open alerts report: {e}", exc_info=True)
    
    return redirect(url_for('dashboard'))

# --- Scheduled Report Endpoints (UNCHANGED) ---
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
        
        # Get current data
        current_df = monitor.fetch_data()
        open_alerts = current_df[pd.isnull(current_df['End Time'])] if current_df is not None else pd.DataFrame()
        
        # Get today's stats
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
        
        # Format and send report
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

# --- Test Endpoint (UNCHANGED) ---
@app.route('/test-alert')
def test_alert():
    """Test the alert system"""
    try:
        webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
        if not webhook_url:
            return "Webhook URL not configured", 500
        
        discord_client = DiscordClient(webhook_url=webhook_url)
        success = discord_client.send_alert(
            title="🧪 Test Alert",
            message="Alert system is working correctly!",
            color=0x00FF00
        )
        
        if success:
            logging.info("Test alert sent successfully")
            return "Test alert sent successfully!"
        else:
            return "Test alert failed!"
            
    except Exception as e:
        logging.error(f"Test alert error: {e}")
        return f"Test alert error: {e}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)