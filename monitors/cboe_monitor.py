"""
CBOE Circuit Breaker Monitor Module - FIXED VERSION
Handles downloading and monitoring CBOE circuit breaker data with proper change detection
"""

import requests
import pandas as pd
import hashlib
from typing import Dict, List, Optional, Tuple
from io import StringIO
from datetime import datetime

class CBOEMonitor:
    """Enhanced CBOE circuit breaker monitoring system with proper change detection"""
    
    def __init__(self, config, alert_manager):
        self.config = config
        self.alert_manager = alert_manager
        self.previous_df = None
        self.previous_hash = ""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Updated VIP tickers list
        self.vip_tickers = ['TSLA', 'HOOD', 'UVXY', 'RBLX', 'QBTS', 'TEM']
        print(f"[CBOE] 💎 VIP Tickers: {', '.join(self.vip_tickers)}")
        
    def download_csv(self) -> Optional[pd.DataFrame]:
        """Download and parse CBOE CSV data with error handling"""
        try:
            print(f"[CBOE] 📥 Downloading data from CBOE...")
            response = self.session.get(self.config.cboe_url, timeout=30)
            response.raise_for_status()
            
            # Parse CSV data
            df = pd.read_csv(StringIO(response.text))
            print(f"[CBOE] ✅ Downloaded {len(df)} circuit breaker records")
            return df
            
        except requests.exceptions.RequestException as e:
            print(f"[CBOE] ❌ Download failed: {e}")
            return None
        except pd.errors.EmptyDataError:
            print(f"[CBOE] ⚠️  Empty data received")
            return None
        except Exception as e:
            print(f"[CBOE] ❌ Unexpected error: {e}")
            return None
    
    def find_keyword_matches(self, df: pd.DataFrame) -> Tuple[List[str], List[str]]:
        """Find keyword matches and separate VIP from regular matches"""
        if df is None or df.empty:
            return [], []
        
        matches = []
        vip_matches = []
        
        # Convert dataframe to searchable text
        searchable_content = df.to_string().upper()
        
        # Search for each keyword
        for keyword in self.config.keywords:
            if keyword.upper() in searchable_content:
                matches.append(keyword)
        
        # Search for VIP tickers specifically
        for vip_ticker in self.vip_tickers:
            if vip_ticker.upper() in searchable_content:
                vip_matches.append(vip_ticker)
                # Make sure VIP tickers are also in matches
                if vip_ticker not in matches:
                    matches.append(vip_ticker)
        
        # Remove duplicates while preserving order
        matches = list(dict.fromkeys(matches))
        vip_matches = list(dict.fromkeys(vip_matches))
        
        return matches, vip_matches
    
    def get_active_circuit_breakers(self, df: pd.DataFrame) -> List[Dict]:
        """Get circuit breakers that are currently active (started but not ended)"""
        if df is None or df.empty:
            return []
        
        active_breakers = []
        
        try:
            for _, row in df.iterrows():
                # Check if has trigger date/time but no end date/time
                trigger_date = row.get('Trigger Date', '') if 'Trigger Date' in row else row.get('START TIME', '')
                trigger_time = row.get('Trigger Time', '') if 'Trigger Time' in row else ''
                end_date = row.get('End Date', '') if 'End Date' in row else row.get('END TIME', '')
                end_time = row.get('End Time', '') if 'End Time' in row else ''
                
                # Consider it active if it has trigger info but no end info
                has_trigger = bool(trigger_date and str(trigger_date) != 'nan' and trigger_date != '')
                has_end = bool(end_date and str(end_date) != 'nan' and end_date != '')
                
                if has_trigger and not has_end:
                    symbol = row.get('Symbol', row.get('SYMBOL', 'N/A'))
                    security_name = row.get('Security Name', row.get('SECURITY NAME', 'N/A'))
                    
                    active_breakers.append({
                        'symbol': symbol,
                        'security_name': security_name,
                        'trigger_date': trigger_date,
                        'trigger_time': trigger_time,
                        'exchange': row.get('Primary Listing Exchange', row.get('EXCHANGE', 'N/A')),
                        'is_vip': symbol.upper() in [vip.upper() for vip in self.vip_tickers]
                    })
        
        except Exception as e:
            print(f"[CBOE] ⚠️ Error parsing active breakers: {e}")
        
        return active_breakers
    
    def analyze_circuit_breaker_data(self, df: pd.DataFrame) -> Dict:
        """Analyze circuit breaker data for additional insights"""
        if df is None or df.empty:
            return {}
        
        active_breakers = self.get_active_circuit_breakers(df)
        
        analysis = {
            'total_rows': len(df),
            'columns': list(df.columns),
            'active_breakers': len(active_breakers),
            'active_breakers_list': active_breakers
        }
        
        # Separate VIP active breakers
        vip_active = [cb for cb in active_breakers if cb['is_vip']]
        if vip_active:
            analysis['vip_active_breakers'] = len(vip_active)
            analysis['vip_active_symbols'] = [cb['symbol'] for cb in vip_active]
        
        return analysis
    
    def check(self) -> Dict:
        """Perform comprehensive CBOE check with PROPER change detection"""
        print(f"[CBOE] 🔍 Starting circuit breaker check at {datetime.now().strftime('%H:%M:%S')}")
        
        # Download data
        df = self.download_csv()
        if df is None:
            return {
                'error': 'Failed to download CBOE data',
                'timestamp': datetime.now().isoformat()
            }
        
        # Check for changes
        current_hash = hashlib.md5(df.to_string().encode('utf-8')).hexdigest()
        has_changes = (current_hash != self.previous_hash)
        is_initial = (self.previous_hash == "")
        
        # Find matches
        matches, vip_matches = self.find_keyword_matches(df)
        
        # Analyze data
        analysis = self.analyze_circuit_breaker_data(df)
        
        # Prepare results
        results = {
            'timestamp': datetime.now().isoformat(),
            'total_rows': len(df),
            'matches': len(matches),
            'vip_matches': len(vip_matches),
            'keywords_found': matches,
            'vip_keywords_found': vip_matches,
            'has_changes': has_changes,
            'is_initial': is_initial,
            'analysis': analysis,
            'alert_sent': False
        }
        
        # *** THIS IS THE CRITICAL FIX ***
        # Only send alerts if there are actual changes OR it's the initial run
        if (has_changes or is_initial) and (matches or vip_matches):
            print(f"[CBOE] ⚡ {'INITIAL RUN' if is_initial else 'CHANGES DETECTED'} - Sending alerts for {len(matches)} matches ({len(vip_matches)} VIP)")
            
            success = self.alert_manager.process_circuit_breaker_matches(
                matches=matches,
                vip_matches=vip_matches,
                mode=self._get_current_mode(),
                additional_data=analysis
            )
            results['alert_sent'] = success
            
            # Enhanced logging
            if vip_matches:
                print(f"[CBOE] 🔥 VIP MATCHES: {', '.join(vip_matches)}")
            if matches:
                print(f"[CBOE] 📊 ALL MATCHES: {', '.join(matches)}")
                
        elif matches or vip_matches:
            print(f"[CBOE] ✅ Same data as before - No alerts sent ({len(matches)} existing matches)")
            
        else:
            print(f"[CBOE] ✅ No keyword matches found in {len(df)} records")
        
        # Update state
        self.previous_hash = current_hash
        self.previous_df = df.copy()
        
        return results
    
    def manual_check_active_positions(self) -> Dict:
        """Manual check for active circuit breakers - ALWAYS sends alerts"""
        print(f"[CBOE] 🔧 MANUAL CHECK: Forcing active positions alert...")
        
        # Download fresh data
        df = self.download_csv()
        if df is None:
            return {
                'error': 'Failed to download CBOE data for manual check',
                'timestamp': datetime.now().isoformat()
            }
        
        # Get active circuit breakers
        active_breakers = self.get_active_circuit_breakers(df)
        analysis = self.analyze_circuit_breaker_data(df)
        
        # Find matches in active breakers
        active_matches = []
        active_vip_matches = []
        
        for breaker in active_breakers:
            symbol = breaker['symbol'].upper()
            
            # Check if symbol matches our keywords
            for keyword in self.config.keywords:
                if keyword.upper() in symbol or keyword.upper() in breaker['security_name'].upper():
                    if keyword not in active_matches:
                        active_matches.append(keyword)
            
            # Check if it's a VIP ticker
            if symbol in [vip.upper() for vip in self.vip_tickers]:
                if symbol not in active_vip_matches:
                    active_vip_matches.append(symbol)
        
        # FORCE alerts regardless of changes
        if active_breakers:
            print(f"[CBOE] 🚨 MANUAL CHECK: Forcing alerts for {len(active_breakers)} active positions ({len(active_vip_matches)} VIP)")
            
            # Create special alert message for manual check
            manual_analysis = analysis.copy()
            manual_analysis['manual_check'] = True
            manual_analysis['forced_alert'] = True
            
            success = self.alert_manager.process_circuit_breaker_matches(
                matches=active_matches or ['MANUAL_CHECK'],  # Force at least one match
                vip_matches=active_vip_matches,
                mode=self._get_current_mode(),
                additional_data=manual_analysis
            )
            
            return {
                'manual_check': True,
                'active_positions': len(active_breakers),
                'active_vip_positions': len(active_vip_matches),
                'active_breakers_list': active_breakers,
                'alert_sent': success,
                'timestamp': datetime.now().isoformat()
            }
        else:
            print(f"[CBOE] ✅ MANUAL CHECK: No active positions found")
            return {
                'manual_check': True,
                'active_positions': 0,
                'active_vip_positions': 0,
                'message': 'No currently active circuit breakers',
                'timestamp': datetime.now().isoformat()
            }
    
    def _get_current_mode(self) -> str:
        """Get current market mode (helper method)"""
        from datetime import datetime, time
        import pytz
        
        cst = pytz.timezone('America/Chicago')
        now_cst = datetime.now(cst).time()
        
        rush_start = time(8, 20)
        rush_end = time(10, 0)
        
        if rush_start <= now_cst <= rush_end:
            return "RUSH_HOUR"
        elif time(10, 0) <= now_cst <= time(15, 30):
            return "NORMAL_HOURS"
        else:
            return "AFTER_HOURS"
    
    def get_status(self) -> Dict:
        """Get monitor status information"""
        return {
            'cboe_url': self.config.cboe_url,
            'monitoring_keywords': len(self.config.keywords),
            'vip_tickers': len(self.vip_tickers),
            'vip_tickers_list': self.vip_tickers,
            'keywords': self.config.keywords,
            'has_previous_data': bool(self.previous_hash),
            'last_check': datetime.now().isoformat()
        }