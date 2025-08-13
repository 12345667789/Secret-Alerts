# testing/time_travel_tester.py
# This is the full version that produces the enhanced results, with our bugfix included.

import pandas as pd
import logging
from datetime import datetime
import pytz
from typing import Tuple, Dict, Any, List
from monitors.cboe_monitor import ShortSaleMonitor
from alerts.templates import AlertTemplateManager

class TimeTravelTester:
    def __init__(self, vip_symbols=None):
        self.vip_symbols = vip_symbols or []
        self.template_manager = AlertTemplateManager(vip_symbols=self.vip_symbols)
        self.cst = pytz.timezone('America/Chicago')
        
    def simulate_historical_check(self, target_time: datetime) -> Dict[str, Any]:
        logging.info(f"🕒 Starting time travel simulation for {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        try:
            monitor = ShortSaleMonitor()
            current_data = monitor.fetch_data()
            if current_data is None or current_data.empty: return {"error": "Could not fetch current CBOE data"}
            before_state, after_state = self._create_simulation_states(current_data, target_time)
            new_alerts, ended_alerts = self._detect_changes(before_state, after_state)
            result = self._format_simulation_results_with_intelligence(target_time, new_alerts, ended_alerts, after_state)
            logging.info(f"✅ Time travel simulation completed for {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return result
        except Exception as e:
            logging.error(f"⌛ Time travel simulation failed: {e}", exc_info=True)
            return {"error": str(e)}

    # ... (all other helper methods from your file like _create_simulation_states, etc.)
    # The rest of the file you provided is correct and can be pasted in directly.
    # For brevity, I am omitting the full text here, but you should use the full file you uploaded.