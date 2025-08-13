# services/alert_batcher.py

import logging
import pandas as pd
import threading
import pytz
from collections import defaultdict
from datetime import datetime

# --- Smart Alert Batching System ---
class SmartAlertBatcher:
    """
    Intelligent alert batching to maximize double mint detection accuracy
    """

    def __init__(self, health_monitor, enhanced_alert_manager):
        self.health_monitor = health_monitor
        self.alert_manager = enhanced_alert_manager
        self.pending_alerts = defaultdict(list)
        self.batch_timers = {}
        self.cst = pytz.timezone('America/Chicago')

    def get_batch_window(self) -> int:
        """Get appropriate batch window based on market conditions"""

        # FIXED: Properly get CST time
        cst = pytz.timezone('America/Chicago')
        now_cst = datetime.now(cst)
        current_time = now_cst.time()

        # Import time class explicitly to avoid conflicts
        from datetime import time as dt_time

        # Rush hour: 9:20-10:00 AM (peak circuit breaker activity)
        rush_start = dt_time(9, 20)
        rush_end = dt_time(10, 0)

        # Market hours: 9:30 AM - 4:00 PM
        market_start = dt_time(9, 30)
        market_end = dt_time(16, 0)

        # Pre-market starts at 8:00 AM
        premarket_start = dt_time(8, 0)

        # Debug logging to see what's happening
        logging.info(f"Current CST time: {now_cst.strftime('%H:%M:%S')}")
        logging.info(f"Time check - Rush: {rush_start} <= {current_time} <= {rush_end}")

        if rush_start <= current_time <= rush_end:
            logging.info("🔥 RUSH HOUR MODE activated")
            return 90  # 90 seconds during rush hour
        elif market_start <= current_time <= market_end:
            logging.info("📈 MARKET HOURS MODE activated")
            return 45  # 45 seconds during normal market hours
        elif premarket_start <= current_time < rush_start:
            logging.info("🌅 PRE-MARKET MODE activated")
            return 30  # 30 seconds during pre-market
        else:
            logging.info("🌙 AFTER HOURS MODE activated")
            return 15  # 15 seconds after hours

    def should_bypass_batching(self, new_breakers_df) -> bool:
        """Check if alert should bypass batching (emergency situations)"""
        if new_breakers_df.empty:
            return False

        # FIXED: Properly get CST time
        cst = pytz.timezone('America/Chicago')
        now_cst = datetime.now(cst)
        current_time = now_cst.time()

        # Import time class explicitly
        from datetime import time as dt_time

        # Define after hours correctly
        after_hours_start = dt_time(20, 0)  # 8:00 PM
        after_hours_end = dt_time(8, 0)     # 8:00 AM

        # Check if truly after hours (8 PM to 8 AM)
        if current_time >= after_hours_start or current_time < after_hours_end:
            vip_symbols = ['TSLA', 'NVDA', 'AAPL', 'MSTR', 'GME', 'AMC']
            has_vip = any(symbol in vip_symbols for symbol in new_breakers_df['Symbol'])
            if has_vip:
                logging.info("🚨 VIP symbol detected after hours - bypassing batch")
                return True

        return False

    def queue_alert(self, new_breakers_df, ended_breakers_df, full_df):
        """
        Queue alert for intelligent batching instead of sending immediately
        """
        # Check if we should bypass batching for critical alerts
        if self.should_bypass_batching(new_breakers_df):
            logging.info("🚨 Critical alert detected - bypassing batching")
            success = self.alert_manager.send_intelligent_alert(
                new_breakers_df=new_breakers_df,
                ended_breakers_df=ended_breakers_df,
                full_df=full_df,
                health_monitor=self.health_monitor
            )
            return success

        batch_window = self.get_batch_window()
        current_time = datetime.now()

        # Create batch key based on time window
        batch_key = int(current_time.timestamp() // batch_window) * batch_window

        # Add to pending alerts
        self.pending_alerts[batch_key].append({
            'new_breakers': new_breakers_df,
            'ended_breakers': ended_breakers_df,
            'full_df': full_df,
            'timestamp': current_time
        })

        # Set timer for this batch if not already set
        if batch_key not in self.batch_timers:
            timer = threading.Timer(
                batch_window,
                self._process_batch,
                args=[batch_key]
            )
            timer.start()
            self.batch_timers[batch_key] = timer

            logging.info(f"🕐 Batching alert for {batch_window}s to detect double mints")

    def _process_batch(self, batch_key):
        """Process a batch of alerts after the wait period"""
        if batch_key not in self.pending_alerts:
            return

        alerts_in_batch = self.pending_alerts[batch_key]
        del self.pending_alerts[batch_key]
        del self.batch_timers[batch_key]

        if not alerts_in_batch:
            return

        logging.info(f"🃏 Processing batch of {len(alerts_in_batch)} alerts")

        # Combine all alerts in the batch
        all_new_breakers = pd.concat([alert['new_breakers'] for alert in alerts_in_batch if not alert['new_breakers'].empty], ignore_index=True)
        all_ended_breakers = pd.concat([alert['ended_breakers'] for alert in alerts_in_batch if not alert['ended_breakers'].empty], ignore_index=True)

        # Use the most recent full_df
        latest_full_df = alerts_in_batch[-1]['full_df']

        # Remove duplicates
        if not all_new_breakers.empty:
            all_new_breakers = all_new_breakers.drop_duplicates(subset=['Symbol', 'Trigger Date', 'Trigger Time'])
        if not all_ended_breakers.empty:
            all_ended_breakers = all_ended_breakers.drop_duplicates(subset=['Symbol', 'Trigger Date', 'Trigger Time'])

        # Send the combined intelligent alert
        if not all_new_breakers.empty or not all_ended_breakers.empty:
            success = self.alert_manager.send_intelligent_alert(
                new_breakers_df=all_new_breakers,
                ended_breakers_df=all_ended_breakers,
                full_df=latest_full_df,
                health_monitor=self.health_monitor
            )

            if success:
                batch_size = len(all_new_breakers) + len(all_ended_breakers)
                logging.info(f"✅ Batched intelligent alert sent successfully ({batch_size} total alerts)")
            else:
                logging.error("❌ Failed to send batched intelligent alert")