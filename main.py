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

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Track module import status
MODULE_STATUS = {
    'config.settings': False,
    'config.version': False,
    'monitors.cboe_monitor': False,
    'alerts.alert_manager': False,
    'alerts.discord_client': False,
    'utils.logger': False,
    'utils.market_schedule': False
}

print("🔍 DEBUG: Starting module imports...")

try:
    from config.settings import get_config
    MODULE_STATUS['config.settings'] = True
    print("✅ config.settings imported successfully")
except ImportError as e:
    print(f"❌ config.settings failed: {e}")

try:
    from config.version import VERSION, BUILD_DATE
    MODULE_STATUS['config.version'] = True
    print("✅ config.version imported successfully")
except ImportError as e:
    print(f"❌ config.version failed: {e}")
    VERSION, BUILD_DATE = "4.1-debug", "2025-08-06"

try:
    from monitors.cboe_monitor import CBOEMonitor
    MODULE_STATUS['monitors.cboe_monitor'] = True
    print("✅ monitors.cboe_monitor imported successfully")
except ImportError as e:
    print(f"❌ monitors.cboe_monitor failed: {e}")

try:
    from alerts.alert_manager import AlertManager
    MODULE_STATUS['alerts.alert_manager'] = True
    print("✅ alerts.alert_manager imported successfully")
except ImportError as e:
    print(f"❌ alerts.alert_manager failed: {e}")

try:
    from alerts.discord_client import DiscordClient
    MODULE_STATUS['alerts.discord_client'] = True
    print("✅ alerts.discord_client imported successfully")
except ImportError as e:
    print(f"❌ alerts.discord_client failed: {e}")

try:
    from utils.logger import logger
    MODULE_STATUS['utils.logger'] = True
    print("✅ utils.logger imported successfully")
except ImportError as e:
    print(f"❌ utils.logger failed: {e}")

try:
    from utils.market_schedule import MarketScheduler
    MODULE_STATUS['utils.market_schedule'] = True
    print("✅ utils.market_schedule imported successfully")
except ImportError as e:
    print(f"❌ utils.market_schedule failed: {e}")

# Check if critical modules failed
failed_modules = [name for name, status in MODULE_STATUS.items() if not status]
if failed_modules:
    print(f"\\n❌ CRITICAL: {len(failed_modules)} modules failed to import:")
    for module in failed_modules:
        print(f"   - {module}")
    print("\\n🔧 Please fix these modules before continuing.")
    sys.exit(1)

print(f"\\n🎉 All {len(MODULE_STATUS)} modules imported successfully!\\n")

class DebugTradingSystemOrchestrator:
    """Main orchestrator with comprehensive debugging and health checks"""
    
    def __init__(self):
        print("🔍 DEBUG: Initializing TradingSystemOrchestrator...")
        
        self.system_health = {
            'config_loaded': False,
            'discord_client_ready': False,
            'alert_manager_ready': False,
            'cboe_monitor_ready': False,
            'market_scheduler_ready': False,
            'startup_time': datetime.now().isoformat()
        }
        
        self.running = False
        self.last_cboe_check = None
        self.total_checks = 0
        self.total_alerts_sent = 0
        
        try:
            # Initialize configuration
            print("🔍 DEBUG: Loading configuration...")
            self.config = get_config()
            self.system_health['config_loaded'] = True
            print(f"✅ Config loaded - Discord webhook: {'✅ Set' if self.config.discord_webhook else '❌ Missing'}")
            print(f"✅ Config loaded - VIP tickers: {len(self.config.vip_tickers)}")
            print(f"✅ Config loaded - Keywords: {len(self.config.keywords)}")
            
            # Initialize Discord client
            print("🔍 DEBUG: Initializing Discord client...")
            self.discord = DiscordClient(self.config.discord_webhook)
            self.system_health['discord_client_ready'] = True
            print(f"✅ Discord client ready - Enabled: {self.discord.enabled}")
            
            # Initialize Alert Manager
            print("🔍 DEBUG: Initializing Alert Manager...")
            self.alert_manager = AlertManager(self.config, self.discord)
            self.system_health['alert_manager_ready'] = True
            print("✅ Alert Manager ready")
            
            # Initialize CBOE Monitor
            print("🔍 DEBUG: Initializing CBOE Monitor...")
            self.cboe_monitor = CBOEMonitor(self.config, self.alert_manager)
            self.system_health['cboe_monitor_ready'] = True
            print(f"✅ CBOE Monitor ready - URL: {self.config.cboe_url}")
            
            # Initialize Market Scheduler
            print("🔍 DEBUG: Initializing Market Scheduler...")
            self.market_scheduler = MarketScheduler(self.config)
            self.system_health['market_scheduler_ready'] = True
            mode, status = self.market_scheduler.get_current_status()
            print(f"✅ Market Scheduler ready - Current mode: {mode}")
            
            print("\\n🎉 All modules initialized successfully!\\n")
            
        except Exception as e:
            print(f"❌ CRITICAL: Failed to initialize system: {e}")
            print(f"🔍 DEBUG: Exception details:\\n{traceback.format_exc()}")
            sys.exit(1)
    
    def run_system_diagnostics(self) -> dict:
        """Run comprehensive system diagnostics"""
        print("🔍 DEBUG: Running system diagnostics...")
        
        diagnostics = {
            'timestamp': datetime.now().isoformat(),
            'module_imports': MODULE_STATUS.copy(),
            'system_health': self.system_health.copy(),
            'tests': {}
        }
        
        # Test 1: Config validation
        try:
            assert self.config.cboe_url.startswith('https://'), "CBOE URL should use HTTPS"
            assert len(self.config.keywords) > 0, "Keywords list should not be empty"
            assert len(self.config.vip_tickers) > 0, "VIP tickers list should not be empty"
            diagnostics['tests']['config_validation'] = {'status': 'PASS', 'details': 'All config checks passed'}
            print("✅ Config validation: PASS")
        except Exception as e:
            diagnostics['tests']['config_validation'] = {'status': 'FAIL', 'error': str(e)}
            print(f"❌ Config validation: FAIL - {e}")
        
        # Test 2: Discord client test
        try:
            if self.config.discord_webhook:
                # Test Discord webhook format
                assert self.config.discord_webhook.startswith('https://discord.com/api/webhooks/'), "Invalid Discord webhook format"
                diagnostics['tests']['discord_webhook'] = {'status': 'PASS', 'details': 'Discord webhook format valid'}
                print("✅ Discord webhook: PASS")
            else:
                diagnostics['tests']['discord_webhook'] = {'status': 'SKIP', 'details': 'No Discord webhook configured'}
                print("⚠️ Discord webhook: SKIP - No webhook configured")
        except Exception as e:
            diagnostics['tests']['discord_webhook'] = {'status': 'FAIL', 'error': str(e)}
            print(f"❌ Discord webhook: FAIL - {e}")
        
        # Test 3: Market scheduler test
        try:
            mode = self.market_scheduler.get_current_mode()
            should_monitor = self.market_scheduler.should_monitor()
            interval = self.market_scheduler.get_check_interval()
            
            assert mode in ['RUSH_HOUR', 'NORMAL_HOURS', 'PRE_MARKET', 'AFTER_HOURS', 'CLOSED'], f"Invalid market mode: {mode}"
            assert isinstance(should_monitor, bool), "should_monitor should return boolean"
            assert interval > 0, "Check interval should be positive"
            
            diagnostics['tests']['market_scheduler'] = {
                'status': 'PASS', 
                'details': f"Mode: {mode}, Should monitor: {should_monitor}, Interval: {interval}s"
            }
            print(f"✅ Market scheduler: PASS - {mode}, monitoring: {should_monitor}")
        except Exception as e:
            diagnostics['tests']['market_scheduler'] = {'status': 'FAIL', 'error': str(e)}
            print(f"❌ Market scheduler: FAIL - {e}")
        
        # Test 4: CBOE URL connectivity test
        try:
            import requests
            response = requests.head(self.config.cboe_url, timeout=10)
            if response.status_code == 200:
                diagnostics['tests']['cboe_connectivity'] = {'status': 'PASS', 'details': f'CBOE URL accessible (HTTP {response.status_code})'}
                print("✅ CBOE connectivity: PASS")
            else:
                diagnostics['tests']['cboe_connectivity'] = {'status': 'WARN', 'details': f'CBOE URL returned HTTP {response.status_code}'}
                print(f"⚠️ CBOE connectivity: WARN - HTTP {response.status_code}")
        except Exception as e:
            diagnostics['tests']['cboe_connectivity'] = {'status': 'FAIL', 'error': str(e)}
            print(f"❌ CBOE connectivity: FAIL - {e}")
        
        return diagnostics
    
    def test_cboe_download(self) -> dict:
        """Test CBOE data download"""
        print("🔍 DEBUG: Testing CBOE data download...")
        
        try:
            df = self.cboe_monitor.download_csv()
            if df is not None:
                matches, vip_matches = self.cboe_monitor.find_keyword_matches(df)
                
                test_result = {
                    'status': 'SUCCESS',
                    'total_rows': len(df),
                    'columns': list(df.columns),
                    'matches_found': len(matches),
                    'vip_matches_found': len(vip_matches),
                    'keywords_matched': matches,
                    'vip_keywords_matched': vip_matches
                }
                
                print(f"✅ CBOE download: SUCCESS - {len(df)} rows, {len(matches)} matches ({len(vip_matches)} VIP)")
                if vip_matches:
                    print(f"🔥 VIP matches: {', '.join(vip_matches)}")
                if matches:
                    print(f"📊 All matches: {', '.join(matches)}")
                
                return test_result
            else:
                return {'status': 'FAIL', 'error': 'Failed to download CSV data'}
        except Exception as e:
            print(f"❌ CBOE download: FAIL - {e}")
            return {'status': 'FAIL', 'error': str(e), 'traceback': traceback.format_exc()}
    
    def test_discord_alert(self) -> dict:
        """Test Discord alert functionality"""
        print("🔍 DEBUG: Testing Discord alert...")
        
        try:
            test_msg = f"🧪 **DEBUG TEST - Secret_Alerts v{VERSION}**\\n\\n"
            test_msg += f"✅ **All modules loaded successfully**\\n"
            test_msg += f"📊 **System Status:** All {len(MODULE_STATUS)} modules operational\\n"
            test_msg += f"⏰ **Test Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n"
            test_msg += f"🎯 **Monitoring:** {len(self.config.keywords)} keywords, {len(self.config.vip_tickers)} VIP tickers\\n\\n"
            test_msg += f"*Debug mode: System diagnostics complete!*"
            
            success = self.discord.send_alert("🧪 DEBUG: System Test", test_msg, 0x00FF00)
            
            if success:
                print("✅ Discord test: SUCCESS")
                return {'status': 'SUCCESS', 'message': 'Discord alert sent successfully'}
            else:
                print("❌ Discord test: FAIL - Alert not sent")
                return {'status': 'FAIL', 'error': 'Discord alert failed to send'}
                
        except Exception as e:
            print(f"❌ Discord test: FAIL - {e}")
            return {'status': 'FAIL', 'error': str(e)}
    
    def start_monitoring_loop(self):
        """Enhanced monitoring loop with detailed logging"""
        print("🔍 DEBUG: Starting monitoring loop...")
        
        # Send startup notification
        self._send_startup_alert()
        
        while self.running:
            try:
                self.total_checks += 1
                check_start_time = datetime.now()
                
                # Check if we should monitor now
                if self.market_scheduler.should_monitor():
                    mode = self.market_scheduler.get_current_mode()
                    print(f"\\n🔍 DEBUG: Check #{self.total_checks} - {mode} mode at {check_start_time.strftime('%H:%M:%S')}")
                    
                    # Perform CBOE check
                    results = self.cboe_monitor.check()
                    self.last_cboe_check = datetime.now().isoformat()
                    
                    if results.get('error'):
                        print(f"❌ CBOE check failed: {results['error']}")
                    else:
                        matches = results.get('matches', 0)
                        vip_matches = results.get('vip_matches', 0)
                        total_rows = results.get('total_rows', 0)
                        
                        print(f"📊 CBOE check results: {total_rows} rows, {matches} matches ({vip_matches} VIP)")
                        
                        if vip_matches > 0:
                            print(f"🔥 VIP matches: {results.get('vip_keywords_found', [])}")
                            self.total_alerts_sent += 1
                        elif matches > 0:
                            print(f"📊 Standard matches: {results.get('keywords_found', [])}")
                            self.total_alerts_sent += 1
                        else:
                            print("✅ No matches found")
                    
                    check_duration = (datetime.now() - check_start_time).total_seconds()
                    print(f"⏱️ Check completed in {check_duration:.2f}s")
                    
                else:
                    mode = self.market_scheduler.get_current_mode()
                    print(f"💤 {mode} - Skipping check #{self.total_checks}")
                
                # Sleep for appropriate interval
                interval = self.market_scheduler.get_check_interval()
                print(f"😴 Sleeping for {interval} seconds...\\n")
                time.sleep(interval)
                
            except Exception as e:
                print(f"❌ Error in monitoring loop: {e}")
                print(f"🔍 DEBUG: Exception details:\\n{traceback.format_exc()}")
                time.sleep(60)  # Wait 1 minute on error
    
    def start_web_server(self):
        """Enhanced web server with debug endpoints"""
        port = int(os.environ.get('PORT', 8080))
        
        class DebugDashboardHandler(BaseHTTPRequestHandler):
            def __init__(self, *args, trading_system=None, **kwargs):
                self.trading_system = trading_system
                super().__init__(*args, **kwargs)
            
            def do_GET(self):
                if self.path == '/':
                    self.serve_dashboard()
                elif self.path == '/debug':
                    self.serve_debug_dashboard()
                elif self.path == '/api/diagnostics':
                    self.serve_diagnostics()
                elif self.path == '/api/status':
                    self.serve_api_status()
                elif self.path == '/test/discord':
                    self.handle_discord_test()
                elif self.path == '/test/cboe':
                    self.handle_cboe_test()
                elif self.path == '/health':
                    self.handle_health()
                else:
                    self.send_error(404, "Not Found")
            
            def serve_debug_dashboard(self):
                """Serve comprehensive debug dashboard"""
                diagnostics = self.trading_system.run_system_diagnostics()
                
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Secret_Alerts v{VERSION} - DEBUG</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="30">
    <style>
        body {{ background: #0a0e27; color: #e0e0e0; font-family: monospace; margin: 0; padding: 1rem; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 2rem; background: #1a1a2e; padding: 2rem; border-radius: 8px; }}
        .section {{ background: #16213e; padding: 1.5rem; margin-bottom: 1rem; border-radius: 8px; }}
        .status-pass {{ color: #00ff88; }}
        .status-fail {{ color: #ff3366; }}
        .status-warn {{ color: #ff9500; }}
        .status-skip {{ color: #888; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1rem; }}
        .btn {{ background: #00d9ff; color: #0a0e27; padding: 0.75rem 1rem; border-radius: 4px; text-decoration: none; font-weight: bold; margin: 0.25rem; display: inline-block; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
        .stat {{ background: #2d3748; padding: 1rem; border-radius: 8px; text-align: center; }}
        pre {{ background: #0a0e27; padding: 1rem; border-radius: 4px; overflow-x: auto; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #2d3748; }}
        th {{ background: #2d3748; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Secret_Alerts v{VERSION} - DEBUG DASHBOARD</h1>
            <p>System Health Monitor & Diagnostics</p>
        </div>
        
        <div class="stats">
            <div class="stat">
                <h3>Total Checks</h3>
                <p style="font-size: 2rem;">{self.trading_system.total_checks}</p>
            </div>
            <div class="stat">
                <h3>Alerts Sent</h3>
                <p style="font-size: 2rem;">{self.trading_system.total_alerts_sent}</p>
            </div>
            <div class="stat">
                <h3>Last Check</h3>
                <p>{self.trading_system.last_cboe_check or 'Never'}</p>
            </div>
            <div class="stat">
                <h3>System Status</h3>
                <p style="font-size: 1.5rem; color: #00ff88;">{'🟢 RUNNING' if self.trading_system.running else '🔴 STOPPED'}</p>
            </div>
        </div>
        
        <div class="grid">
            <div class="section">
                <h2>📦 Module Import Status</h2>
                <table>
                    <tr><th>Module</th><th>Status</th></tr>
                    {''.join(f'<tr><td>{module}</td><td class="status-{"pass" if status else "fail"}">{"✅ LOADED" if status else "❌ FAILED"}</td></tr>' for module, status in diagnostics['module_imports'].items())}
                </table>
            </div>
            
            <div class="section">
                <h2>🏥 System Health</h2>
                <table>
                    <tr><th>Component</th><th>Status</th></tr>
                    {''.join(f'<tr><td>{component.replace("_", " ").title()}</td><td class="status-{"pass" if status else "fail"}">{"✅ READY" if status else "❌ FAILED"}</td></tr>' for component, status in diagnostics['system_health'].items() if component != 'startup_time')}
                </table>
            </div>
        </div>
        
        <div class="section">
            <h2>🧪 Diagnostic Tests</h2>
            <table>
                <tr><th>Test</th><th>Status</th><th>Details</th></tr>
                {''.join(f'<tr><td>{test}</td><td class="status-{result["status"].lower()}">{result["status"]}</td><td>{result.get("details", result.get("error", "N/A"))}</td></tr>' for test, result in diagnostics['tests'].items())}
            </table>
        </div>
        
        <div class="section">
            <h2>⚙️ Actions</h2>
            <a href="/test/discord" class="btn">🧪 Test Discord</a>
            <a href="/test/cboe" class="btn">📊 Test CBOE Download</a>
            <a href="/api/diagnostics" class="btn" target="_blank">📄 Full Diagnostics JSON</a>
            <a href="/api/status" class="btn" target="_blank">📊 System Status JSON</a>
            <a href="/" class="btn">🏠 Main Dashboard</a>
        </div>
    </div>
</body>
</html>"""
                self._send_html_response(html)
            
            def serve_diagnostics(self):
                """Serve full system diagnostics as JSON"""
                diagnostics = self.trading_system.run_system_diagnostics()
                self._send_json_response(diagnostics)
            
            def handle_discord_test(self):
                """Handle Discord test"""
                result = self.trading_system.test_discord_alert()
                self._send_simple_response("Discord Test", f"<pre>{json.dumps(result, indent=2)}</pre>")
            
            def handle_cboe_test(self):
                """Handle CBOE test"""
                result = self.trading_system.test_cboe_download()
                self._send_simple_response("CBOE Test", f"<pre>{json.dumps(result, indent=2)}</pre>")
            
            def serve_dashboard(self):
                """Serve main dashboard with debug info"""
                mode, status = self.trading_system.market_scheduler.get_current_status()
                
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Secret_Alerts v{VERSION}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="60">
    <style>
        body {{ background: #1a1a2e; color: #e0e0e0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 2rem; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 12px; }}
        .header h1 {{ margin: 0; font-size: 2.5rem; }}
        .debug-banner {{ background: #ff9500; color: #000; text-align: center; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; font-weight: bold; }}
        .status-card {{ background: #16213e; padding: 1.5rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #00d9ff; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }}
        .card {{ background: #16213e; padding: 1.5rem; border-radius: 12px; border: 1px solid #2d3748; }}
        .btn {{ background: #00d9ff; color: #1a1a2e; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-block; margin: 0.25rem; }}
        .ticker {{ background: #2d3748; padding: 0.5rem; border-radius: 6px; display: inline-block; margin: 0.25rem; font-weight: bold; }}
        .vip {{ background: linear-gradient(135deg, #ffd700, #ffb300); color: #1a1a2e; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="debug-banner">
            🔍 DEBUG MODE ACTIVE - Enhanced monitoring and diagnostics enabled
        </div>
        
        <div class="header">
            <h1>🚀 Secret_Alerts v{VERSION}</h1>
            <p>Modular Trading Intelligence System</p>
        </div>
        
        <div class="status-card">
            <h2>📊 System Status</h2>
            <p><strong>Market Mode:</strong> {mode}</p>
            <p><strong>Status:</strong> {status}</p>
            <p><strong>System:</strong> {'🟢 Running' if self.trading_system.running else '🔴 Stopped'}</p>
            <p><strong>Discord:</strong> {'✅ Enabled' if self.trading_system.discord.enabled else '❌ Disabled'}</p>
            <p><strong>Total Checks:</strong> {self.trading_system.total_checks}</p>
            <p><strong>Alerts Sent:</strong> {self.trading_system.total_alerts_sent}</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>🔍 Debug Actions</h3>
                <a href="/debug" class="btn">🔍 Full Debug Dashboard</a>
                <a href="/test/discord" class="btn">🧪 Test Discord</a>
                <a href="/test/cboe" class="btn">📊 Test CBOE</a>
                <a href="/api/diagnostics" class="btn" target="_blank">📄 Diagnostics API</a>
            </div>
            
            <div class="card">
                <h3>💎 VIP Tickers</h3>
                {' '.join(f'<span class="ticker vip">{ticker}</span>' for ticker in self.trading_system.config.vip_tickers)}
            </div>
            
            <div class="card">
                <h3>📊 All Keywords</h3>
                {' '.join(f'<span class="ticker">{keyword}</span>' for keyword in self.trading_system.config.keywords[:10])}
                {f'<br><small>...and {len(self.trading_system.config.keywords) - 10} more</small>' if len(self.trading_system.config.keywords) > 10 else ''}
            </div>
        </div>
    </div>
</body>
</html>"""
                self._send_html_response(html)
            
            def serve_api_status(self):
                """Enhanced API status with debug info"""
                status_data = {
                    "version": VERSION,
                    "build_date": BUILD_DATE,
                    "timestamp": datetime.now().isoformat(),
                    "debug_mode": True,
                    "system_health": self.trading_system.system_health,
                    "module_status": MODULE_STATUS,
                    "market": self.trading_system.market_scheduler.get_status_dict(),
                    "monitoring": {
                        "total_checks": self.trading_system.total_checks,
                        "total_alerts_sent": self.trading_system.total_alerts_sent,
                        "last_cboe_check": self.trading_system.last_cboe_check,
                        "running": self.trading_system.running
                    },
                    "configuration": {
                        "keywords_count": len(self.config.keywords),
                        "vip_tickers_count": len(self.config.vip_tickers),
                        "discord_enabled": self.trading_system.discord.enabled,
                        "cboe_url": self.trading_system.config.cboe_url
                    }
                }
                self._send_json_response(status_data)
            
            def handle_health(self):
                """Health check endpoint"""
                health_status = "healthy" if all(self.trading_system.system_health.values()) else "degraded"
                self._send_json_response({
                    "status": health_status, 
                    "version": VERSION,
                    "timestamp": datetime.now().isoformat(),
                    "debug_mode": True
                })
            
            def _send_html_response(self, html):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))
            
            def _send_json_response(self, data):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data, indent=2).encode())
            
            def _send_simple_response(self, title, content):
                html = f"""<!DOCTYPE html>
<html><head><title>{title}</title>
<style>body{{background:#1a1a2e;color:#fff;font-family:sans-serif;text-align:center;padding:3rem;}}
.container{{max-width:800px;margin:auto;background:#16213e;padding:2rem;border-radius:12px;}}
a{{color:#00d9ff;font-weight:bold;text-decoration:none;}}
pre{{background:#0a0e27;padding:1rem;border-radius:8px;text-align:left;overflow-x:auto;}}
</style></head><body><div class="container">
<h1>{title}</h1><div>{content}</div><br><a href='/debug'>← Back to Debug Dashboard</a>
</div></body></html>"""
                self._send_html_response(html)
        
        # *** THIS IS THE FIX ***
        # Use a lambda to correctly pass the 'self' instance to the handler.
        handler = lambda *args, **kwargs: DebugDashboardHandler(*args, trading_system=self, **kwargs)
        server = HTTPServer(('', port), handler)
        
        print(f"🌐 Debug web server starting on port {port}")
        print(f"🔍 Visit your URL for the main dashboard")
        print(f"🔍 Visit your URL/debug for detailed diagnostics")
        server.serve_forever()
    
    def _send_startup_alert(self):
        """Enhanced startup alert with debug info"""
        mode, status = self.market_scheduler.get_current_status()
        
        message = f"🚀 **Secret_Alerts v{VERSION} Started (DEBUG MODE)**\\n\\n"
        message += f"🔍 **Debug Features Enabled:**\\n"
        message += f"• Detailed module health checks\\n"
        message += f"• Enhanced error reporting\\n"
        message += f"• Real-time diagnostics dashboard\\n"
        message += f"• Individual component testing\\n\\n"
        message += f"📅 **Current Mode:** {mode}\\n"
        message += f"📊 **Status:** {status}\\n"
        message += f"💎 **VIP Tickers:** {', '.join(self.config.vip_tickers)}\\n"
        message += f"🎯 **Keywords:** {len(self.config.keywords)} monitored\\n"
        message += f"🏗️ **Architecture:** Modular (all {len(MODULE_STATUS)} modules loaded)\\n\\n"
        message += f"🔍 **Debug Dashboard:** Visit /debug endpoint for full diagnostics\\n"
        message += f"*Debug mode active - ready for comprehensive testing!*"
        
        self.discord.send_alert("🚀 Secret_Alerts DEBUG Mode Online", message, 0x00FF00)
    
    # *** THIS IS THE FIX - REMOVED DUPLICATE METHOD ***
    # The recursive test_discord_alert method was removed from here.
    
    def run_complete_system_test(self) -> dict:
        """Run all system tests and return comprehensive results"""
        print("\\n🧪 Running complete system test suite...")
        
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {}
        }
        
        # Run diagnostics
        test_results['diagnostics'] = self.run_system_diagnostics()
        
        # Test Discord
        test_results['tests']['discord'] = self.test_discord_alert()
        
        # Test CBOE download
        test_results['tests']['cboe'] = self.test_cboe_download()
        
        # Calculate overall status
        all_tests = []
        all_tests.extend([test['status'] for test in test_results['diagnostics']['tests'].values()])
        all_tests.append(test_results['tests']['discord']['status'])
        all_tests.append(test_results['tests']['cboe']['status'])
        
        passed_tests = sum(1 for test in all_tests if test in ['PASS', 'SUCCESS'])
        total_tests = len(all_tests)
        
        test_results['summary'] = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'success_rate': f"{(passed_tests/total_tests*100):.1f}%",
            'overall_status': 'PASS' if passed_tests == total_tests else 'PARTIAL' if passed_tests > 0 else 'FAIL'
        }
        
        print(f"\\n🧪 Test suite complete: {passed_tests}/{total_tests} tests passed ({test_results['summary']['success_rate']})")
        
        return test_results
    
    def run(self):
        """Start the complete debug system"""
        print("\\n" + "="*70)
        print(f"🔍 Secret_Alerts v{VERSION} - DEBUG MODE")
        print(f"🏗️  Built: {BUILD_DATE}")
        print("🧪 Enhanced debugging and diagnostics enabled")
        print("="*70 + "\\n")
        
        # Run initial diagnostics
        self.run_system_diagnostics()
        
        # Run complete system test
        test_results = self.run_complete_system_test()
        
        if test_results['summary']['overall_status'] == 'FAIL':
            print("\\n❌ CRITICAL: System tests failed. Please review the errors above.")
            print("🔧 Fix the issues before deploying to production.")
            return
        
        self.running = True
        
        try:
            print("\\n🚀 Starting system with debug monitoring...")
            
            # Start monitoring in background thread
            monitor_thread = threading.Thread(target=self.start_monitoring_loop, daemon=True)
            monitor_thread.start()
            
            # Start web server (this will block)
            self.start_web_server()
            
        except KeyboardInterrupt:
            print("\\n🛑 Shutdown signal received")
        except Exception as e:
            print(f"\\n❌ System error: {e}")
            print(f"🔍 DEBUG: Exception details:\\n{traceback.format_exc()}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Graceful system shutdown with debug info"""
        print("\\n🛑 Shutting down debug system...")
        self.running = False
        
        shutdown_msg = f"🛑 **Secret_Alerts v{VERSION} DEBUG Shutdown**\\n\\n"
        shutdown_msg += f"📊 **Session Statistics:**\\n"
        shutdown_msg += f"• Total checks performed: {self.total_checks}\\n"
        shutdown_msg += f"• Total alerts sent: {self.total_alerts_sent}\\\\n"
        shutdown_msg += f"• Last check: {self.last_cboe_check or 'Never'}\\\\n"
        shutdown_msg += f"⏰ **Shutdown time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\\\n\\\\n"
        shutdown_msg += f"*Debug session complete*"
        
        self.discord.send_alert("🛑 DEBUG Session Ended", shutdown_msg, 0xFF6600)
        print("✅ Debug system shutdown complete")


def main():
    """Enhanced main entry point with error handling"""
    try:
        print("🔍 Starting Secret_Alerts DEBUG system...")
        system = DebugTradingSystemOrchestrator()
        system.run()
    except Exception as e:
        print(f"\\n❌ CRITICAL: Failed to start system: {e}")
        print(f"🔍 DEBUG: Exception details:\\n{traceback.format_exc()}")
        print("\\n🔧 Please check the error details above and fix any issues.")


if __name__ == "__main__":
    main()
