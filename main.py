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
# NOTE: Imports for testing modules have been removed from here.
from alerts.discord_client import DiscordClient
from alerts.templates import AlertTemplateManager
from alerts.enhanced_alert_manager import EnhancedAlertManager
from monitors.cboe_monitor import ShortSaleMonitor
from config.settings import get_config, get_config_from_firestore
from services.health_monitor import EnhancedHealthMonitor
from services.alert_batcher import SmartAlertBatcher

# --- Global Application Setup ---
app = Flask(__name__)
config = get_config()
log_lock = threading.Lock()

# --- Logging Setup ---
recent_logs = deque(maxlen=20)
class CaptureLogsHandler(logging.Handler):
    def emit(self, record):
        with log_lock:
            recent_logs.append(self.format(record))

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)
capture_handler = CaptureLogsHandler()
capture_handler.setFormatter(log_formatter)
app.logger.addHandler(capture_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
app.logger.addHandler(console_handler)

# Initialize global objects
health_monitor = EnhancedHealthMonitor()
template_manager = AlertTemplateManager(vip_symbols=config.vip_tickers)

# --- Flask Routes ---

@app.route('/')
def dashboard():
    with log_lock:
        logs_to_display = list(recent_logs)
    log_html = ""
    for log in reversed(logs_to_display):
        css_class = "error" if any(level in log for level in ["ERROR", "CRITICAL"]) else "warning" if "WARNING" in log else "success"
        log_html += f'<div class="{css_class}">{log}</div>'
    return render_template('dashboard.html', logs_html=log_html)

@app.route('/api/health')
def health_api():
    return jsonify(health_monitor.get_health_snapshot())

@app.route('/api/intelligence')
def intelligence_api():
    return jsonify(health_monitor.get_intelligence_summary())

# ... (Your other main routes like /run-check, /report-open-alerts, etc. go here) ...
# For brevity, I'm omitting them, but they should be the same as your last working version.

@app.route('/test-intelligence')
def test_intelligence():
    """Test the intelligence system by analyzing the most recent circuit breaker."""
    # MOVED IMPORT: Import only when this route is called.
    from alerts.alert_intelligence import quick_analyze
    try:
        monitor = ShortSaleMonitor()
        full_df = monitor.fetch_data()
        if full_df is None or full_df.empty: return "No data available for intelligence testing", 400
        sample_symbol = full_df.iloc[0]['Symbol']
        sample_date = full_df.iloc[0]['Trigger Date']
        result = quick_analyze(sample_symbol, sample_date, full_df, config.vip_tickers)
        return f"""<html>... (html for results) ...</html>"""
    except Exception as e:
        app.logger.error(f"Intelligence test failed: {e}", exc_info=True)
        return f"Intelligence test failed: {str(e)}", 500

@app.route('/test-batching')
def test_batching():
    # This route is self-contained, no changes needed.
    # ... (code for this route remains the same)
    return "Batching Test Page"

@app.route('/time-travel')
def time_travel():
    """Runs a time travel test or shows suggestions."""
    # MOVED IMPORTS: Import only when this route is called.
    from testing.time_travel_tester import run_time_travel_test, get_test_suggestions

    target_time_str = request.args.get('time')
    if target_time_str:
        try:
            target_time = datetime.strptime(target_time_str, '%Y-%m-%d %H:%M:%S')
            target_time = pytz.timezone('America/Chicago').localize(target_time)
            results = run_time_travel_test(target_time=target_time, vip_symbols=config.vip_tickers)
            return render_template('time_travel_results.html', results=results)
        except Exception as e:
            app.logger.error(f"Time travel test failed: {e}", exc_info=True)
            return f"Time travel test failed: {str(e)}", 500
    else:
        suggestions = get_test_suggestions(vip_symbols=config.vip_tickers)
        # ... (html generation logic for suggestions remains the same) ...
        return "Time Travel Suggestions Page"

# --- Application Startup ---
if __name__ == '__main__':
    app.logger.info("--- Starting Secret_Alerts Locally---")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)