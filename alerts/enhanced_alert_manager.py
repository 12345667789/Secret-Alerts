"""
Enhanced Alert Manager with Intelligence
Extends the existing AlertManager to include frequency, double mint, and priority analysis
"""

import logging
import pandas as pd
from typing import Dict, List
from .alert_intelligence import AlertIntelligenceEngine


class EnhancedAlertManager:
    """
    Enhanced version of AlertManager that adds intelligence analysis
    Compatible with existing AlertManager interface
    """


    def _create_intelligent_alert_data(self, new_breakers_df: pd.DataFrame, 
                                      ended_breakers_df: pd.DataFrame, 
                                      intelligent_results: List[Dict]) -> Dict:
        """
        Create alert data with intelligence enhancements for time travel testing
        """
        try:
            # Generate the basic alert using existing template system
            formatter = self.template_manager.get_formatter('short_sale')
            alert_data = formatter.format_changes_alert(new_breakers_df, ended_breakers_df)
            
            # Enhance the alert with intelligence data
            if intelligent_results:
                enhanced_message = self._enhance_alert_message(alert_data['message'], intelligent_results)
                alert_data['message'] = enhanced_message
                
                # Adjust color based on priority
                alert_data['color'] = self._determine_alert_color(intelligent_results)
                
                # Enhance title with priority indicators
                alert_data['title'] = self._enhance_alert_title(alert_data['title'], intelligent_results)
            
            return alert_data
            
        except Exception as e:
            logging.error(f"Error creating intelligent alert data: {e}")
            # Fallback to basic alert
            formatter = self.template_manager.get_formatter('short_sale')
            return formatter.format_changes_alert(new_breakers_df, ended_breakers_df)
    
    
    def __init__(self, discord_client, template_manager, vip_symbols: List[str]):
        self.discord_client = discord_client
        self.template_manager = template_manager
        self.intelligence_engine = AlertIntelligenceEngine(vip_symbols)
        self.vip_symbols = vip_symbols
        
        logging.info(f"EnhancedAlertManager initialized with {len(vip_symbols)} VIP symbols")
    
    def send_formatted_alert(self, alert_data: Dict) -> bool:
        """
        Send alert using existing interface (backwards compatible)
        This maintains compatibility with existing code
        """
        return self.discord_client.send_alert(
            title=alert_data['title'],
            message=alert_data['message'],
            color=alert_data['color']
        )
    
    def send_intelligent_alert(self, new_breakers_df: pd.DataFrame, ended_breakers_df: pd.DataFrame, 
                              full_df: pd.DataFrame, health_monitor) -> bool:
        """
        Send alerts with intelligence analysis
        
        Args:
            new_breakers_df: New circuit breakers detected
            ended_breakers_df: Circuit breakers that ended
            full_df: Complete CBOE dataset for frequency analysis
            health_monitor: Health monitor instance for recording alerts
            
        Returns:
            bool: Success status
        """
        try:
            # Analyze new breakers with intelligence
            intelligent_results = []
            if not new_breakers_df.empty:
                intelligent_results = self.intelligence_engine.analyze_batch(new_breakers_df, full_df)
            
            # Create enhanced alert using existing template system
            formatter = self.template_manager.get_formatter('short_sale')
            
            # Generate the basic alert (maintains existing functionality)
            alert_data = formatter.format_changes_alert(new_breakers_df, ended_breakers_df)
            
            # Enhance the alert with intelligence data
            if intelligent_results:
                enhanced_message = self._enhance_alert_message(alert_data['message'], intelligent_results)
                alert_data['message'] = enhanced_message
                
                # Adjust color based on priority
                alert_data['color'] = self._determine_alert_color(intelligent_results)
                
                # Enhance title with priority indicators
                alert_data['title'] = self._enhance_alert_title(alert_data['title'], intelligent_results)
            
            # Send the enhanced alert
            success = self.send_formatted_alert(alert_data)
            
            # Record alerts with intelligence data
            if success:
                self._record_intelligent_alerts(intelligent_results, ended_breakers_df, health_monitor)
            
            return success
            
        except Exception as e:
            logging.error(f"Error in send_intelligent_alert: {e}")
            # Fallback to basic alert
            formatter = self.template_manager.get_formatter('short_sale')
            alert_data = formatter.format_changes_alert(new_breakers_df, ended_breakers_df)
            return self.send_formatted_alert(alert_data)
    
    def _enhance_alert_message(self, original_message: str, intelligent_results: List[Dict]) -> str:
        """Enhance alert message with intelligence data"""
        
        if not intelligent_results:
            return original_message
        
        # Separate by priority
        vip_alerts = [r for r in intelligent_results if r['priority'] == 'VIP']
        high_alerts = [r for r in intelligent_results if r['priority'] == 'HIGH']
        double_mint_alerts = [r for r in intelligent_results if r['is_double_mint']]
        
        enhancement = ""
        
        # Add VIP section
        if vip_alerts:
            enhancement += "\n\n💎 **VIP ALERTS:**\n"
            for result in vip_alerts:
                enhancement += f"• {result['enhanced_details']}\n"
        
        # Add Double Mint section
        if double_mint_alerts:
            enhancement += "\n\n🍃 **DOUBLE MINT ALERTS:**\n"
            for result in double_mint_alerts:
                related = ', '.join(result['related_symbols'])
                enhancement += f"• {result['priority_emoji']} {result['row_data']['Symbol']} + {related} ({result['underlying_asset']})\n"
        
        # Add High Frequency section
        high_freq_alerts = [r for r in intelligent_results if r['frequency'] >= 20]
        if high_freq_alerts:
            enhancement += "\n\n🔥 **HIGH FREQUENCY:**\n"
            for result in high_freq_alerts:
                enhancement += f"• {result['frequency_tier']} {result['row_data']['Symbol']} ({result['frequency']}x this year)\n"
        
        return original_message + enhancement
    
    def _determine_alert_color(self, intelligent_results: List[Dict]) -> int:
        """Determine alert color based on intelligence priority"""
        
        if not intelligent_results:
            return 0x0099FF  # Blue (default)
        
        # VIP gets gold
        if any(r['priority'] == 'VIP' for r in intelligent_results):
            return 0xFFD700  # Gold
        
        # Double mint gets red
        if any(r['is_double_mint'] for r in intelligent_results):
            return 0xFF0000  # Red
        
        # High priority gets orange
        if any(r['priority'] == 'HIGH' for r in intelligent_results):
            return 0xFF8C00  # Orange
        
        return 0x0099FF  # Blue (standard)
    
    def _enhance_alert_title(self, original_title: str, intelligent_results: List[Dict]) -> str:
        """Enhance alert title with priority indicators"""
        
        if not intelligent_results:
            return original_title
        
        indicators = []
        
        # Count priority types
        vip_count = sum(1 for r in intelligent_results if r['priority'] == 'VIP')
        double_mint_count = sum(1 for r in intelligent_results if r['is_double_mint'])
        high_freq_count = sum(1 for r in intelligent_results if r['frequency'] >= 20)
        
        if vip_count > 0:
            indicators.append(f"💎 {vip_count} VIP")
        
        if double_mint_count > 0:
            indicators.append(f"🍃 {double_mint_count} Double Mint")
        
        if high_freq_count > 0:
            indicators.append(f"🔥 {high_freq_count} High Freq")
        
        if indicators:
            return f"{original_title} ({' | '.join(indicators)})"
        
        return original_title
    
    def _record_intelligent_alerts(self, intelligent_results: List[Dict], ended_breakers_df: pd.DataFrame, 
                                 health_monitor):
        """Record alerts with intelligence data in the health monitor"""
        
        # Record new breakers with intelligence
        for result in intelligent_results:
            row_data = result['row_data']
            alert_id = f"{row_data['Symbol']}-{row_data['Trigger Date']}-{row_data['Trigger Time']}".replace(' ', '_').replace(':', '')
            
            enhanced_details = f"Trigger: {row_data['Trigger Time']} | {result['analysis_summary']}"
            
            # Use enhanced record_alert_sent if available, otherwise fall back to original
            if hasattr(health_monitor, 'record_alert_sent_enhanced'):
                health_monitor.record_alert_sent_enhanced(
                    alert_id=alert_id,
                    alert_type="NEW_BREAKER",
                    symbol=row_data['Symbol'],
                    details=enhanced_details,
                    frequency=result['frequency'],
                    double_mint=result['is_double_mint'],
                    priority=result['priority']
                )
            else:
                # Fallback to original method
                health_monitor.record_alert_sent(
                    alert_id=alert_id,
                    alert_type="NEW_BREAKER",
                    symbol=row_data['Symbol'],
                    details=enhanced_details
                )
        
        # Record ended breakers (without intelligence for now)
        for _, row in ended_breakers_df.iterrows():
            alert_id = f"{row['Symbol']}-{row['Trigger Date']}-{row['Trigger Time']}-END".replace(' ', '_').replace(':', '')
            
            if hasattr(health_monitor, 'record_alert_sent_enhanced'):
                health_monitor.record_alert_sent_enhanced(
                    alert_id=alert_id,
                    alert_type="ENDED_BREAKER",
                    symbol=row['Symbol'],
                    details=f"Ended: {row['End Time']}",
                    frequency=1,  # Default for ended alerts
                    double_mint=False,
                    priority="STANDARD"
                )
            else:
                health_monitor.record_alert_sent(
                    alert_id=alert_id,
                    alert_type="ENDED_BREAKER",
                    symbol=row['Symbol'],
                    details=f"Ended: {row['End Time']}"
                )
    
    def get_intelligence_summary(self, full_df: pd.DataFrame) -> Dict:
        """Get summary of current intelligence state"""
        if full_df is None or full_df.empty:
            return {
                'total_symbols': 0,
                'high_frequency_count': 0,
                'vip_active': 0,
                'double_mint_potential': 0
            }
        
        # Get frequency analysis
        symbol_frequencies = full_df['Symbol'].value_counts()
        high_frequency_symbols = symbol_frequencies[symbol_frequencies >= 15]
        
        # Check VIP activity
        vip_active = 0
        for vip_symbol in self.vip_symbols:
            if vip_symbol in symbol_frequencies:
                vip_active += 1
        
        return {
            'total_symbols': len(symbol_frequencies),
            'high_frequency_count': len(high_frequency_symbols),
            'vip_active': vip_active,
            'double_mint_potential': len([s for s in symbol_frequencies.index if any(
                self.intelligence_engine.double_mint_detector.extract_underlying_asset(s) == 
                self.intelligence_engine.double_mint_detector.extract_underlying_asset(other) 
                for other in symbol_frequencies.index if s != other
            )])
        }


# Backwards compatibility function
def create_enhanced_alert_manager(discord_client, template_manager, vip_symbols: List[str]) -> EnhancedAlertManager:
    """Factory function for creating enhanced alert manager"""
    return EnhancedAlertManager(discord_client, template_manager, vip_symbols)


# For easy import and testing
if __name__ == "__main__":
    # Test the intelligence engine
    import pandas as pd
    
    # Sample data for testing
    test_data = {
        'Symbol': ['TSLT', 'TSLZ', 'NVDX', 'MSTU'],
        'Trigger Date': ['2025-08-12', '2025-08-12', '2025-08-11', '2025-08-12'],
        'Trigger Time': ['09:30:00', '14:15:00', '10:00:00', '11:30:00'],
        'Security Name': ['T-Rex 2X Long Tesla', 'T-Rex 2X Inverse Tesla', 'T-Rex 2X Long NVIDIA', 'T-Rex 2X Long MSTR']
    }
    
    test_df = pd.DataFrame(test_data)
    vip_symbols = ['TSLA', 'NVDA', 'MSTR']
    
    # Test intelligence analysis
    from .alert_intelligence import AlertIntelligenceEngine
    engine = AlertIntelligenceEngine(vip_symbols)
    
    result = engine.analyze_alert('TSLT', '2025-08-12', test_df)
    print("Test result:", result)