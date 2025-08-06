"""
Web dashboard for the Secret_Alerts trading intelligence system
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from config.version import VERSION, BUILD_DATE, ARCHITECTURE
from utils.logger import logger

# Global reference to the trading system (set by main.py)
trading_system = None

class DashboardHandler(BaseHTTPRequestHandler):
    """Web dashboard request handler"""
    
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
        else:
            self.send_404()
    
    def serve_dashboard(self):
        """Serve the main dashboard"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Get VIP tickers from config
        vip_list = ', '.join(trading_system.config.vip_tickers) if trading_system else "TSLA, NVDA, AAPL, GME, AMC"
        discord_status = "✅ Configured" if trading_system and trading_system.config.discord_webhook else "❌ Not configured"
        
        dashboard_html = f"""
        <html>
        <head>
            <title>Secret_Alerts v{VERSION}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                       max-width: 1200px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
                .module {{ background: white; border: 1px solid #ddd; margin: 15px 0; padding: 20px; 
                          border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .button {{ background-color: #4CAF50; border: none; color: white; padding: 12px 24px; 
                          text-decoration: none; display: inline-block; margin: 8px 4px; 
                          border-radius: 6px; cursor: pointer; font-size: 14px; transition: all 0.3s; }}
                .button:hover {{ background-color: #45a049; transform: translateY(-1px); }}
                .test-btn {{ background-color: #2196F3; }}
                .test-btn:hover {{ background-color: #1976D2; }}
                .force-btn {{ background-color: #f44336; }}
                .force-btn:hover {{ background-color: #d32f2f; }}
                .status-good {{ color: #4CAF50; font-weight: bold; }}
                .status-bad {{ color: #f44336; font-weight: bold; }}
                .version {{ font-size: 12px; color: #666; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }}
                .metric {{ background: #f8f9fa; padding: 10px; border-radius: 4px; margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚀 Secret_Alerts Trading Intelligence v{VERSION}</h1>
                <p><strong>Architecture:</strong> {ARCHITECTURE} | <strong>Build:</strong> {BUILD_DATE}</p>
            </div>
            
            <div class="grid">
                <div class="module">
                    <h2>📊 System Status</h2>
                    <div class="metric">
                        <strong>Status:</strong> <span class="status-good">Active & Monitoring</span>
                    </div>
                    <div class="metric">
                        <strong>Version:</strong> {VERSION} (Built: {BUILD_DATE})
                    </div>
                    <div class="metric">
                        <strong>Last Check:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S CST')}
                    </div>
                    <div class="metric">
                        <strong>Discord Alerts:</strong> {discord_status}
                    </div>
                </div>
                
                <div class="module">
                    <h2>🧪 Test Functions</h2>
                    <a href="/test-discord" class="button test-btn">📱 Test Discord Alert</a>
                    <a href="/force-check" class="button force-btn">🔍 Force CBOE Check</a>
                    <a href="/status" class="button">📊 API Status</a>
                </div>
                
                <div class="module">
                    <h2>💎 VIP Tickers</h2>
                    <div class="metric">
                        <strong>Monitored:</strong> {vip_list}
                    </div>
                    <div class="metric">
                        <strong>Special Rules:</strong> Enhanced analysis, priority alerts, gold-colored notifications
                    </div>
                </div>
                
                <div class="module">
                    <h2>📈 Module Status</h2>
                    <div class="metric">✅ <strong>CBOE Monitor:</strong> Active</div>
                    <div class="metric">✅ <strong>Alert Manager:</strong> Ready</div>
                    <div class="metric">✅ <strong>VIP Manager:</strong> Loaded</div>
                    <div class="metric">✅ <strong>Event Recorder:</strong> Standby</div>
                    <div class="metric">🚧 <strong>Analyst:</strong> Framework ready</div>
                    <div class="metric">🚧 <strong>Trading:</strong> Paper mode ready</div>
                    <div class="metric">🚧 <strong>Data Collection:</strong> Framework ready</div>
                </div>
                
                <div class="module">
                    <h2>🔍 Intelligence Sources</h2>
                    <div class="metric">
                        <strong>CBOE Monitor:</strong> Circuit breakers, short sale data
                    </div>
                    <div class="metric">
                        <strong>Framework Ready:</strong> Options flow, earnings, FDA approvals
                    </div>
                    <div class="metric">
                        <strong>Future Sources:</strong> Crypto, insider trading, social sentiment
                    </div>
                </div>
                
                <div class="module">
                    <h2>🏗️ System Architecture</h2>
                    <div class="metric">
                        <strong>Design:</strong> Modular, multi-source intelligence
                    </div>
                    <div class="metric">
                        <strong>Deployment:</strong> Google Cloud Run
                    </div>
                    <div class="metric">
                        <strong>Scalability:</strong> Add new data sources as modules
                    </div>
                </div>
            </div>
            
            <div class="module">
                <p class="version">
                    <strong>Secret_Alerts v{VERSION}</strong> | 
                    Build: {BUILD_DATE} | 
                    Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
                    Professional trading intelligence platform
                </p>
            </div>
        </body>
        </html>
        """
        
        self.wfile.write(dashboard_html.encode())
    
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
                </body></html>
                """
            else:
                response_html = """
                <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #f44336;">❌ Discord Test Failed</h1>
                <p>Check your webhook URL configuration in environment variables.</p>
                <p><a href="/" style="color: #2196F3; text-decoration: none;">← Back to Dashboard</a></p>
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
                </body></html>
                """
            except Exception as e:
                response_html = f"""
                <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1 style="color: #f44336;">❌ CBOE Check Failed</h1>
                <p>Error: {str(e)}</p>
                <p><a href="/" style="color: #2196F3; text-decoration: none;">← Back to Dashboard</a></p>
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
                'web_dashboard': 'active'
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
    logger.info(f"Web dashboard started on port {port}", "WEB")
    return server
