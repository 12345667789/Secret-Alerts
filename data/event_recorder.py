# ===============================================
# data/event_recorder.py
# ===============================================

"""
Event recording system for capturing trading events
"""

from datetime import datetime, timedelta
import json
from typing import Dict

from utils.logger import logger

class EventRecorder:
    """Records trading events and triggers data collection"""
    
    def __init__(self, config):
        self.config = config
        self.market_data_client = None  # Will be set by main system
        self.storage_manager = None     # Will be set by main system
    
    def record_circuit_breaker_event(self, match_data: Dict):
        """Record a circuit breaker event and trigger data collection"""
        symbol = match_data['symbol']
        event_time = datetime.now()
        
        logger.info(f"Recording circuit breaker event for {symbol}", "EVENT_RECORDER")
        
        # Create event record
        event_record = {
            'event_id': f"{symbol}_{event_time.strftime('%Y%m%d_%H%M%S')}",
            'event_type': 'circuit_breaker',
            'symbol': symbol,
            'security_name': match_data['security_name'],
            'trigger_time': match_data['trigger_time'],
            'detection_time': event_time.isoformat(),
            'exchange': match_data['exchange'],
            'raw_data': match_data['row_data']
        }
        
        # Trigger data collection (placeholder for future implementation)
        if self.market_data_client:
            self._collect_event_data(event_record)
        
        # Store event record (placeholder for future implementation)
        if self.storage_manager:
            self.storage_manager.store_event(event_record)
        
        return event_record
    
    def _collect_event_data(self, event_record: Dict):
        """Collect market data around the event (placeholder)"""
        symbol = event_record['symbol']
        event_time = datetime.fromisoformat(event_record['detection_time'])
        
        # Collect data from 30 minutes before to 2 hours after
        start_time = event_time - timedelta(minutes=30)
        end_time = event_time + timedelta(hours=2)
        
        logger.info(f"Collecting market data for {symbol} event", "EVENT_RECORDER")
        
        # This will be implemented when we add the market data client
        # self.market_data_client.collect_candles(symbol, start_time, end_time)