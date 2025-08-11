import os
import time
import logging
import schedule
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Custom Log Handler to Capture Recent Logs ---
# A deque is a list-like container with fast appends and pops from either end.
# We'll use it to keep a running list of the last 10 log records.
recent_logs = deque(maxlen=10)

class CaptureLogsHandler(logging.Handler):
    def emit(self, record):
        # Add the formatted log message to our deque
        recent_logs.append(self.format(record))

# --- Configure Root Logger ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# Get the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Add our custom handler to the root logger
capture_handler = CaptureLogsHandler()
capture_handler.setFormatter(log_formatter)
root_logger.addHandler(capture_handler)

# Also add a standard handler to print logs to the console
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)


# --- Assumed Imports from Your Project ---
# In a real project, these would be in other files.
class MockDiscordClient:
    def __init__(self, webhook_url):
        if not webhook_url:
            raise ValueError("Discord webhook URL is required.")
        logging.info(f"Mock DiscordClient initialized.")
    def send(self, embed):
        logging.info(f"--- MOCK ALERT SENT: {embed['title']} ---")

class MockAlertManager:
    def __init__(self, discord_client):
        self.discord_client = discord_client
    def send_alert(self, title, message, color=0xffa500):
        embed = {'title': title, 'description': message, 'color': color}
        self.discord_client.send(embed)

from monitors.cboe_monitor import CBOEMonitor

# --- Configuration ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "YOUR_DEFAULT_WEBHOOK_URL_HERE")
CHECK_INTERVAL_MINUTES = 15

# --- Web Server for Dashboard ---
class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        # Generate the log entries HTML
        log_html = ""
        for log in reversed(recent_logs): # Show newest first
            color = "#e0e0e0" # Default color
            if "WARNING" in log:
                color = "#fca311" # Yellow for warnings
            elif "ERROR" in log or "CRITICAL" in log:
                color = "#e63946" # Red for errors
            log_html += f'<div style="color: {color};">{log}</div>'

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Secret_Alerts Dashboard</title>
            <meta http-equiv="refresh" content="15">
            <style>
                body {{ background: #1a1a2e; color: #e0e0e0; font-family: monospace; margin: 0; padding: 2rem; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ text-align: center; margin-bottom: 2rem; }}
                .card {{ background: #16213e; padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #00d9ff; }}
                h1, h2 {{ color: #00d9ff; }}
                .log-box {{ height: 300px; overflow-y: auto; background: #0a0e27; padding: 1rem; border-radius: 8px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header"><h1>🚀 Secret_Alerts Dashboard</h1></div>
                <div class="card">
                    <h2>Recent Activity (Live)</h2>
                    <div class="log-box">{log_html}</div>
                </div>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('', port), DashboardHandler)
    logging.info(f"🌐 Web server starting on http://localhost:{port}")
    server.serve_forever()

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

def main():
    import threading

    logging.info("--- Starting Secret_Alerts System ---")

    # Start the web server in a separate thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    # Initialize components
    try:
        discord_client = MockDiscordClient(webhook_url=DISCORD_WEBHOOK_URL)
        alert_manager = MockAlertManager(discord_client=discord_client)
        cboe_monitor = CBOEMonitor()
    except Exception as e:
        logging.critical(f"Failed to initialize system components: {e}")
        return

    logging.info(f"Scheduling check every {CHECK_INTERVAL_MINUTES} minutes.")
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(perform_check, monitor=cboe_monitor, alerter=alert_manager)
    
    # Run the initial check immediately
    perform_check(monitor=cboe_monitor, alerter=alert_manager)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
