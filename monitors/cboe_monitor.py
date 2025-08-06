"""
CBOE Circuit Breaker Monitor Module
Handles downloading and monitoring CBOE circuit breaker data
"""

import requests
import pandas as pd
import hashlib
from typing import Dict, List, Optional, Tuple
from io import StringIO
from datetime import datetime

class CBOEMonitor:
    """Enhanced CBOE circuit breaker monitoring system"""
    
    def __init__(self, config, alert_manager):
        self.config = config
        self.alert_manager = alert_manager
        self.previous_df = None
        self.previous_hash = ""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def download_csv(self) -> Optional[pd.DataFrame]:
        """Download and parse CBOE CSV data with error handling"""
        try:
            print(f"[CBOE] 📥 Downloading data from CBOE...")
            response = self.session.get(self.config.cboe_url, timeout=30)  # Fixed: cboe_url not cboe_csv_url
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
                
                # Check if it's a VIP ticker
                if keyword.upper() in [ticker.upper() for ticker in self.config.vip_tickers]:
                    vip_matches.append(keyword)
        
        # Remove duplicates while preserving order
        matches = list(dict.fromkeys(matches))
        vip_matches = list(dict.fromkeys(vip_matches))
        
        return matches, vip_matches
    
    def analyze_circuit_breaker_data(self, df: pd.DataFrame) -> Dict:
        """Analyze circuit breaker data for additional insights"""
        if df is None or df.empty:
            return {}
        
        analysis = {
            'total_rows': len(df),
            'columns': list(df.columns),
        }
        
        # Look for active circuit breakers (have trigger time but no end time)
        if 'Trigger Time' in df.columns and 'End Time' in df.columns:
            active_breakers = df[
                (df['Trigger Time'].notna()) & 
                (df['End Time'].isna() | (df['End Time'] == ''))
            ]
            analysis['active_breakers'] = len(active_breakers)
            
            if len(active_breakers) > 0:
                analysis['active_symbols'] = active_breakers['Symbol'].tolist() if 'Symbol' in active_breakers.columns else []
        
        return analysis
    
    def check(self) -> Dict:
        """Perform comprehensive CBOE check with change detection"""
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
            'analysis': analysis
        }
        
        # Send alerts if we have matches
        if matches or vip_matches:
            success = self.alert_manager.process_circuit_breaker_matches(
                matches=matches,
                vip_matches=vip_matches,
                mode=self._get_current_mode(),
                additional_data=analysis
            )
            results['alert_sent'] = success
            
            # Log findings
            if vip_matches:
                print(f"[CBOE] 🔥 VIP MATCHES FOUND: {', '.join(vip_matches)}")
            if matches:
                print(f"[CBOE] 📊 Total matches: {', '.join(matches)}")
        else:
            print(f"[CBOE] ✅ No keyword matches found in {len(df)} records")
        
        # Update state
        self.previous_hash = current_hash
        self.previous_df = df.copy()
        
        return results
    
    def _get_current_mode(self) -> str:
        """Get current market mode (helper method)"""
        # This is a simple fallback - in practice this would come from MarketScheduler
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
            'vip_tickers': len(self.config.vip_tickers),
            'keywords': self.config.keywords,
            'vip_tickers_list': self.config.vip_tickers,
            'has_previous_data': bool(self.previous_hash)
        }