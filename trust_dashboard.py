"""
trust_dashboard.py

A self-contained monitoring system and web dashboard for the Secret_Alerts project.
This module provides a "Trust Dashboard" to answer three key questions:
1. Is the system successfully downloading the latest data? (Data Freshness)
2. What was the outcome of the most recent checks? (Transaction Log)
3. What alerts has the system actually sent? (Alert Ledger)
"""

import json
import threading
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from collections import deque
import time
import pytz

# --- Core Health Monitoring Class ---

class HealthMonitor:
    """
    A thread-safe class to track the health and activity of the monitoring system.
    This object should be created once and shared with the main application loop
    and the dashboard server.
    """
    def __init__(self, max_log_size=100, max_ledger_size=200):
        self.lock = threading.Lock()
        self.cst = pytz.timezone('America/Chicago')

        # 1. Data Freshness Status
        self.last_check_status = {
            "timestamp": None,
            "successful": False,
            "file_hash": "N/A",
            "error_message": "No checks run yet."
        }

        # 2. Transaction Log
        self.transaction_log = deque(maxlen=max_log_size)

        # 3. Alert Ledger
        self.alert_ledger = deque(maxlen=max_ledger_size)
        
        self.log_transaction("System Initialized", "INFO")

    def _get_current_time_str(self):
        return datetime.now(self.cst).strftime('%Y-%m-%d %H:%M:%S CST')

    def record_check_attempt(self, success: bool, file_hash: str = None, error: str = None):
        """
        Call this every time the system attempts to download and check the CBOE file.
        This updates the "Data Freshness" panel.
        """
        with self.lock:
            self.last_check_status = {
                "timestamp": self._get_current_time_str(),
                "successful": success,
                "file_hash": file_hash if success else "FAILED",
                "error_message": error
            }
        
        if success:
            self.log_transaction(f"Data fetch successful. Hash: {file_hash[:12]}...", "SUCCESS")
        else:
            self.log_transaction(f"Data fetch FAILED. Reason: {error}", "ERROR")

    def log_transaction(self, message: str, level: str = "INFO"):
        """
        Call this to record any significant event (e.g., analysis result).
        This updates the "Recent Activity" log.
        Levels: INFO, SUCCESS, WARN, ERROR
        """
        with self.lock:
            self.transaction_log.appendleft({
                "timestamp": self._get_current_time_str(),
                "message": message,
                "level": level
            })

    def record_alert_sent(self, alert_type: str, symbol: str, details: str):
        """
        Call this immediately after a Discord alert is confirmed sent.
        This updates the "Alert Ledger".
        """
        with self.lock:
            self.alert_ledger.appendleft({
                "timestamp": self._get_current_time_str(),
                "alert_type": alert_type, # e.g., "NEW_BREAKER", "ENDED_BREAKER"
                "symbol": symbol,
                "details": details
            })
        self.log_transaction(f"Alert sent for {symbol} ({alert_type})", "SUCCESS")

    def get_health_snapshot(self):
        """Returns all current health data for the dashboard API."""
        with self.lock:
            return {
                "last_check": self.last_check_status.copy(),
                "transactions": list(self.transaction_log),
                "alerts": list(self.alert_ledger)
            }

# --- Web Dashboard Components ---

class TrustDashboardHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for the Trust Dashboard."""

    # Make the HealthMonitor instance available to the handler
    monitor: HealthMonitor = None

    def do_GET(self):
        if self.path == '/':
            self.serve_dashboard_page()
        elif self.path == '/api/health':
            self.serve_health_api()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'404 Not Found')

    def serve_health_api(self):
        """Serves the latest health data as JSON."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        snapshot = self.monitor.get_health_snapshot()
        self.wfile.write(json.dumps(snapshot).encode('utf-8'))

    def serve_dashboard_page(self):
        """Serves the main HTML dashboard page."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        # The meta refresh tag ensures updates even if JS is disabled
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Secret_Alerts Trust Dashboard</title>
            <meta http-equiv="refresh" content="900">
            <style>
                body {{ font-family: 'Segoe UI', system-ui, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 20px; }}
                .container {{ max-width: 1400px; margin: 0 auto; display: grid; grid-template-columns: repeat(12, 1fr); gap: 20px; }}
                .header {{ grid-column: 1 / -1; text-align: center; padding-bottom: 20px; border-bottom: 1px solid #333; }}
                .header h1 {{ color: #4CAF50; margin: 0; }}
                .module {{ background-color: #1e1e1e; border: 1px solid #333; border-radius: 8px; padding: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }}
                .module h2 {{ margin-top: 0; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
                .data-freshness {{ grid-column: 1 / 5; }}
                .transaction-log {{ grid-column: 5 / -1; }}
                .alert-ledger {{ grid-column: 1 / -1; }}
                .status-grid {{ display: grid; grid-template-columns: 1fr 2fr; gap: 10px; align-items: center; }}
                .status-grid strong {{ color: #aaa; }}
                .status-value {{ font-family: 'Courier New', monospace; font-size: 1.1em; word-wrap: break-word; }}
                .status-good {{ color: #66bb6a; }}
                .status-bad {{ color: #ef5350; }}
                .log-table, .ledger-table {{ width: 100%; border-collapse: collapse; }}
                .log-table th, .log-table td, .ledger-table th, .ledger-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
                .log-table th, .ledger-table th {{ background-color: #2a2a2a; }}
                .log-level-SUCCESS {{ color: #66bb6a; }}
                .log-level-ERROR {{ color: #ef5350; }}
                .log-level-WARN {{ color: #ffa726; }}
                .log-level-INFO {{ color: #42a5f5; }}
                .table-container {{ max-height: 400px; overflow-y: auto; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header"><h1>🛡️ Secret_Alerts Trust Dashboard</h1></div>

                <div class="module data-freshness">
                    <h2>1. Data Freshness</h2>
                    <div id="freshness-content">Loading...</div>
                </div>

                <div class="module transaction-log">
                    <h2>2. Recent Activity Log</h2>
                    <div class="table-container">
                        <table class="log-table">
                            <thead><tr><th>Time</th><th>Level</th><th>Message</th></tr></thead>
                            <tbody id="log-content"><tr><td colspan="3">Loading...</td></tr></tbody>
                        </table>
                    </div>
                </div>

                <div class="module alert-ledger">
                    <h2>3. Alert Ledger (Confirmed Sent)</h2>
                    <div class="table-container">
                        <table class="ledger-table">
                            <thead><tr><th>Time</th><th>Type</th><th>Symbol</th><th>Details</th></tr></thead>
                            <tbody id="ledger-content"><tr><td colspan="4">Loading...</td></tr></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <script>
                function updateDashboard() {{
                    fetch('/api/health')
                        .then(response => response.json())
                        .then(data => {{
                            // 1. Update Freshness
                            const freshnessDiv = document.getElementById('freshness-content');
                            const lastCheck = data.last_check;
                            const successClass = lastCheck.successful ? 'status-good' : 'status-bad';
                            const successText = lastCheck.successful ? 'Success' : 'Failed';
                            freshnessDiv.innerHTML = `
                                <div class="status-grid">
                                    <strong>Last Check:</strong><span class="status-value">${{lastCheck.timestamp || 'N/A'}}</span>
                                    <strong>Status:</strong><span class="status-value ${{successClass}}">${{successText}}</span>
                                    <strong>File Hash:</strong><span class="status-value">${{lastCheck.file_hash}}</span>
                                    <strong>Details:</strong><span class="status-value">${{lastCheck.error_message || 'OK'}}</span>
                                </div>
                            `;

                            // 2. Update Transaction Log
                            const logBody = document.getElementById('log-content');
                            logBody.innerHTML = '';
                            if (data.transactions.length === 0) {{
                                logBody.innerHTML = '<tr><td colspan="3">No transactions logged yet.</td></tr>';
                            }} else {{
                                data.transactions.forEach(log => {{
                                    const row = logBody.insertRow();
                                    row.innerHTML = `
                                        <td>${{log.timestamp}}</td>
                                        <td class="log-level-${{log.level}}">${{log.level}}</td>
                                        <td>${{log.message}}</td>
                                    `;
                                }});
                            }}

                            // 3. Update Alert Ledger
                            const ledgerBody = document.getElementById('ledger-content');
                            ledgerBody.innerHTML = '';
                            if (data.alerts.length === 0) {{
                                ledgerBody.innerHTML = '<tr><td colspan="4">No alerts sent yet.</td></tr>';
                            }} else {{
                                data.alerts.forEach(alert => {{
                                    const row = ledgerBody.insertRow();
                                    row.innerHTML = `
                                        <td>${{alert.timestamp}}</td>
                                        <td>${{alert.alert_type}}</td>
                                        <td>${{alert.symbol}}</td>
                                        <td>${{alert.details}}</td>
                                    `;
                                }});
                            }}
                        }})
                        .catch(error => console.error('Failed to update dashboard:', error));
                }}

                // Initial load and set interval for updates every 15 seconds
                document.addEventListener('DOMContentLoaded', () => {{
                    updateDashboard();
                    setInterval(updateDashboard, 15000);
                }});
            </script>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))


def start_trust_dashboard_server(monitor_instance: HealthMonitor, port: int = 8081):
    """
    Starts the Trust Dashboard web server in a separate thread.

    Args:
        monitor_instance: The shared HealthMonitor object.
        port: The port to run the dashboard on.
    """
    def handler_factory(*args, **kwargs):
        # This factory ensures the handler has access to the monitor instance
        handler = TrustDashboardHandler(*args, **kwargs)
        handler.monitor = monitor_instance
        return handler

    server = HTTPServer(('', port), handler_factory)
    
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"🛡️ Trust Dashboard is LIVE at http://localhost:{port}")
    return server

# --- Example Usage (for testing this file directly) ---
if __name__ == '__main__':
    print("Running Trust Dashboard in standalone test mode.")
    
    # Create a HealthMonitor instance
    test_monitor = HealthMonitor()
    
    # Start the dashboard server
    dashboard_server = start_trust_dashboard_server(test_monitor, port=8081)

    # --- Simulate the main application's activity ---
    def simulate_app_activity(monitor: HealthMonitor):
        while True:
            print("\n--- Simulating a check cycle ---")
            # Simulate a successful check
            time.sleep(10)
            file_content = f"Some data from CBOE at {time.time()}".encode('utf-8')
            file_hash = hashlib.md5(file_content).hexdigest()
            monitor.record_check_attempt(success=True, file_hash=file_hash)
            monitor.log_transaction("Analysis: No changes detected.", "INFO")
            
            # Simulate a check that finds something
            time.sleep(15)
            new_file_content = f"TSLA added at {time.time()}".encode('utf-8')
            new_file_hash = hashlib.md5(new_file_content).hexdigest()
            monitor.record_check_attempt(success=True, file_hash=new_file_hash)
            monitor.log_transaction("Analysis: Found 1 new breaker [TSLA].", "WARN")
            monitor.record_alert_sent(
                alert_type="NEW_BREAKER",
                symbol="TSLA",
                details="Trigger Time: 14:30:00"
            )

            # Simulate a failed check
            time.sleep(10)
            monitor.record_check_attempt(success=False, error="HTTP 503 Service Unavailable")

    simulation_thread = threading.Thread(target=simulate_app_activity, args=(test_monitor,), daemon=True)
    simulation_thread.start()

    try:
        # Keep the main thread alive to let the servers run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down dashboard server.")
        dashboard_server.shutdown()
