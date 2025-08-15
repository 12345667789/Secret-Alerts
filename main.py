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
from services.speed_monitor import SpeedMonitor
from alerts.alert_intelligence import quick_analyze
from testing.time_travel_tester import run_time_travel_test, get_suggestions

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

# --- Global Component Initialization ---
health_monitor = EnhancedHealthMonitor()
template_manager = AlertTemplateManager(vip_symbols=config.vip_tickers)
speed_monitor = SpeedMonitor()

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
    """Serves the latest health data as JSON."""
    return jsonify(health_monitor.get_health_snapshot())

@app.route('/api/intelligence')
def intelligence_api():
    """Serve intelligence statistics"""
    return jsonify(health_monitor.get_intelligence_summary())

@app.route('/run-check', methods=['POST'])
def run_check_endpoint():
    app.logger.info("Check triggered by Cloud Scheduler.")
    monitor = ShortSaleMonitor()
    try:
        new_breakers_df, ended_breakers_df, current_df = monitor.get_changes()
        health_monitor.record_check_attempt(success=True)

        if current_df is None:
            raise RuntimeError("Failed to fetch data from CBOE; aborting check.")

        if not new_breakers_df.empty or not ended_breakers_df.empty:
            webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
            if not webhook_url:
                raise ValueError("Webhook URL not found in Firestore")

            discord_client = DiscordClient(webhook_url=webhook_url)
            alert_manager = EnhancedAlertManager(discord_client, template_manager.short_sale, config.vip_tickers)

            if not hasattr(app, 'smart_batcher'):
                app.smart_batcher = SmartAlertBatcher(health_monitor, alert_manager)
            
            app.smart_batcher.queue_alert(new_breakers_df, ended_breakers_df, current_df)
            
            app.logger.info("Alerts queued successfully. Saving new state to Firestore.")
            monitor.save_state(current_df)
        else:
            app.logger.info("No new or ended circuit breakers found. Updating state.")
            monitor.save_state(current_df)

        return "Check completed successfully.", 200

    except Exception as e:
        error_msg = f"An error occurred during the scheduled check: {e}. State was NOT saved."
        app.logger.error(error_msg, exc_info=True)
        health_monitor.record_check_attempt(success=False, error=str(e))
        return "An error occurred during the check.", 500

@app.route('/report-open-alerts', methods=['POST'])
def report_open_alerts():
    app.logger.info("Open alerts report triggered by user.")
    submitted_password = request.form.get('password')
    correct_password = get_config_from_firestore('security', 'dashboard_password')
    if not correct_password or submitted_password != correct_password:
        return "Invalid password.", 403

    try:
        webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
        discord_client = DiscordClient(webhook_url=webhook_url)
        alert_manager = EnhancedAlertManager(discord_client, template_manager.short_sale, config.vip_tickers)
        monitor = ShortSaleMonitor()
        current_df = monitor.fetch_data()

        if current_df is None or current_df.empty:
            alert_manager.send_formatted_alert({'title': "Open Alerts Report", 'message': "Could not retrieve data.", 'color': 0xfca311})
            return redirect(url_for('dashboard'))

        open_alerts = current_df[pd.isnull(current_df['End Time'])]
        
        alert_manager.send_open_alerts_report(open_alerts)
        
    except Exception as e:
        app.logger.error(f"Failed to generate open alerts report: {e}", exc_info=True)

    return redirect(url_for('dashboard'))

@app.route('/reset-monitor-state', methods=['POST'])
def reset_monitor_state():
    app.logger.info("Manual monitor state reset triggered from dashboard.")
    submitted_password = request.form.get('password')
    correct_password = get_config_from_firestore('security', 'dashboard_password')
    if not correct_password or submitted_password != correct_password:
        return "Invalid password.", 403

    try:
        monitor = ShortSaleMonitor()
        monitor.save_state(pd.DataFrame()) # Reset by saving an empty state
        health_monitor.log_transaction("Monitor state manually reset by user.", "SUCCESS")
        app.logger.info("Successfully reset 'short_sale_monitor_state' document.")
    except Exception as e:
        app.logger.error(f"Failed to reset monitor state: {e}", exc_info=True)
        health_monitor.log_transaction(f"Error resetting state: {e}", "ERROR")
    
    return redirect(url_for('dashboard'))

@app.route('/test-intelligence')
def test_intelligence():
    """Test the intelligence system by analyzing the most recent circuit breaker."""
    try:
        monitor = ShortSaleMonitor()
        full_df = monitor.fetch_data()

        if full_df is None or full_df.empty:
            return "No data available for intelligence testing", 400

        sample_symbol = full_df.iloc[0]['Symbol']
        sample_date = full_df.iloc[0]['Trigger Date']
        result = quick_analyze(sample_symbol, sample_date, full_df, config.vip_tickers)

        return f"""
        <html><body style="font-family: monospace; background: #121212; color: #e0e0e0; padding: 2rem;">
        <h2>Intelligence Test Results for: {sample_symbol}</h2>
        <pre style="background: #1e1e1e; padding: 1rem; border-radius: 8px;">{json.dumps(result, indent=2)}</pre>
        <a href="/">- Back to Dashboard</a>
        </body></html>
        """
    except Exception as e:
        app.logger.error(f"Intelligence test failed: {e}", exc_info=True)
        return f"Intelligence test failed: {str(e)}", 500

@app.route('/test-batching')
def test_batching():
    """Display the current smart batching mode and window."""
    try:
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
        app.logger.error(f"Batching test failed: {e}", exc_info=True)
        return f"Test failed: {str(e)}", 500

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

@app.route('/test-discord')
def test_discord():
    """Test Discord functionality via web interface"""
    try:
        webhook_url = get_config_from_firestore('discord_webhooks', 'short_sale_alerts')
        if not webhook_url:
            return "❌ No webhook URL found", 500
            
        discord_client = DiscordClient(webhook_url)
        
        # Test 1: Speed alert format  
        speed_message = f"⚡ **SPEED ALERT** ⚡\n**NEW CIRCUIT BREAKERS:** TEST-SYMBOL\n*Test at {datetime.now().strftime('%H:%M:%S')}*"
        success1 = discord_client.send_alert(
            "🧪 Discord Test - Speed Alert",
            speed_message,
            color=0xFF4500  # Orange
        )
        
        # Test 2: Health report format
        health_message = """**Speed Monitor Health Report** 🟢
        
**Last 15 Minutes:**
- Checks performed: 5 (TEST)
- Alerts sent: 1 (TEST)
- Errors: 0
- Current breakers: 23

**Overall Stats:**
- Total checks: 100 (TEST)
- Success rate: 100.0%
- Status: Testing Discord connectivity

*This is a test message*"""

        success2 = discord_client.send_alert(
            "📊 Discord Test - Health Report",
            health_message,
            color=0x00FF00  # Green
        )
        
        results = f"Speed Alert: {'✅' if success1 else '❌'}, Health Report: {'✅' if success2 else '❌'}"
        
        return f"""
        <html><body style="font-family: monospace; background: #121212; color: #e0e0e0; padding: 2rem;">
        <h2>Discord Test Results</h2>
        <p>{results}</p>
        <p>Check your Discord channel for 2 test messages:</p>
        <ul>
        <li>🟠 Orange "Speed Alert" message</li>
        <li>🟢 Green "Health Report" message</li>
        </ul>
        <a href="/">← Back to Dashboard</a>
        </body></html>
        """
        
    except Exception as e:
        return f"❌ Test error: {str(e)}", 500


@app.route('/time-travel')
def time_travel():
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
        suggestions = get_suggestions(vip_symbols=config.vip_tickers)
        html = """
        <html><body style="font-family: monospace; background: #121212; color: #e0e0e0; padding: 2rem;">
        <h2>Time Travel Test</h2>
        <p>Select a historical time to simulate an alert check.</p>
        <div style="background: #1e1e1e; padding: 1rem; border-radius: 8px;">
        """
        for sug in suggestions:
            vip_label = " (💎 VIP)" if sug.get('is_vip') else ""
            html += f'<p><a href="/time-travel?time={sug["test_time"]}" style="color: #00d9ff;">{sug["test_time"]}</a> - {sug["description"]}{vip_label}</p>'
        html += """
        </div>
        <br/><a href="/">- Back to Dashboard</a>
        </body></html>
        """
        return html

# --- Application Startup ---
if __name__ == '__main__':
    app.logger.info("--- Starting Secret_Alerts Locally---")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)