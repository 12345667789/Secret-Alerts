#!/usr/bin/env python3
"""
Secret_Alerts v4.1 - Modular Trading Intelligence System (Debug Version)
Main orchestrator with comprehensive health checks and debugging
"""

import os
import sys
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import traceback
import pandas as pd

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_config
from monitors.cboe_monitor import CBOEMonitor
from alerts.alert_manager import AlertManager
from alerts.discord_client import DiscordClient
from utils.market_schedule import MarketScheduler

# --- Global Test Mode State ---
# This can now be changed at runtime via the web dashboard
TEST_MODE = True

class DebugTradingSystemOrchestrator:
    def __init__(self):
        print("🔍 DEBUG: Initializing TradingSystemOrchestrator...")
        
        self.running = False
        self.live_cboe_url = "" # Store the original URL
        
        try:
            # Initialize configuration
            print("🔍 DEBUG: Loading configuration...")
            self.config = get_config()
            self.live_cboe_url = self.config.cboe_url # Save the live URL

            # Initialize Discord client, Alert Manager, etc.
            self.discord = DiscordClient(self.config.discord_webhook)
            self.alert_manager = AlertManager(self.config, self.discord)
            self.cboe_monitor = CBOEMonitor(self.config, self.alert_manager)
            self.market_scheduler = MarketScheduler(self.config)
            
            print("\n🎉 All modules initialized successfully!\n")
            
        except Exception as e:
            print(f"❌ CRITICAL: Failed to initialize system: {e}")
            sys.exit(1)

    def start_web_server(self):
        """Enhanced web server with debug endpoints and mode toggles"""
        port = int(os.environ.get('PORT', 8080))
        
        class DebugDashboardHandler(BaseHTTPRequestHandler):
            def __init__(self, *args, trading_system=None, **kwargs):
                self.trading_system = trading_system
                super().__init__(*args, **kwargs)

            def do_GET(self):
                global TEST_MODE
                if self.path == '/':
                    self.serve_dashboard()
                elif self.path == '/test/force-alert':
                    self.handle_force_alert()
                # --- NEW ENDPOINTS FOR TOGGLING MODE ---
                elif self.path == '/enable_test_mode':
                    TEST_MODE = True
                    self.trading_system.alert_manager.send_system_alert("🧪 Test Mode Enabled", "System is now monitoring the test URL with rapid checks.", 0xffa500)
                    self.serve_dashboard()
                elif self.path == '/disable_test_mode':
                    TEST_MODE = False
                    self.trading_system.alert_manager.send_system_alert("🟢 Production Mode Enabled", "System is now monitoring the live CBOE URL with normal intervals.", 0x28a745)
                    self.serve_dashboard()
                else:
                    self.send_error(404, "Not Found")
            
            def handle_force_alert(self):
                result = self.trading_system.cboe_monitor.manual_check_active_positions()
                self._send_simple_response("Forced Alert Test", f"<pre>{json.dumps(result, indent=2)}</pre>")

            def serve_dashboard(self):
                """Serve main dashboard with debug info and mode toggle buttons"""
                global TEST_MODE
                mode, status = self.trading_system.market_scheduler.get_current_status()
                
                if TEST_MODE:
                    mode = "TEST MODE (RUSH)"
                    status = f"Active & Monitoring (Interval: 15s)"

                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Secret_Alerts v4.1</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="30">
    <style>
        body {{ background: #1a1a2e; color: #e0e0e0; font-family: sans-serif; margin: 0; padding: 2rem; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 12px; }}
        .banner {{ text-align: center; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; font-weight: bold; }}
        .test-mode-banner {{ background: #e63946; color: #fff; }}
        .prod-mode-banner {{ background: #2a9d8f; color: #fff; }}
        .status-card {{ background: #16213e; padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #00d9ff; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }}
        .card {{ background: #16213e; padding: 1.5rem; border-radius: 12px; }}
        .btn {{ background: #00d9ff; color: #1a1a2e; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block; margin: 0.25rem; }}
        .btn-alert {{ background: #ff5555; }}
        .btn-toggle-test {{ background: #fca311; }}
        .btn-toggle-prod {{ background: #2a9d8f; }}
    </style>
</head>
<body>
    <div class="container">
        {'<div class="banner test-mode-banner">🧪 LIVE TEST MODE ACTIVE</div>' if TEST_MODE else '<div class="banner prod-mode-banner">🟢 LIVE PRODUCTION MODE ACTIVE</div>'}
        
        <div class="header"><h1>🚀 Secret_Alerts v4.1</h1></div>
        
        <div class="status-card">
            <h2>📊 System Status</h2>
            <p><strong>Market Mode:</strong> {mode}</p>
            <p><strong>Status:</strong> {status}</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>⚙️ System Controls</h3>
                <a href="/test/force-alert" class="btn btn-alert">🚨 Force Active Alert</a>
                {'<a href="/disable_test_mode" class="btn btn-toggle-prod">Switch to Production</a>' if TEST_MODE else '<a href="/enable_test_mode" class="btn btn-toggle-test">Switch to Test Mode</a>'}
            </div>
        </div>
    </div>
</body>
</html>"""
                self._send_html_response(html)

            def _send_simple_response(self, title, content):
                html = f"""<!DOCTYPE html><html><head><title>{title}</title><style>body{{background:#1a1a2e;color:#fff;font-family:sans-serif;padding:3rem;}} .container{{max-width:800px;margin:auto;background:#16213e;padding:2rem;border-radius:12px;}} a{{color:#00d9ff;}} pre{{background:#0a0e27;padding:1rem;border-radius:8px;text-align:left;}}</style></head><body><div class="container"><h1>{title}</h1><div>{content}</div><br><a href='/'>← Back to Dashboard</a></div></body></html>"""
                self._send_html_response(html)

            def _send_html_response(self, html):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
        
        handler = lambda *args, **kwargs: DebugDashboardHandler(*args, trading_system=self, **kwargs)
        server = HTTPServer(('', port), handler)
        print(f"🌐 Web server starting on port {port}")
        server.serve_forever()
    
    def start_monitoring_loop(self):
        """Enhanced monitoring loop that respects the global TEST_MODE flag."""
        print("🔍 DEBUG: Starting monitoring loop...")
        
        while self.running:
            try:
                global TEST_MODE
                should_monitor = self.market_scheduler.should_monitor()
                interval = self.market_scheduler.get_check_interval()
                mode = self.market_scheduler.get_current_mode()

                if TEST_MODE:
                    should_monitor = True
                    interval = 15
                    mode = "TEST RUSH HOUR"
                    self.config.cboe_url = "http://talkhotel.com/BatsCircuitBreakers2025_test.csv"
                else:
                    self.config.cboe_url = self.live_cboe_url

                if should_monitor:
                    print(f"\n🔍 DEBUG: Check - {mode} mode")
                    self.cboe_monitor.check()
                else:
                    print(f"💤 {mode} - Skipping check")
                
                print(f"😴 Sleeping for {interval} seconds...\n")
                time.sleep(interval)
                
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                time.sleep(60)

    def run(self):
        self.running = True
        monitor_thread = threading.Thread(target=self.start_monitoring_loop, daemon=True)
        monitor_thread.start()
        self.start_web_server()

def main():
    try:
        system = DebugTradingSystemOrchestrator()
        system.run()
    except Exception as e:
        print(f"\n❌ CRITICAL: Failed to start system: {e}")

if __name__ == "__main__":
    main()
