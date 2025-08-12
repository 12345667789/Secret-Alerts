"""
Time Travel Testing Module for Secret_Alerts
Simulates historical state changes to test alert detection logic
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
import pytz
from typing import Tuple, Dict, Any
from monitors.cboe_monitor import ShortSaleMonitor
from alerts.templates import AlertTemplateManager

class TimeTravelTester:
    """
    Test alert detection by simulating historical data states
    """
    
    def __init__(self, vip_symbols=None):
        self.vip_symbols = vip_symbols or ['TSLA', 'AAPL', 'GOOG', 'NVDA']
        self.template_manager = AlertTemplateManager(vip_symbols=self.vip_symbols)
        self.cst = pytz.timezone('America/Chicago')
        
    def simulate_historical_check(self, target_time_str: str) -> Dict[str, Any]:
        """
        Simulate what alerts would have been generated at a specific time
        
        Args:
            target_time_str: Time to simulate in format "2025-08-12 09:35:00"
        
        Returns:
            Dictionary with simulation results
        """
        logging.info(f"🕐 Starting time travel simulation for {target_time_str}")
        
        try:
            # Parse target time
            target_time = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
            target_time = self.cst.localize(target_time)
            
            # Get current CBOE data
            monitor = ShortSaleMonitor()
            current_data = monitor.fetch_data()
            
            if current_data is None or current_data.empty:
                return {"error": "Could not fetch current CBOE data"}
            
            # Create simulated "before" and "after" states
            before_state, after_state = self._create_simulation_states(
                current_data, target_time
            )
            
            # Simulate the alert detection
            new_alerts, ended_alerts = self._detect_changes(before_state, after_state)
            
            # Format the results
            result = self._format_simulation_results(
                target_time, before_state, after_state, new_alerts, ended_alerts
            )
            
            logging.info(f"✅ Time travel simulation completed for {target_time_str}")
            return result
            
        except Exception as e:
            logging.error(f"❌ Time travel simulation failed: {e}")
            return {"error": str(e)}
    
    def _create_simulation_states(self, current_data: pd.DataFrame, 
                                 target_time: datetime) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Create before/after states based on target time
        """
        # Convert string dates to datetime for comparison
        current_data = current_data.copy()
        current_data['trigger_datetime'] = pd.to_datetime(
            current_data['Trigger Date'] + ' ' + current_data['Trigger Time']
        )
        
        # Create "before" state - all alerts that existed before target time
        before_mask = current_data['trigger_datetime'] < target_time
        before_state = current_data[before_mask].copy()
        
        # For "before" state, remove end times for alerts that ended after target time
        if 'End Date' in before_state.columns and 'End Time' in before_state.columns:
            for idx, row in before_state.iterrows():
                if pd.notnull(row['End Date']) and pd.notnull(row['End Time']):
                    end_datetime = pd.to_datetime(f"{row['End Date']} {row['End Time']}")
                    if end_datetime >= target_time:
                        # This alert hadn't ended yet at target time
                        before_state.at[idx, 'End Date'] = None
                        before_state.at[idx, 'End Time'] = None
        
        # Create "after" state - add alerts that triggered AT the target time
        target_date = target_time.strftime('%Y-%m-%d')
        target_time_window = target_time + timedelta(minutes=1)  # 1-minute window
        
        new_at_target = current_data[
            (current_data['trigger_datetime'] >= target_time) & 
            (current_data['trigger_datetime'] < target_time_window)
        ].copy()
        
        after_state = pd.concat([before_state, new_at_target]).drop_duplicates()
        
        # Add unique keys for comparison
        before_state['UniqueKey'] = (
            before_state['Symbol'].astype(str) + "_" + 
            before_state['Trigger Date'].astype(str) + "_" + 
            before_state['Trigger Time'].astype(str)
        )
        
        after_state['UniqueKey'] = (
            after_state['Symbol'].astype(str) + "_" + 
            after_state['Trigger Date'].astype(str) + "_" + 
            after_state['Trigger Time'].astype(str)
        )
        
        return before_state, after_state
    
    def _detect_changes(self, before_state: pd.DataFrame, 
                       after_state: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Detect new and ended alerts between states
        """
        new_alerts = pd.DataFrame()
        ended_alerts = pd.DataFrame()
        
        if before_state.empty:
            # All alerts in after_state are new
            new_alerts = after_state.copy()
        else:
            # Find new alerts (in after but not in before)
            before_keys = set(before_state['UniqueKey'])
            after_keys = set(after_state['UniqueKey'])
            new_keys = after_keys - before_keys
            
            if new_keys:
                new_alerts = after_state[after_state['UniqueKey'].isin(new_keys)].copy()
            
            # Find ended alerts (were open in before, now have end time in after)
            if 'End Time' in before_state.columns and 'End Time' in after_state.columns:
                previously_open = before_state[pd.isnull(before_state['End Time'])]
                currently_closed = after_state[pd.notnull(after_state['End Time'])]
                
                if not previously_open.empty and not currently_closed.empty:
                    ended_keys = set(previously_open['UniqueKey']) & set(currently_closed['UniqueKey'])
                    if ended_keys:
                        ended_alerts = currently_closed[currently_closed['UniqueKey'].isin(ended_keys)].copy()
        
        return new_alerts, ended_alerts
    
    def _format_simulation_results(self, target_time: datetime, before_state: pd.DataFrame,
                                  after_state: pd.DataFrame, new_alerts: pd.DataFrame,
                                  ended_alerts: pd.DataFrame) -> Dict[str, Any]:
        """
        Format simulation results for display
        """
        result = {
            "simulation_time": target_time.strftime('%Y-%m-%d %H:%M:%S CST'),
            "before_state": {
                "total_alerts": len(before_state),
                "open_alerts": len(before_state[pd.isnull(before_state['End Time'])]) if not before_state.empty else 0,
                "sample_alerts": []
            },
            "after_state": {
                "total_alerts": len(after_state),
                "open_alerts": len(after_state[pd.isnull(after_state['End Time'])]) if not after_state.empty else 0,
                "sample_alerts": []
            },
            "detected_changes": {
                "new_alerts": len(new_alerts),
                "ended_alerts": len(ended_alerts),
                "new_alert_details": [],
                "ended_alert_details": []
            },
            "discord_preview": None
        }
        
        # Add sample alerts from before state
        if not before_state.empty:
            open_before = before_state[pd.isnull(before_state['End Time'])].head(3)
            for _, row in open_before.iterrows():
                result["before_state"]["sample_alerts"].append({
                    "symbol": row['Symbol'],
                    "security_name": row.get('Security Name', ''),
                    "trigger_time": f"{row['Trigger Date']} {row['Trigger Time']}",
                    "is_vip": row['Symbol'] in self.vip_symbols
                })
        
        # Add sample alerts from after state
        if not after_state.empty:
            open_after = after_state[pd.isnull(after_state['End Time'])].head(3)
            for _, row in open_after.iterrows():
                result["after_state"]["sample_alerts"].append({
                    "symbol": row['Symbol'],
                    "security_name": row.get('Security Name', ''),
                    "trigger_time": f"{row['Trigger Date']} {row['Trigger Time']}",
                    "is_vip": row['Symbol'] in self.vip_symbols
                })
        
        # Add new alert details
        if not new_alerts.empty:
            for _, row in new_alerts.iterrows():
                result["detected_changes"]["new_alert_details"].append({
                    "symbol": row['Symbol'],
                    "security_name": row.get('Security Name', ''),
                    "trigger_time": f"{row['Trigger Date']} {row['Trigger Time']}",
                    "is_vip": row['Symbol'] in self.vip_symbols
                })
        
        # Add ended alert details
        if not ended_alerts.empty:
            for _, row in ended_alerts.iterrows():
                result["detected_changes"]["ended_alert_details"].append({
                    "symbol": row['Symbol'],
                    "security_name": row.get('Security Name', ''),
                    "end_time": f"{row.get('End Date', 'N/A')} {row.get('End Time', 'N/A')}",
                    "is_vip": row['Symbol'] in self.vip_symbols
                })
        
        # Generate Discord preview if there are changes
        if not new_alerts.empty or not ended_alerts.empty:
            formatter = self.template_manager.get_formatter('short_sale')
            alert_data = formatter.format_changes_alert(new_alerts, ended_alerts)
            result["discord_preview"] = alert_data
        
        return result
    
    def get_suggested_test_times(self) -> list:
        """
        Suggest good test times based on current CBOE data
        """
        try:
            monitor = ShortSaleMonitor()
            current_data = monitor.fetch_data()
            
            if current_data is None or current_data.empty:
                return []
            
            # Get recent trigger times
            recent_triggers = current_data.sort_values('Trigger Date', ascending=False).head(10)
            
            suggestions = []
            for _, row in recent_triggers.iterrows():
                # Convert trigger time to datetime and add 1 minute for "after" simulation
                try:
                    trigger_dt = datetime.strptime(f"{row['Trigger Date']} {row['Trigger Time']}", 
                                                 "%Y-%m-%d %H:%M:%S")
                    test_time = trigger_dt + timedelta(minutes=1)
                    
                    suggestions.append({
                        "test_time": test_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "description": f"Test detection of {row['Symbol']} alert at {row['Trigger Time']}",
                        "symbol": row['Symbol'],
                        "is_vip": row['Symbol'] in self.vip_symbols
                    })
                except:
                    continue
            
            return suggestions[:5]  # Return top 5 suggestions
            
        except Exception as e:
            logging.error(f"Error generating test suggestions: {e}")
            return []


def run_time_travel_test(target_time: str, vip_symbols=None) -> Dict[str, Any]:
    """
    Convenience function to run a time travel test
    
    Args:
        target_time: Time string in format "2025-08-12 09:35:00"
        vip_symbols: List of VIP symbols
        
    Returns:
        Test results dictionary
    """
    tester = TimeTravelTester(vip_symbols=vip_symbols)
    return tester.simulate_historical_check(target_time)


def get_test_suggestions(vip_symbols=None) -> list:
    """
    Get suggested test times based on recent CBOE data
    """
    tester = TimeTravelTester(vip_symbols=vip_symbols)
    return tester.get_suggested_test_times()
