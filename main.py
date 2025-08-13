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
# CORRECTED IMPORT: Import the get_config function, not the variables directly.
from config.settings import get_config, get_config_from_firestore
from services.health_monitor import EnhancedHealthMonitor
from services.alert_batcher import SmartAlertBatcher

# --- Global Application Setup ---
app = Flask(__name__)

# CORRECTED CONFIGURATION: Create the config object to access all settings.
config = get_config()

# Setup for the legacy log viewer on the dashboard
recent_logs = deque(maxlen=20)
class CaptureLogsHandler(logging.Handler):
    def emit(self, record):
        recent_logs.append(self.format(record))

# Initialize global objects using the config object
health_monitor = EnhancedHealthMonitor()
# CORRECTED USAGE: Use config.vip_tickers instead of VIP_SYMBOLS
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
        # CORRECTED USAGE: Pass config.vip_tickers to the alert manager
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
        # CORRECTED USAGE: Pass config.vip_tickers to the alert manager
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

# --- Application Startup ---
if __name__ == '__main__':
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
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)