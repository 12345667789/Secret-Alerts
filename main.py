import os
import time
import logging
import schedule
from collections import deque
from flask import Flask, render_template_string

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

# --- Assumed/Mock Imports ---
class MockDiscordClient:
    def __init__(self, webhook_url):
        if not webhook_url: raise ValueError("Webhook URL required")
        logging.info("Mock DiscordClient initialized.")
    def send(self, embed):
        logging.info(f"--- MOCK ALERT SENT: {embed['title']} ---")

class MockAlertManager:
    def __init__(self, discord_client):
        self.discord_client = discord_client
    def send_alert(self, title, message, color=0xffa500):
        embed = {'title': title, 'description': message, 'color': color}
        self.discord_client.send(embed)

from monitors.cboe_monitor import CBOEMonitor

# --- Flask App Definition ---
# This 'app' variable is what Gunicorn will look for.
app = Flask(__name__)

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Secret_Alerts Dashboard</title>
    <meta http-equiv="refresh" content="15">
    <style>
        body { background: #1a1a2e; color: #e0e0e0; font-family: monospace; margin: 0; padding: 2rem; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 2rem; }
        .card { background: #16213e; padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #00d9ff; }
        h1, h2 { color: #00d9ff; }
        .log-box { height: 400px; overflow-y: auto; background: #0a0e27; padding: 1rem; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>🚀 Secret_Alerts Dashboard</h1></div>
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
        color = "#e0e0e0"
        if "WARNING" in log: color = "#fca311"
        elif "ERROR" in log or "CRITICAL" in log: color = "#e63946"
        log_html += f'<div style="color: {color};">{log}</div>'
    return render_template_string(DASHBOARD_TEMPLATE, logs_html=log_html)

# --- Main Application Logic ---
def perform_check(monitor, alerter):
    logging.info("Scheduler: Starting job to check for new symbols.")
    try:
        new_symbols_df = monitor.check_for_unusual_volume()
        if not new_symbols_df.empty:
            logging.warning(f"Found {len(new_symbols_df)} new symbols to alert on.")
            for _, row in new_symbols_df.iterrows():
                title = f"🚀 New Symbol Alert: ${row['Symbol']}"
                message = f"Unusual volume detected for **{row['Symbol']}**. Volume: **{int(row['Total_Volume']):,}**"
                alerter.send_alert(title, message)
        else:
            logging.info("Job finished. No new symbols found.")
    except Exception as e:
        logging.error(f"An error occurred during the scheduled check: {e}", exc_info=True)

def run_scheduled_jobs():
    """This function runs in the background to perform checks."""
    try:
        discord_client = MockDiscordClient(webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", "http://mock.url"))
        alert_manager = MockAlertManager(discord_client=discord_client)
        cboe_monitor = CBOEMonitor()
    except Exception as e:
        logging.critical(f"Failed to initialize components for scheduler: {e}")
        return

    schedule.every(15).minutes.do(perform_check, monitor=cboe_monitor, alerter=alert_manager)
    
    # Run one check immediately at startup
    perform_check(monitor=cboe_monitor, alerter=alert_manager)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    # This block is for local development. Gunicorn will not run this.
    # It starts the scheduler in a background thread and then the Flask dev server.
    import threading
    scheduler_thread = threading.Thread(target=run_scheduled_jobs, daemon=True)
    scheduler_thread.start()
    
    # The Flask development server is NOT for production.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)
