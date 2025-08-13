import os
import logging
import pandas as pd
import json
import threading
from collections import deque
from flask import Flask, render_template, request, redirect, url_for, jsonify
from google.cloud import firestore
from datetime import datetime
import pytz

# --- Import our refactored components ---
from alerts.discord_client import DiscordClient
from alerts.templates import AlertTemplateManager
from alerts.enhanced_alert_manager import EnhancedAlertManager
from monitors.cboe_monitor import ShortSaleMonitor
from config.settings import get_config, get_config_from_firestore
from services.health_monitor import EnhancedHealthMonitor
from services.alert_batcher import SmartAlertBatcher

# Add this line with your other custom imports
from alerts.alert_intelligence import quick_analyze

# Add this with your other custom imports
from testing.time_travel_tester import run_time_travel_test

# --- Global Application Setup ---
app = Flask(__name__)
config = get_config()

# Logging setup moved here to ensure it runs under Gunicorn
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if root_logger.hasHandlers():
    root_logger.handlers.clear()

# This handler captures logs for the dashboard viewer
recent_logs = deque(maxlen=20)
class CaptureLogsHandler(logging.Handler):
    def emit(self, record):
        recent_logs.append(self.format(record))

capture_handler = CaptureLogsHandler()
capture_handler.setFormatter(log_formatter)
root_logger.addHandler(capture_handler)

# This handler prints logs to the standard console (visible in Cloud Logging)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# Initialize global objects
health_monitor = EnhancedHealthMonitor()
template_manager = AlertTemplateManager(vip_symbols=config.vip_tickers)

# --- Flask Routes ---

@app.route('/')
def dashboard():
    log_html = ""
    for log in reversed(recent_logs):
        css_class = "error" if any(level in log for level in ["ERROR", "CRITICAL"]) else "warning" if "WARNING" in log else "success"
        log_html += f'<div class="{css_class}">{log}</div>'
    return render_template('dashboard.html', logs_html=log_html)

@app.route('/api/health')
def health_api():
    """Serves the latest health data as JSON."""
    return jsonify(health_monitor.get_health_snapshot())

@app.route('/api/intelligence')
def intelligence_api():
    """Serve intelligence statistics"""
    return jsonify(health_monitor.get_intelligence_summary())

@app.route('/run-check', methods=['POST'])
def run_check_endpoint():
    logging.info("Check triggered by Cloud Scheduler.")
    monitor = ShortSaleMonitor()
    try:
        new_breakers_df, ended_breakers_df = monitor.check_for_new_and_ended_breakers()
        health_monitor.record_check_attempt(success=True)
        webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
        if not webhook_url:
            raise ValueError("Webhook URL not found in Firestore")

        discord_client = DiscordClient(webhook_url=webhook_url)
        alert_manager = EnhancedAlertManager(discord_client, template_manager, config.vip_tickers)

        log_msg = f"Analysis complete. Found {len(new_breakers_df)} new, {len(ended_breakers_df)} ended."
        health_monitor.log_transaction(log_msg, "INFO")
        logging.info(log_msg)

        if not new_breakers_df.empty or not ended_breakers_df.empty:
            full_df = monitor.fetch_data()
            if not hasattr(app, 'smart_batcher'):
                app.smart_batcher = SmartAlertBatcher(health_monitor, alert_manager)
            app.smart_batcher.queue_alert(new_breakers_df, ended_breakers_df, full_df)
        else:
            logging.info("No new or ended circuit breakers found.")

        return "Check completed successfully.", 200

    except Exception as e:
        error_msg = f"An error occurred during the scheduled check: {e}"
        logging.error(error_msg, exc_info=True)
        health_monitor.record_check_attempt(success=False, error=str(e))
        return "An error occurred during the check.", 500

@app.route('/report-open-alerts', methods=['POST'])
def report_open_alerts():
    logging.info("Open alerts report triggered by user.")
    submitted_password = request.form.get('password')
    correct_password = get_config_from_firestore('security', 'dashboard_password')
    if not correct_password or submitted_password != correct_password:
        return "Invalid password.", 403

    try:
        webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
        discord_client = DiscordClient(webhook_url=webhook_url)
        alert_manager = EnhancedAlertManager(discord_client, template_manager, config.vip_tickers)
        monitor = ShortSaleMonitor()
        current_df = monitor.fetch_data()

        if current_df is None or current_df.empty:
            alert_manager.send_formatted_alert({'title': "Open Alerts Report", 'message': "Could not retrieve data.", 'color': 0xfca311})
            return redirect(url_for('dashboard'))

        open_alerts = current_df[pd.isnull(current_df['End Time'])]
        formatter = template_manager.get_formatter('short_sale')
        alert_data = formatter.format_open_alerts_report(open_alerts)
        alert_manager.send_formatted_alert(alert_data)
    except Exception as e:
        logging.error(f"Failed to generate open alerts report: {e}", exc_info=True)

    return redirect(url_for('dashboard'))

@app.route('/reset-monitor-state', methods=['POST'])
def reset_monitor_state():
    logging.info("Manual monitor state reset triggered from dashboard.")
    submitted_password = request.form.get('password')
    correct_password = get_config_from_firestore('security', 'dashboard_password')
    if not correct_password or submitted_password != correct_password:
        return "Invalid password.", 403

    try:
        db = firestore.Client()
        doc_ref = db.collection('app_config').document('short_sale_monitor_state')
        doc_ref.delete()
        health_monitor.log_transaction("Monitor state manually reset by user.", "SUCCESS")
        logging.info("Successfully deleted 'short_sale_monitor_state' document.")
    except Exception as e:
        logging.error(f"Failed to delete monitor state: {e}", exc_info=True)
        health_monitor.log_transaction(f"Error resetting state: {e}", "ERROR")
    
    return redirect(url_for('dashboard'))

# Replace the placeholder test routes with this functional code

@app.route('/test-intelligence')
def test_intelligence():
    """Test the intelligence system by analyzing the most recent circuit breaker."""
    try:
        monitor = ShortSaleMonitor()
        full_df = monitor.fetch_data()

        if full_df is None or full_df.empty:
            return "No data available for intelligence testing", 400

        # Analyze the most recent symbol
        sample_symbol = full_df.iloc[0]['Symbol']
        sample_date = full_df.iloc[0]['Trigger Date']
        result = quick_analyze(sample_symbol, sample_date, full_df, config.vip_tickers)

        # Return a simple formatted HTML page
        return f"""
        <html><body style="font-family: monospace; background: #121212; color: #e0e0e0; padding: 2rem;">
        <h2>Intelligence Test Results for: {sample_symbol}</h2>
        <pre style="background: #1e1e1e; padding: 1rem; border-radius: 8px;">{json.dumps(result, indent=2)}</pre>
        <a href="/">- Back to Dashboard</a>
        </body></html>
        """
    except Exception as e:
        logging.error(f"Intelligence test failed: {e}", exc_info=True)
        return f"Intelligence test failed: {str(e)}", 500

@app.route('/test-batching')
def test_batching():
    """Display the current smart batching mode and window."""
    try:
        # This logic determines the batching state based on the current time
        cst = pytz.timezone('America/Chicago')
        now_cst = datetime.now(cst)
        current_time = now_cst.time()
        from datetime import time as dt_time
        
        rush_start, rush_end = dt_time(9, 20), dt_time(10, 0)
        market_start, market_end = dt_time(9, 30), dt_time(16, 0)
        premarket_start = dt_time(8, 0)

        if rush_start <= current_time <= rush_end:
            mode, window = "🔥 RUSH HOUR", 90
        elif market_start <= current_time <= market_end:
            mode, window = "📈 MARKET HOURS", 45
        elif premarket_start <= current_time < rush_start:
            mode, window = "🌅 PRE-MARKET", 30
        else:
            mode, window = "🌙 AFTER HOURS", 15

        return f"""
        <html><body style="font-family: monospace; background: #121212; color: #e0e0e0; padding: 2rem;">
        <h2>Smart Batching System Status</h2>
        <p><strong>Current Time (CST):</strong> {now_cst.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Current Mode:</strong> {mode}</p>
        <p><strong>Alert Batch Window:</strong> {window} seconds</p>
        <a href="/">- Back to Dashboard</a>
        </body></html>
        """
    except Exception as e:
        logging.error(f"Batching test failed: {e}", exc_info=True)
        return f"Test failed: {str(e)}", 500

# Replace the placeholder time_travel route with this functional code

# Replace the old time_travel route with this corrected version

@app.route('/time-travel')
def time_travel():
    """Runs the time travel test for the current time and displays the results."""
    try:
        # Create a timezone-aware datetime object for the current time
        cst = pytz.timezone('America/Chicago')
        target_time = datetime.now(cst)
        
        # Call the test function with the required 'target_time' argument
        results = run_time_travel_test(target_time=target_time)
        
        # Format the results for display in the browser
        return f"""
        <html><body style="font-family: monospace; background: #121212; color: #e0e0e0; padding: 2rem;">
        <h2>Time Travel Test Results</h2>
        <p><strong>Test run for time:</strong> {target_time.strftime('%Y-%m-%d %H:%M:%S CST')}</p>
        <pre style="background: #1e1e1e; padding: 1rem; border-radius: 8px; white-space: pre-wrap; word-wrap: break-word;">{json.dumps(results, indent=2)}</pre>
        <a href="/">- Back to Dashboard</a>
        </body></html>
        """
    except Exception as e:
        logging.error(f"Time travel test failed: {e}", exc_info=True)
        return f"Time travel test failed: {str(e)}", 500
# --- Application Startup ---
if __name__ == '__main__':
    logging.info("--- Starting Secret_Alerts Locally---")
    # The 'debug=True' is useful for local development
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)