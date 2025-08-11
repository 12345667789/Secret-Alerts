import os
import logging
from collections import deque
from flask import Flask, render_template_string, request

# --- Log Capturing Setup ---
# This part remains the same to capture logs for the dashboard
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
# These would be your actual classes from other files
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
app = Flask(__name__)

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
    """Renders the dashboard with the most recent logs."""
    log_html = ""
    for log in reversed(recent_logs):
        color = "#e0e0e0"
        if "WARNING" in log: color = "#fca311"
        elif "ERROR" in log or "CRITICAL" in log: color = "#e63946"
        log_html += f'<div style="color: {color};">{log}</div>'
    return render_template_string(DASHBOARD_TEMPLATE, logs_html=log_html)


@app.route('/run-check', methods=['POST'])
def run_check_endpoint():
    """
    This is the secure endpoint that Cloud Scheduler will call.
    It runs the alert check logic.
    """
    logging.info("Check triggered by Cloud Scheduler.")
    try:
        # Initialize components needed for the check
        discord_client = MockDiscordClient(webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", "http://mock.url"))
        alert_manager = MockAlertManager(discord_client=discord_client)
        cboe_monitor = CBOEMonitor()
        
        # Perform the check
        new_symbols_df = cboe_monitor.check_for_unusual_volume()

        if not new_symbols_df.empty:
            logging.warning(f"Found {len(new_symbols_df)} new symbols to alert on.")
            for _, row in new_symbols_df.iterrows():
                title = f"🚀 New Symbol Alert: ${row['Symbol']}"
                message = f"Unusual volume detected for **{row['Symbol']}**. Volume: **{int(row['Total_Volume']):,}**"
                alert_manager.send_alert(title, message)
        else:
            logging.info("Check finished. No new symbols found.")
        
        return "Check completed successfully.", 200

    except Exception as e:
        logging.error(f"An error occurred during the scheduled check: {e}", exc_info=True)
        return "An error occurred during the check.", 500


if __name__ == '__main__':
    # This block is for local development only. Gunicorn will not run this.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
