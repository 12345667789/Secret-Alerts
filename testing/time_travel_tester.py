"""
Time Travel Testing Module for Secret_Alerts _test stage
Simulates historical state changes to test alert detection logic with intelligence analysis
"""

import pandas as pd
import logging
from datetime import datetime
import pytz
from typing import Tuple, Dict, Any, List
from monitors.cboe_monitor import ShortSaleMonitor
from alerts.templates import AlertTemplateManager

class TimeTravelTester:
    """
    Test alert detection by simulating historical data states with intelligence analysis
    """
    
    def __init__(self, vip_symbols=None):
        self.vip_symbols = vip_symbols or []
        self.template_manager = AlertTemplateManager(vip_symbols=self.vip_symbols)
        self.cst = pytz.timezone('America/Chicago')
        
    def simulate_historical_check(self, target_time: datetime) -> Dict[str, Any]:
        """
        Simulate what alerts would have been generated at a specific time.
        """
        logging.info(f"🕒 Starting time travel simulation for {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            monitor = ShortSaleMonitor()
            current_data = monitor.fetch_data()
            
            if current_data is None or current_data.empty:
                return {"error": "Could not fetch current CBOE data"}
            
            before_state, after_state = self._create_simulation_states(current_data, target_time)
            new_alerts, ended_alerts = self._detect_changes(before_state, after_state)
            result = self._format_simulation_results_with_intelligence(target_time, new_alerts, ended_alerts, after_state)
            
            logging.info(f"✅ Time travel simulation completed for {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return result
            
        except Exception as e:
            logging.error(f"⌛ Time travel simulation failed: {e}", exc_info=True)
            return {"error": str(e)}

    # ... all other helper methods from your original file go here ...
    # (_create_simulation_states, _detect_changes, etc.)
    # For brevity, I am omitting them, but they should be the same as the last version you sent.


# --- Convenience Functions (defined at the module level) ---

def run_time_travel_test(target_time: datetime, vip_symbols=None) -> Dict[str, Any]:
    """
    Convenience function to run a time travel test with intelligence.
    """
    tester = TimeTravelTester(vip_symbols=vip_symbols)
    return tester.simulate_historical_check(target_time)


def get_test_suggestions(vip_symbols=None) -> list:
    """
    Get suggested test times based on recent CBOE data.
    """
    tester = TimeTravelTester(vip_symbols=vip_symbols)
    return tester.get_suggested_test_times()


def get_intelligence_test_summary(vip_symbols=None) -> Dict[str, Any]:
    """
    Get intelligence summary for testing purposes.
    """
    tester = TimeTravelTester(vip_symbols=vip_symbols)
    return tester.get_intelligence_summary()