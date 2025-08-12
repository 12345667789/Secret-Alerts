"""
Enhanced web dashboard for the Secret_Alerts trading intelligence system
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date
import pytz
from urllib.parse import parse_qs
import pandas as pd

from config.version import VERSION, BUILD_DATE, ARCHITECTURE
from utils.logger import logger

# Global reference to the trading system (set by main.py)
trading_system = None

class DashboardHandler(BaseHTTPRequestHandler):
    """Enhanced web dashboard request handler"""
    
    def do_GET(self):
        path = self.path.split('?')[0]
        
        if path == '/':
            self.serve_dashboard()
        elif path == '/test-discord':
            self.test_discord()
        elif path == '/force-check':
            self.force_check()
        elif path == '/status':
            self.serve_status()
        elif path == '/api/logs':
            self.serve_logs_api()
        elif path == '/api/todays-alerts':
            self.serve_todays_alerts_api()
        elif path == '/time-travel':
            self.serve_time_travel_page()
        else:
            self.send_404()
    
    def do_POST(self):
        """Handle POST requests for time travel testing"""
        path = self.path.split('?')[0]
        
        if path == '/time-travel-test':
            self.handle_time_travel_test()
        else:
            self.send_404()

    def handle_time_travel_test(self):
        """Handle time travel test requests"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # Parse form data
            form_data = parse_qs(post_data.decode('utf-8'))
            test_time = form_data.get('test_time', [''])[0]
            
            if not test_time:
                self.send_error_response("No test time provided")
                return
            
            # Import the time travel tester
            from testing.time_travel_tester import run_time_travel_test
            
            # Run the test
            vip_symbols = trading_system.config.vip_tickers if trading_system else ['TSLA', 'AAPL', 'GOOG', 'NVDA']
            results = run_time_travel_test(test_time, vip_symbols)
            
            # Send results page
            self.send_time_travel_results(results)
            
        except Exception as e:
            logger.error(f"Time travel test error: {e}")
            self.send_error_response(f"Test failed: {str(e)}")

    def serve_time_travel_page(self):
        """Serve the time travel testing interface"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Get suggested test times
        try:
            from testing.time_travel_tester import get_test_suggestions
            vip_symbols = trading_system.config.vip_tickers if trading_system else ['TSLA', 'AAPL', 'GOOG', 'NVDA']
            suggestions = get_test_suggestions(vip_symbols)
        except Exception as e:
            logger.error(f"Error getting test suggestions: {e}")
            suggestions = []
        
        suggestions_html = ""
        if suggestions:
            for suggestion in suggestions:
                vip_badge = "⭐ VIP" if suggestion.get('is_vip') else ""
                suggestions_html += f"""
                <div class="suggestion-item" onclick="fillTestTime('{suggestion['test_time']}')">
                    <strong>{suggestion['symbol']} {vip_badge}</strong><br>
                    <small>{suggestion['description']}</small><br>
                    <code>{suggestion['test_time']}</code>
                </div>
                """
        else:
            suggestions_html = '<p style="color: #666;">Loading suggestions...</p>'
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Time Travel Alert Testing - Secret_Alerts v{VERSION}</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
                .container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }}
                .section {{ background: white; padding: 20px; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .suggestion-item {{ 
                    background: #f9f9f9; margin: 10px 0; padding: 15px; border-radius: 6px; 
                    border: 1px solid #ccc; cursor: pointer; transition: all 0.2s;
                }}
                .suggestion-item:hover {{ background: #e8f4f8; border-color: #2196F3; }}
                .form-group {{ margin: 15px 0; }}
                .form-group label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                .form-group input {{ width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }}
                .btn {{ 
                    background: #2196F3; color: white; padding: 12px 24px; border: none; 
                    border-radius: 6px; cursor: pointer; font-size: 16px; 
                }}
                .btn:hover {{ background: #1976D2; }}
                .header {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; 
                }}
                .info {{ background: #e3f2fd; padding: 15px; border-radius: 6px; margin-bottom: 20px; }}
                .back-link {{ text-align: center; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🕐 Time Travel Alert Testing</h1>
                <p>Test your alert detection by simulating historical state changes</p>
            </div>
            
            <div class="info">
                <strong>How it works:</strong> Select a time when an alert was triggered. The system will simulate 
                what the data looked like before that time, then show what alerts would have been generated.
            </div>
            
            <div class="container">
                <div class="section">
                    <h2>🎯 Manual Time Test</h2>
                    <form method="post" action="/time-travel-test">
                        <div class="form-group">
                            <label for="test_time">Test Time (YYYY-MM-DD HH:MM:SS):</label>
                            <input type="text" id="test_time" name="test_time" 
                                   placeholder="2025-08-12 09:35:00" required>
                        </div>
                        <button type="submit" class="btn">🚀 Run Time Travel Test</button>
                    </form>
                    
                    <p><strong>Examples:</strong></p>
                    <ul>
                        <li><code>2025-08-12 09:33:00</code> - Test CRWV alerts</li>
                        <li><code>2025-08-11 12:09:00</code> - Test TESLA alert</li>
                        <li><code>2025-08-11 09:44:00</code> - Test ETHER alert</li>
                    </ul>
                </div>
                
                <div class="section">
                    <h2>💡 Suggested Test Times</h2>
                    <p>Based on recent CBOE data:</p>
                    <div id="suggestions">
                        {suggestions_html}
                    </div>
                </div>
            </div>
            
            <div class="back-link">
                <a href="/" style="color: #2196F3; text-decoration: none; font-size: 16px;">← Back to Dashboard</a>
            </div>
            
            <script>
                function fillTestTime(timeStr) {{
                    document.getElementById('test_time').value = timeStr;
                }}
            </script>
        </body>
        </html>
        """
        
        self.wfile.write(html.encode())

    def send_time_travel_results(self, results):
        """Send time travel test results"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        if 'error' in results:
            html = f"""
            <html><body style="font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px;">
            <h1 style="color: #f44336;">❌ Time Travel Test Failed</h1>
            <p>Error: {results['error']}</p>
            <p><a href="/time-travel" style="color: #2196F3;">← Back to Time Travel Testing</a></p>
            </body></html>
            """
            self.wfile.write(html.encode())
            return
        
        # Format the results for display
        before_alerts_html = ""
        for alert in results['before_state']['sample_alerts']:
            vip_badge = "⭐" if alert['is_vip'] else ""
            before_alerts_html += f"<li>{vip_badge} <strong>{alert['symbol']}</strong> - {alert['security_name']} (Started {alert['trigger_time']})</li>"
        
        after_alerts_html = ""
        for alert in results['after_state']['sample_alerts']:
            vip_badge = "⭐" if alert['is_vip'] else ""
            after_alerts_html += f"<li>{vip_badge} <strong>{alert['symbol']}</strong> - {alert['security_name']} (Started {alert['trigger_time']})</li>"
        
        new_alerts_html = ""
        for alert in results['detected_changes']['new_alert_details']:
            vip_badge = "⭐ VIP" if alert['is_vip'] else ""
            new_alerts_html += f"<li>{vip_badge} <strong>{alert['symbol']}</strong> - {alert['security_name']} (Triggered {alert['trigger_time']})</li>"
        
        ended_alerts_html = ""
        for alert in results['detected_changes']['ended_alert_details']:
            vip_badge = "⭐ VIP" if alert['is_vip'] else ""
            ended_alerts_html += f"<li>{vip_badge} <strong>{alert['symbol']}</strong> - {alert['security_name']} (Ended {alert['end_time']})</li>"
        
        discord_preview_html = ""
        if results.get('discord_preview'):
            discord_preview_html = f"""
            <div style="background: #36393f; color: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h3 style="color: #7289da; margin-top: 0;">📱 Discord Alert Preview</h3>
                <div style="border-left: 4px solid #ffa500; padding-left: 15px; background: #2f3136; border-radius: 4px; padding: 15px;">
                    <strong>{results['discord_preview']['title']}</strong><br><br>
                    <pre style="white-space: pre-wrap; margin: 0; font-family: Arial;">{results['discord_preview']['message']}</pre>
                </div>
            </div>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Time Travel Test Results - Secret_Alerts v{VERSION}</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
                .results-container {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }}
                .result-section {{ background: white; padding: 20px; border-radius: 8px; border: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .summary {{ background: #e8f5e8; padding: 20px; border-radius: 8px; margin-bottom: 30px; text-align: center; }}
                .changes {{ background: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                ul {{ padding-left: 20px; }}
                li {{ margin: 8px 0; }}
                .metric {{ display: inline-block; margin: 0 20px; }}
                .success {{ color: #28a745; font-weight: bold; }}
                .info {{ color: #17a2b8; font-weight: bold; }}
                .header {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; text-align: center; 
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🕐 Time Travel Test Results</h1>
            </div>
            
            <div class="summary">
                <h2>Simulation for {results['simulation_time']}</h2>
                <div>
                    <span class="metric">📊 <strong>Changes Detected:</strong> 
                        <span class="success">{results['detected_changes']['new_alerts']} New</span>, 
                        <span class="info">{results['detected_changes']['ended_alerts']} Ended</span>
                    </span>
                </div>
            </div>
            
            {discord_preview_html}
            
            <div class="results-container">
                <div class="result-section">
                    <h3>⏪ Before State</h3>
                    <p><strong>Total Alerts:</strong> {results['before_state']['total_alerts']}</p>
                    <p><strong>Open Alerts:</strong> {results['before_state']['open_alerts']}</p>
                    <h4>Sample Open Alerts:</h4>
                    <ul>
                        {before_alerts_html if before_alerts_html else '<li>No open alerts</li>'}
                    </ul>
                </div>
                
                <div class="result-section">
                    <h3>⏩ After State</h3>
                    <p><strong>Total Alerts:</strong> {results['after_state']['total_alerts']}</p>
                    <p><strong>Open Alerts:</strong> {results['after_state']['open_alerts']}</p>
                    <h4>Sample Open Alerts:</h4>
                    <ul>
                        {after_alerts_html if after_alerts_html else '<li>No open alerts</li>'}
                    </ul>
                </div>
            </div>
            
            <div class="changes">
                <h3>🔍 Detected Changes</h3>
                
                <h4>🆕 New Alerts ({results['detected_changes']['new_alerts']}):</h4>
                <ul>
                    {new_alerts_html if new_alerts_html else '<li>No new alerts detected</li>'}
                </ul>
                
                <h4>✅ Ended Alerts ({results['detected_changes']['ended_alerts']}):</h4>
                <ul>
                    {ended_alerts_html if ended_alerts_html else '<li>No ended alerts detected</li>'}
                </ul>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="/time-travel" style="color: #2196F3; text-decoration: none; margin-right: 20px; font-size: 16px;">🔄 Run Another Test</a>
                <a href="/" style="color: #2196F3; text-decoration: none; font-size: 16px;">← Back to Dashboard</a>
            </div>
        </body>
        </html>
        """
        
        self.wfile.write(html.encode())

    def send_error_response(self, error_msg):
        """Send error response"""
        self.send_response(500)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        html = f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
        <h1 style="color: #f44336;">❌ Error</h1>
        <p>{error_msg}</p>
        <p><a href="/time-travel" style="color: #2196F3;">← Back to Time Travel Testing</a></p>
        </body></html>
        """
        self.wfile.write(html.encode())
    
    def serve_dashboard(self):
        """Serve the enhanced dashboard"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Get VIP tickers from config
        vip_list = ', '.join(trading_system.config.vip_tickers) if trading_system else "TSLA, NVDA, AAPL, GME, AMC"
        discord_status = "✅ Configured" if trading_system and trading_system.config.discord_webhook else "❌ Not configured"
        
        dashboard_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Secret_Alerts v{VERSION}</title>
            <meta charset="utf-8">
            <style>
                body {{ 
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                    max-width: 1400px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; 
                }}
                .module {{ 
                    background: white; border: 1px solid #ddd; margin: 15px 0; padding: 20px; 
                    border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
                }}
                .button {{ 
                    background-color: #4CAF50; border: none; color: white; padding: 12px 24px; 
                    text-decoration: none; display: inline-block; margin: 8px 4px; 
                    border-radius: 6px; cursor: pointer; font-size: 14px; transition: all 0.3s; 
                }}
                .button:hover {{ background-color: #45a049; transform: translateY(-1px); }}
                .test-btn {{ background-color: #2196F3; }}
                .test-btn:hover {{ background-color: #1976D2; }}
                .force-btn {{ background-color: #f44336; }}
                .force-btn:hover {{ background-color: #d32f2f; }}
                .time-travel-btn {{ background-color: #9c27b0; }}
                .time-travel-btn:hover {{ background-color: #7b1fa2; }}
                .status-good {{ color: #4CAF50; font-weight: bold; }}
                .status-bad {{ color: #f44336; font-weight: bold; }}
                .version {{ font-size: 12px; color: #666; }}
                .header {{ 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; 
                }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 15px; }}
                .metric {{ background: #f8f9fa; padding: 10px; border-radius: 4px; margin: 5px 0; }}
                
                /* Enhanced Log Viewer Styles */
                .log-container {{
                    height: 400px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: #1a1a1a;
                    color: #00ff00;
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    overflow: hidden;
                    position: relative;
                }}
                .log-header {{
                    background: #333;
                    color: white;
                    padding: 8px 12px;
                    border-bottom: 1px solid #555;
                    font-weight: bold;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }}
                .log-content {{
                    height: calc(100% - 40px);
                    overflow-y: auto;
                    padding: 10px;
                    line-height: 1.4;
                }}
                .log-line {{
                    margin: 2px 0;
                    word-wrap: break-word;
                }}
                .log-info {{ color: #00ff00; }}
                .log-warning {{ color: #ffaa00; }}
                .log-error {{ color: #ff4444; }}
                .log-debug {{ color: #888; }}
                
                /* Today's Alerts Styles */
                .alerts-container {{
                    max-height: 400px;
                    overflow-y: auto;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    background: #f9f9f9;
                }}
                .alert-item {{
                    padding: 10px;
                    border-bottom: 1px solid #eee;
                    transition: background-color 0.2s;
                }}
                .alert-item:hover {{
                    background-color: #f0f0f0;
                }}
                .alert-item.vip {{
                    border-left: 4px solid #ffd700;
                    background-color: #fffbf0;
                }}
                .alert-time {{
                    font-size: 11px;
                    color: #666;
                    float: right;
                }}
                .alert-symbol {{
                    font-weight: bold;
                    color: #2196F3;
                }}
                .alert-status {{
                    display: inline-block;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 10px;
                    font-weight: bold;
                    margin-left: 5px;
                }}
                .alert-status.started {{
                    background: #ffebee;
                    color: #c62828;
                }}
                .alert-status.ended {{
                    background: #e8f5e8;
                    color: #2e7d32;
                }}
                
                /* Refresh Controls */
                .refresh-controls {{
                    display: flex;
                    gap: 10px;
                    align-items: center;
                }}
                .auto-refresh {{
                    font-size: 12px;
                    color: #666;
                }}
                .refresh-btn {{
                    background: #2196F3;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 3px;
                    cursor: pointer;
                    font-size: 11px;
                }}
                .refresh-btn:hover {{
                    background: #1976D2;
                }}
                
                /* Layout for larger screens */
                @media (min-width: 1200px) {{
                    .main-grid {{
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 20px;
                    }}
                    .left-column, .right-column {{
                        display: flex;
                        flex-direction: column;
                        gap: 15px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚀 Secret_Alerts Trading Intelligence v{VERSION}</h1>
                <p><strong>Architecture:</strong> {ARCHITECTURE} | <strong>Build:</strong> {BUILD_DATE}</p>
                <div style="margin-top: 10px;">
                    <span id="live-time" style="font-size: 14px;"></span>
                    <span style="margin-left: 20px; font-size: 14px;">Status: <span class="status-good">● LIVE</span></span>
                </div>
            </div>
            
            <div class="main-grid">
                <div class="left-column">
                    <!-- System Status -->
                    <div class="module">
                        <h2>📊 System Status</h2>
                        <div class="metric">
                            <strong>Status:</strong> <span class="status-good">Active & Monitoring</span>
                        </div>
                        <div class="metric">
                            <strong>Version:</strong> {VERSION} (Built: {BUILD_DATE})
                        </div>
                        <div class="metric">
                            <strong>Last Check:</strong> <span id="last-check-time">Loading...</span>
                        </div>
                        <div class="metric">
                            <strong>Discord Alerts:</strong> {discord_status}
                        </div>
                        <div class="metric">
                            <strong>Today's Date:</strong> {datetime.now().strftime('%Y-%m-%d %A')}
                        </div>
                    </div>
                    
                    <!-- Test Functions -->
                    <div class="module">
                        <h2>🧪 Test Functions</h2>
                        <button onclick="testDiscord()" class="button test-btn">📱 Test Discord Alert</button>
                        <button onclick="forceCheck()" class="button force-btn">🔍 Force CBOE Check</button>
                        <a href="/time-travel" class="button time-travel-btn">🕐 Time Travel Test</a>
                        <a href="/status" class="button">📊 API Status</a>
                    </div>
                    
                    <!-- VIP Tickers -->
                    <div class="module">
                        <h2>💎 VIP Tickers</h2>
                        <div class="metric">
                            <strong>Monitored:</strong> {vip_list}
                        </div>
                        <div class="metric">
                            <strong>Special Rules:</strong> Enhanced analysis, priority alerts, gold-colored notifications
                        </div>
                    </div>
                    
                    <!-- Module Status -->
                    <div class="module">
                        <h2>📈 Module Status</h2>
                        <div class="metric">✅ <strong>CBOE Monitor:</strong> Active</div>
                        <div class="metric">✅ <strong>Alert Manager:</strong> Ready</div>
                        <div class="metric">✅ <strong>VIP Manager:</strong> Loaded</div>
                        <div class="metric">✅ <strong>Event Recorder:</strong> Standby</div>
                        <div class="metric">🚧 <strong>Analyst:</strong> Framework ready</div>
                        <div class="metric">🚧 <strong>Trading:</strong> Paper mode ready</div>
                        <div class="metric">🚧 <strong>Data Collection:</strong> Framework ready</div>
                        <div class="metric">✅ <strong>Time Travel Testing:</strong> Ready</div>
                    </div>
                </div>
                
                <div class="right-column">
                    <!-- Today's Alerts -->
                    <div class="module">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                            <h2>🚨 Today's Circuit Breaker Alerts</h2>
                            <div class="refresh-controls">
                                <button onclick="refreshAlerts()" class="refresh-btn">🔄 Refresh</button>
                                <span class="auto-refresh">Auto-refresh: 30s</span>
                            </div>
                        </div>
                        <div class="alerts-container" id="todays-alerts">
                            <div style="padding: 20px; text-align: center; color: #666;">
                                Loading today's alerts...
                            </div>
                        </div>
                    </div>
                    
                    <!-- Live Log Viewer -->
                    <div class="module">
                        <div class="log-container">
                            <div class="log-header">
                                <span>📋 Live System Logs</span>
                                <div class="refresh-controls">
                                    <button onclick="refreshLogs()" class="refresh-btn">🔄 Refresh</button>
                                    <button onclick="clearLogs()" class="refresh-btn">🗑️ Clear</button>
                                    <span class="auto-refresh">Auto-refresh: 5s</span>
                                </div>
                            </div>
                            <div class="log-content" id="log-content">
                                Loading logs...
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="module">
                <p class="version">
                    <strong>Secret_Alerts v{VERSION}</strong> | 
                    Build: {BUILD_DATE} | 
                    Last updated: <span id="page-updated">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span> |
                    Professional trading intelligence platform
                </p>
            </div>
            
            <script>
                // Update live time
                function updateTime() {{
                    const now = new Date();
                    document.getElementById('live-time').textContent = now.toLocaleString('en-US', {{
                        timeZone: 'America/Chicago',
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    }}) + ' CST';
                    
                    document.getElementById('page-updated').textContent = now.toLocaleString();
                }}
                
                // Refresh logs
                function refreshLogs() {{
                    fetch('/api/logs')
                        .then(response => response.json())
                        .then(data => {{
                            const logContent = document.getElementById('log-content');
                            logContent.innerHTML = '';
                            
                            data.logs.forEach(log => {{
                                const logLine = document.createElement('div');
                                logLine.className = 'log-line';
                                
                                if (log.includes('ERROR') || log.includes('CRITICAL')) {{
                                    logLine.className += ' log-error';
                                }} else if (log.includes('WARNING')) {{
                                    logLine.className += ' log-warning';
                                }} else if (log.includes('DEBUG')) {{
                                    logLine.className += ' log-debug';
                                }} else {{
                                    logLine.className += ' log-info';
                                }}
                                
                                logLine.textContent = log;
                                logContent.appendChild(logLine);
                            }});
                            
                            // Auto-scroll to bottom
                            logContent.scrollTop = logContent.scrollHeight;
                        }})
                        .catch(error => {{
                            console.error('Error fetching logs:', error);
                            document.getElementById('log-content').innerHTML = '<div class="log-error">Error loading logs</div>';
                        }});
                }}
                
                // Refresh today's alerts
                function refreshAlerts() {{
                    fetch('/api/todays-alerts')
                        .then(response => response.json())
                        .then(data => {{
                            const alertsContainer = document.getElementById('todays-alerts');
                            alertsContainer.innerHTML = '';
                            
                            if (data.alerts.length === 0) {{
                                alertsContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">No circuit breaker alerts today</div>';
                                return;
                            }}
                            
                            data.alerts.forEach(alert => {{
                                const alertItem = document.createElement('div');
                                alertItem.className = 'alert-item' + (alert.is_vip ? ' vip' : '');
                                
                                const statusClass = alert.status === 'Started' ? 'started' : 'ended';
                                const vipIcon = alert.is_vip ? '⭐ ' : '';
                                
                                alertItem.innerHTML = `
                                    <div class="alert-time">${{alert.time}}</div>
                                    <div>
                                        <span class="alert-symbol">${{vipIcon}}${{alert.symbol}}</span>
                                        <span class="alert-status ${{statusClass}}">${{alert.status}}</span>
                                    </div>
                                    <div style="font-size: 12px; color: #666; margin-top: 4px;">
                                        ${{alert.security_name}}
                                    </div>
                                `;
                                
                                alertsContainer.appendChild(alertItem);
                            }});
                        }})
                        .catch(error => {{
                            console.error('Error fetching alerts:', error);
                            document.getElementById('todays-alerts').innerHTML = '<div style="padding: 20px; text-align: center; color: #f44336;">Error loading alerts</div>';
                        }});
                }}
                
                // Clear logs
                function clearLogs() {{
                    document.getElementById('log-content').innerHTML = '<div class="log-info">Logs cleared locally</div>';
                }}
                
                // Test Discord
                function testDiscord() {{
                    window.location.href = '/test-discord';
                }}
                
                // Force check
                function forceCheck() {{
                    window.location.href = '/force-check';
                }}
                
                // Initialize
                updateTime();
                refreshLogs();
                refreshAlerts();
                
                // Set up auto-refresh
                setInterval(updateTime, 1000);
                setInterval(refreshLogs, 5000);
                setInterval(refreshAlerts, 30000);
            </script>
        </body>
        </html>
        """
        
        self.wfile.write(dashboard_html.encode())
    
    def serve_logs_api(self):
        """Serve logs as JSON API"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Get recent logs from the logger or system
        logs = []
        if hasattr(trading_system, 'get_recent_logs'):
            logs = trading_system.get_recent_logs()
        else:
            # Fallback to some basic system info
            logs = [
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - System active and monitoring",
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - INFO - Dashboard API serving logs",
            ]
        
        response = {
            'logs': logs,
            'timestamp': datetime.now().isoformat(),
            'count': len(logs)
        }
        
        self.wfile.write(json.dumps(response).encode())
    
    def serve_todays_alerts_api(self):
        """Serve today's alerts as JSON API"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        # Get today's alerts
        alerts = []
        try:
            if hasattr(trading_system, 'get_todays_alerts'):
                alerts = trading_system.get_todays_alerts()
            else:
                # Try to get from CBOE monitor directly
                from monitors.cboe_monitor import ShortSaleMonitor
                monitor = ShortSaleMonitor()
                current_df = monitor.fetch_data()
                
                if current_df is not None and not current_df.empty:
                    # Filter for today's date
                    cst = pytz.timezone('America/Chicago')
                    today = datetime.now(cst).strftime('%Y-%m-%d')
                    
                    # Get today's triggers
                    todays_data = current_df[current_df['Trigger Date'] == today]
                    
                    vip_symbols = trading_system.config.vip_tickers if trading_system else ['TSLA', 'AAPL', 'GOOG', 'NVDA']
                    
                    for _, row in todays_data.iterrows():
                        alert = {
                            'symbol': row['Symbol'],
                            'security_name': row.get('Security Name', ''),
                            'time': f"{row['Trigger Date']} {row['Trigger Time']}",
                            'status': 'Ended' if pd.notnull(row.get('End Time')) else 'Started',
                            'is_vip': row['Symbol'] in vip_symbols
                        }
                        alerts.append(alert)
                    
                    # Sort by VIP status then time
                    alerts.sort(key=lambda x: (not x['is_vip'], x['time']), reverse=True)
        
        except Exception as e:
            logger.error(f"Error fetching today's alerts: {e}")
        
        response = {
            'alerts': alerts,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat(),
            'count': len(alerts)
        }
        
        self.wfile.write(json.dumps(response).encode())
    
    def test_discord(self):
        """Test Discord functionality"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        if not trading_system:
            response_html = "<h1>❌ Error: Trading system not initialized</h1>"
        else:
            success = trading_system.test_discord()
            if success:
                response_html = """
                <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #4CAF50;">✅ Discord Test Sent Successfully!</h1>
                <p>Check your Discord channel for the test message.</p>
                <p><a href="/" style="color: #2196F3; text-decoration: none;">← Back to Dashboard</a></p>
                <script>setTimeout(() => window.location.href = '/', 3000);</script>
                </body></html>
                """
            else:
                response_html = """
                <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #f44336;">❌ Discord Test Failed</h1>
                <p>Check your webhook URL configuration in environment variables.</p>
                <p><a href="/" style="color: #2196F3; text-decoration: none;">← Back to Dashboard</a></p>
                <script>setTimeout(() => window.location.href = '/', 5000);</script>
                </body></html>
                """
        
        self.wfile.write(response_html.encode())
    
    def force_check(self):
        """Force a CBOE check"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        if not trading_system:
            response_html = "<h1>❌ Error: Trading system not initialized</h1>"
        else:
            try:
                results = trading_system.force_cboe_check()
                response_html = f"""
                <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #4CAF50;">✅ CBOE Check Completed!</h1>
                <p><strong>Records found:</strong> {results.get('total_records', 'N/A')}</p>
                <p><strong>Keyword matches:</strong> {len(results.get('keyword_matches', []))}</p>
                <p>Manual check performed successfully. Check Discord for any alerts.</p>
                <p><a href="/" style="color: #2196F3; text-decoration: none;">← Back to Dashboard</a></p>
                <script>setTimeout(() => window.location.href = '/', 3000);</script>
                </body></html>
                """
            except Exception as e:
                response_html = f"""
                <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #f44336;">❌ CBOE Check Failed</h1>
                <p>Error: {str(e)}</p>
                <p><a href="/" style="color: #2196F3; text-decoration: none;">← Back to Dashboard</a></p>
                <script>setTimeout(() => window.location.href = '/', 5000);</script>
                </body></html>
                """
        
        self.wfile.write(response_html.encode())
    
    def serve_status(self):
        """Serve detailed status as JSON"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        status = {
            'version': VERSION,
            'build_date': BUILD_DATE,
            'architecture': ARCHITECTURE,
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'modules': {
                'cboe_monitor': 'active',
                'alert_manager': 'ready',
                'vip_manager': 'loaded',
                'event_recorder': 'standby',
                'analyst': 'framework_ready',
                'trading': 'paper_mode',
                'data_collection': 'framework_ready',
                'web_dashboard': 'active',
                'time_travel_testing': 'ready'
            },
            'configuration': {
                'check_interval': trading_system.config.check_interval if trading_system else 300,
                'discord_configured': bool(trading_system.config.discord_webhook) if trading_system else False,
                'vip_tickers_count': len(trading_system.config.vip_tickers) if trading_system else 5,
                'keywords_count': len(trading_system.config.keywords) if trading_system else 9
            }
        }
        
        self.wfile.write(json.dumps(status, indent=2).encode())
    
    def send_404(self):
        """Send 404 response"""
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        html = """
        <html><body style="font-family: Arial, sans-serif; text-align: center; margin-top: 100px;">
        <h1>404 - Page Not Found</h1>
        <p><a href="/" style="color: #2196F3; text-decoration: none;">← Back to Dashboard</a></p>
        </body></html>
        """
        self.wfile.write(html.encode())

def start_web_server(port: int):
    """Start the web server"""
    server = HTTPServer(('', port), DashboardHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logger.info(f"Enhanced web dashboard started on port {port}", "WEB")
    return server