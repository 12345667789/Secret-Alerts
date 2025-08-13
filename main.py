import os
import logging
import pandas as pd
import json
import threading
import time as time_module
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
from testing.time_travel_tester import run_time_travel_test, get_test_suggestions
from config.settings import get_config_from_firestore, VIP_SYMBOLS
from services.health_monitor import EnhancedHealthMonitor
from services.alert_batcher import SmartAlertBatcher

# --- Global Application Setup ---
# The Flask app must be initialized at the top.
app = Flask(__name__)

# Setup for the legacy log viewer on the dashboard
recent_logs = deque(maxlen=20)
class CaptureLogsHandler(logging.Handler):
    def emit(self, record):
        recent_logs.append(self.format(record))

# Initialize global objects
health_monitor = EnhancedHealthMonitor()
template_manager = AlertTemplateManager(vip_symbols=VIP_SYMBOLS)

# --- Flask Routes ---

@app.route('/')
def dashboard():
    # Removed the duplicate "def dashboard():" line
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

@app.route('/test-intelligence')
def test_intelligence():
    """Test the intelligence system"""
    try:
        monitor = ShortSaleMonitor()
        full_df = monitor.fetch_data()

        if full_df is None or full_df.empty:
            return "No data available for intelligence testing", 400

        from alerts.alert_intelligence import quick_analyze
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
        <p style="text-align: center; margin-top: 20px;"><a href="/">← Back to Dashboard</a></p>
        </body></html>
        """
    except Exception as e:
        return f"Intelligence test failed: {str(e)}", 500

@app.route('/test-batching')
def test_batching():
    """Test the smart batching system with correct timezone"""
    try:
        cst = pytz.timezone('America/Chicago')
        now_cst = datetime.now(cst)
        current_time = now_cst.time()
        from datetime import time as dt_time
        rush_start, rush_end = dt_time(9, 20), dt_time(10, 0)
        market_start, market_end = dt_time(9, 30), dt_time(16, 0)
        premarket_start = dt_time(8, 0)

        if rush_start <= current_time <= rush_end:
            mode, window, desc = "RUSH HOUR", 90, "Peak activity - max batching"
        elif market_start <= current_time <= market_end:
            mode, window, desc = "MARKET HOURS", 45, "Normal hours - balanced batching"
        elif premarket_start <= current_time < rush_start:
            mode, window, desc = "PRE-MARKET", 30, "Pre-market prep - moderate batching"
        else:
            mode, window, desc = "AFTER HOURS", 15, "Minimal batching - VIP alerts bypass"

        return f"""
        <html><body>
        <h2>🃏 Smart Batching System Test</h2>
        <p><strong>Current Time (CST):</strong> {now_cst.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Market Mode:</strong> {mode}</p>
        <p><strong>Batch Window:</strong> {window} seconds</p>
        <p><strong>Description:</strong> {desc}</p>
        <a href="/">← Back to Dashboard</a>
        </body></html>
        """
    except Exception as e:
        return f"Test failed: {str(e)}", 500

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
        alert_manager = EnhancedAlertManager(discord_client, template_manager, VIP_SYMBOLS)

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
        alert_manager = EnhancedAlertManager(discord_client, template_manager, VIP_SYMBOLS)
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

# ... Add other report routes (/report-morning-summary, etc.) here if needed ...

@app.route('/reset-monitor-state', methods=['POST'])
def reset_monitor_state():
    logging.info("Manual monitor state reset triggered from dashboard.")
    
    submitted_password = request.form.get('password')
    correct_password = get_config_from_firestore('security', 'dashboard_password')
    
    if not correct_password or submitted_password != correct_password:
        return "Invalid password.", 403

    try:
        db = firestore.Client()
        # The path to your state document in Firestore
        doc_ref = db.collection('app_config').document('short_sale_monitor_state')
        doc_ref.delete()
        
        health_monitor.log_transaction("Monitor state manually reset by user.", "SUCCESS")
        logging.info("Successfully deleted 'short_sale_monitor_state' document.")
            
    except Exception as e:
        logging.error(f"Failed to delete monitor state: {e}", exc_info=True)
        health_monitor.log_transaction(f"Error resetting state: {e}", "ERROR")
    
    return redirect(url_for('dashboard'))

# --- Application Startup ---
if __name__ == '__main__':
    # Setup logging
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    capture_handler = CaptureLogsHandler()
    capture_handler.setFormatter(log_formatter)
    root_logger.addHandler(capture_handler)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

    logging.info("--- Starting Secret_Alerts ---")
    logging.info("✅ Codebase refactored for stability.")
    logging.info(f"💎 VIP Symbols Loaded: {len(VIP_SYMBOLS)}")
    logging.info("⏰ Smart Alert Batching: Active")

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)