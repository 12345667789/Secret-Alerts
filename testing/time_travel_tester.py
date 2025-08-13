"""
Time Travel Testing Module for Secret_Alerts
Simulates historical state changes to test alert detection logic with intelligence analysis
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
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
        This function now accepts a datetime object directly.
        """
        logging.info(f"🕒 Starting time travel simulation for {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # The line causing the error has been removed, as we now pass a datetime object directly.
            
            monitor = ShortSaleMonitor()
            current_data = monitor.fetch_data()
            
            if current_data is None or current_data.empty:
                return {"error": "Could not fetch current CBOE data"}
            
            before_state, after_state = self._create_simulation_states(current_data, target_time)
            
            new_alerts, ended_alerts = self._detect_changes(before_state, after_state)
            
            result = self._format_simulation_results_with_intelligence(target_time, before_state, after_state, new_alerts, ended_alerts)
            
            logging.info(f"✅ Time travel simulation completed for {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return result
            
        except Exception as e:
            logging.error(f"⌛ Time travel simulation failed: {e}", exc_info=True)
            return {"error": str(e)}
    
    def _create_simulation_states(self, current_data: pd.DataFrame, 
                                 target_time: datetime) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Create before/after states based on target time
        """
        df = current_data.copy()
        
        df['trigger_datetime'] = pd.to_datetime(df['Trigger Date'] + ' ' + df['Trigger Time'], errors='coerce')
        df = df.dropna(subset=['trigger_datetime'])
        df['trigger_datetime'] = df['trigger_datetime'].dt.tz_localize(self.cst)

        before_state = df[df['trigger_datetime'] < target_time].copy()
        
        if 'End Time' in before_state.columns:
            end_datetime_str = before_state['End Date'].astype(str) + ' ' + before_state['End Time'].astype(str)
            end_datetimes = pd.to_datetime(end_datetime_str, errors='coerce').dt.tz_localize(self.cst)
            
            mask_to_reopen = end_datetimes >= target_time
            before_state.loc[mask_to_reopen, 'End Time'] = None
            before_state.loc[mask_to_reopen, 'End Date'] = None

        after_state = df[df['trigger_datetime'] <= target_time].copy()
        
        before_state['UniqueKey'] = before_state['Symbol'].astype(str) + "_" + before_state['Trigger Date'].astype(str) + "_" + before_state['Trigger Time'].astype(str)
        after_state['UniqueKey'] = after_state['Symbol'].astype(str) + "_" + after_state['Trigger Date'].astype(str) + "_" + after_state['Trigger Time'].astype(str)
        
        return before_state, after_state
    
    def _detect_changes(self, before_state: pd.DataFrame, 
                       after_state: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Detect new and ended alerts between states
        """
        if before_state.empty:
            new_alerts = after_state.copy()
        else:
            merged = after_state.merge(before_state[['UniqueKey']], on='UniqueKey', how='left', indicator=True)
            new_alert_mask = merged['_merge'] == 'left_only'
            new_alerts = after_state[new_alert_mask].copy()

        if before_state.empty:
            ended_alerts = pd.DataFrame()
        else:
            previously_open = before_state[pd.isnull(before_state['End Time'])]
            currently_closed = after_state[pd.notnull(after_state['End Time'])]
            
            ended_alerts = pd.DataFrame()
            if not previously_open.empty and not currently_closed.empty:
                ended_keys = previously_open.merge(currently_closed[['UniqueKey']], on='UniqueKey', how='inner')['UniqueKey']
                ended_alerts = previously_open[previously_open['UniqueKey'].isin(ended_keys)].copy()

        return new_alerts, ended_alerts
    
    def _format_simulation_results_with_intelligence(self, target_time: datetime, before_state: pd.DataFrame,
                                  after_state: pd.DataFrame, new_alerts: pd.DataFrame,
                                  ended_alerts: pd.DataFrame) -> Dict[str, Any]:
        """
        Format simulation results with intelligence analysis
        """
        result = {
            "simulation_time": target_time.strftime('%Y-%m-%d %H:%M:%S CST'),
            "detected_changes": {
                "new_alerts": len(new_alerts),
                "ended_alerts": len(ended_alerts),
                "new_alert_details": [],
            },
            "discord_preview": None,
            "intelligence_preview": None
        }
        
        if not new_alerts.empty:
            try:
                from alerts.enhanced_alert_manager import EnhancedAlertManager
                
                class DummyDiscordClient:
                    def send_alert(self, **kwargs):
                        return True
                
                dummy_discord = DummyDiscordClient()
                
                enhanced_manager = EnhancedAlertManager(
                    discord_client=dummy_discord,
                    template_manager=self.template_manager,
                    vip_symbols=self.vip_symbols
                )
                
                clean_df = self._clean_dataframe_for_intelligence(after_state)
                
                intelligence_results = enhanced_manager.intelligence_engine.analyze_batch(new_alerts, clean_df)
                
                enhanced_alert_data = self._create_intelligent_alert_preview(
                    new_alerts, ended_alerts, intelligence_results, enhanced_manager
                )
                
                result["discord_preview"] = enhanced_alert_data
                
                result["intelligence_preview"] = {
                    "total_analyzed": len(intelligence_results),
                    "vip_alerts": len([r for r in intelligence_results if r['priority'] == 'VIP']),
                    "double_mint_alerts": len([r for r in intelligence_results if r['is_double_mint']]),
                    "high_frequency_alerts": len([r for r in intelligence_results if r['frequency'] >= 15]),
                    "analysis_details": [
                        {
                            "symbol": r['row_data']['Symbol'],
                            "priority": r['priority'],
                            "priority_emoji": r['priority_emoji'],
                            "frequency": r['frequency'],
                            "frequency_tier": r['frequency_tier'],
                            "double_mint": r['is_double_mint'],
                            "underlying_asset": r['underlying_asset'],
                            "enhanced_details": r['enhanced_details']
                        }
                        for r in intelligence_results
                    ]
                }
                
                logging.info(f"🧠 Intelligence analysis: {len(intelligence_results)} alerts analyzed")
                
            except Exception as e:
                logging.warning(f"Could not generate intelligence preview for time travel: {e}")
                formatter = self.template_manager.get_formatter('short_sale')
                alert_data = formatter.format_changes_alert(new_alerts, ended_alerts)
                result["discord_preview"] = alert_data
                result["intelligence_preview"] = {"error": str(e)}
            
            for _, row in new_alerts.iterrows():
                result["detected_changes"]["new_alert_details"].append({
                    "symbol": row['Symbol'], 
                    "security_name": row.get('Security Name', ''),
                    "trigger_time": f"{row['Trigger Date']} {row['Trigger Time']}",
                    "is_vip": row['Symbol'] in self.vip_symbols
                })
        
        else:
            if not ended_alerts.empty:
                formatter = self.template_manager.get_formatter('short_sale')
                alert_data = formatter.format_changes_alert(new_alerts, ended_alerts)
                result["discord_preview"] = alert_data
        
        return result
    
    def _clean_dataframe_for_intelligence(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean DataFrame to ensure it works with intelligence analysis"""
        clean_df = df.copy()
        
        temp_columns = ['UniqueKey', 'trigger_datetime', '_merge']
        for col in temp_columns:
            if col in clean_df.columns:
                clean_df = clean_df.drop(columns=[col])
        
        required_columns = ['Symbol', 'Trigger Date', 'Trigger Time', 'Security Name']
        missing_columns = [col for col in required_columns if col not in clean_df.columns]
        
        if missing_columns:
            logging.warning(f"Missing columns for intelligence analysis: {missing_columns}")
            for col in missing_columns:
                clean_df[col] = ''
        
        return clean_df
    
    def _create_intelligent_alert_preview(self, new_breakers_df: pd.DataFrame, 
                                        ended_breakers_df: pd.DataFrame, 
                                        intelligent_results: List[Dict],
                                        enhanced_manager) -> Dict:
        """
        Create alert preview with intelligence enhancements for time travel testing
        """
        try:
            formatter = self.template_manager.get_formatter('short_sale')
            alert_data = formatter.format_changes_alert(new_breakers_df, ended_breakers_df)
            
            if intelligent_results:
                enhanced_message = enhanced_manager._enhance_alert_message(alert_data['message'], intelligent_results)
                alert_data['message'] = enhanced_message
                alert_data['color'] = enhanced_manager._determine_alert_color(intelligent_results)
                alert_data['title'] = enhanced_manager._enhance_alert_title(alert_data['title'], intelligent_results)
            
            return alert_data
            
        except Exception as e:
            logging.error(f"Error creating intelligent alert preview: {e}")
            formatter = self.template_manager.get_formatter('short_sale')
            return formatter.format_changes_alert(new_breakers_df, ended_breakers_df)
    
    def _format_simulation_results(self, target_time: datetime, before_state: pd.DataFrame,
                                  after_state: pd.DataFrame, new_alerts: pd.DataFrame,
                                  ended_alerts: pd.DataFrame) -> Dict[str, Any]:
        """
        Legacy format simulation results for backwards compatibility
        """
        return self._format_simulation_results_with_intelligence(
            target_time, before_state, after_state, new_alerts, ended_alerts
        )
    
    def get_suggested_test_times(self) -> list:
        """
        Suggest good test times based on current CBOE data with VIP prioritization
        """
        try:
            monitor = ShortSaleMonitor()
            current_data = monitor.fetch_data()
            
            if current_data is None or current_data.empty: 
                return []
            
            current_data['is_vip'] = current_data['Symbol'].isin(self.vip_symbols)
            recent_triggers = current_data.sort_values(['is_vip', 'Trigger Date'], ascending=[False, False]).head(20)
            
            suggestions = []
            seen_symbols = set()
            
            for _, row in recent_triggers.iterrows():
                try:
                    symbol = row['Symbol']
                    
                    if symbol in seen_symbols:
                        continue
                    seen_symbols.add(symbol)
                    
                    description = f"Test detection of {symbol} alert"
                    if symbol in self.vip_symbols:
                        description += " (VIP Symbol)"
                    
                    suggestions.append({
                        "test_time": f"{row['Trigger Date']} {row['Trigger Time']}",
                        "description": description,
                        "symbol": symbol,
                        "is_vip": symbol in self.vip_symbols
                    })
                    
                    if len(suggestions) >= 8:
                        break
                        
                except Exception as e:
                    logging.debug(f"Error processing suggestion for row: {e}")
                    continue
            
            return suggestions
            
        except Exception as e:
            logging.error(f"Error generating test suggestions: {e}")
            return []

    def get_intelligence_summary(self) -> Dict[str, Any]:
        """
        Get intelligence summary of current CBOE data for testing
        """
        try:
            monitor = ShortSaleMonitor()
            current_data = monitor.fetch_data()
            
            if current_data is None or current_data.empty:
                return {"error": "No data available"}
            
            vip_count = len(current_data[current_data['Symbol'].isin(self.vip_symbols)])
            total_symbols = len(current_data['Symbol'].unique())
            symbol_frequencies = current_data['Symbol'].value_counts()
            high_freq_symbols = symbol_frequencies[symbol_frequencies >= 15]
            
            return {
                "total_records": len(current_data),
                "unique_symbols": total_symbols,
                "vip_symbols_active": vip_count,
                "high_frequency_symbols": len(high_freq_symbols),
                "top_frequency_symbols": symbol_frequencies.head(5).to_dict(),
                "vip_symbols_found": [symbol for symbol in self.vip_symbols if symbol in current_data['Symbol'].values]
            }
            
        except Exception as e:
            logging.error(f"Error getting intelligence summary: {e}")
            return {"error": str(e)}

# This function's signature has been updated to accept a datetime object
def run_time_travel_test(target_time: datetime, vip_symbols=None) -> Dict[str, Any]:
    """
    Convenience function to run a time travel test with intelligence
    """
    tester = TimeTravelTester(vip_symbols=vip_symbols)
    return tester.simulate_historical_check(target_time)


def get_test_suggestions(vip_symbols=None) -> list:
    """
    Get suggested test times based on recent CBOE data with VIP prioritization
    """
    tester = TimeTravelTester(vip_symbols=vip_symbols)
    return tester.get_suggested_test_times()


def get_intelligence_test_summary(vip_symbols=None) -> Dict[str, Any]:
    """
    Get intelligence summary for testing purposes
    """
    tester = TimeTravelTester(vip_symbols=vip_symbols)
    return tester.get_intelligence_summary()