"""
Alert template system for formatting different types of notifications.
"""
import pandas as pd
import pytz
from datetime import datetime
from typing import List, Dict, Any, Optional


class AlertFormatter:
    """Base class for formatting alerts"""
    
    def __init__(self, vip_symbols: List[str] = None):
        self.vip_symbols = vip_symbols or []
        self.cst = pytz.timezone('America/Chicago')
    
    def format_alert(self, *args, **kwargs) -> Dict[str, Any]:
        """Override in subclasses"""
        raise NotImplementedError


class ShortSaleAlertFormatter(AlertFormatter):
    """Formatter for short sale circuit breaker alerts"""
    
    def _extract_underlying_ticker(self, security_name: str) -> Optional[str]:
        """Extract underlying ticker from security name"""
        if pd.isna(security_name):
            return None
        
        words = str(security_name).upper().split()
        keywords = ['LONG', 'INVERSE']
        
        for keyword in keywords:
            if keyword in words:
                try:
                    idx = words.index(keyword)
                    if idx + 1 < len(words):
                        return words[idx + 1]
                except (ValueError, IndexError):
                    continue
        return None
    
    def _format_ticker_lines(self, df: pd.DataFrame, date_col: str, time_col: str, status_text: str) -> List[str]:
        """Format individual ticker lines for alerts"""
        if df.empty:
            return []
        
        # Add underlying ticker and VIP status
        df = df.copy()
        df['underlying'] = df['Security Name'].apply(self._extract_underlying_ticker)
        df['is_vip'] = df['Symbol'].isin(self.vip_symbols)
        
        # Sort by VIP status first, then chronologically
        df_sorted = df.sort_values(by=['is_vip', date_col, time_col], ascending=[False, False, False])
        
        # Format lines
        alert_lines = []
        today_str = datetime.now(self.cst).strftime('%Y-%m-%d')
        
        for _, row in df_sorted.iterrows():
            vip_marker = "⭐ " if row['is_vip'] else ""
            date_info = "Today" if row[date_col] == today_str else row[date_col]
            
            if pd.notnull(row['underlying']):
                line = f"• {vip_marker}**{row['underlying']}** (*{row['Symbol']}*) - {row['Security Name']} ({status_text} {date_info} at {row[time_col]})"
            else:
                line = f"• {vip_marker}**{row['Symbol']}** (*{row['Security Name']}*) ({status_text} {date_info} at {row[time_col]})"
            
            alert_lines.append(line)
        
        return alert_lines
    
    def format_changes_alert(self, new_breakers_df: pd.DataFrame, ended_breakers_df: pd.DataFrame) -> Dict[str, Any]:
        """Format alert for new and ended circuit breakers"""
        num_started = len(new_breakers_df)
        num_ended = len(ended_breakers_df)
        now_cst = datetime.now(self.cst)
        
        title = f"⚡ CBOE Changes: {num_started} Started, {num_ended} Ended"
        message_parts = [f"**CHANGES DETECTED at {now_cst.strftime('%-I:%M:%S %p CST')}**"]
        
        if not new_breakers_df.empty:
            started_lines = self._format_ticker_lines(
                new_breakers_df, 'Trigger Date', 'Trigger Time', 'Started'
            )
            message_parts.append(f"🆕 **{num_started} STARTED:**")
            message_parts.extend(started_lines)
            message_parts.append("")  # Empty line
        
        if not ended_breakers_df.empty:
            ended_lines = self._format_ticker_lines(
                ended_breakers_df, 'End Date', 'End Time', 'Ended'
            )
            message_parts.append(f"✅ **{num_ended} ENDED:**")
            message_parts.extend(ended_lines)
        
        return {
            'title': title,
            'message': '\n'.join(message_parts),
            'color': 0xffa500  # Orange for changes
        }
    
    def format_open_alerts_report(self, open_alerts_df: pd.DataFrame) -> Dict[str, Any]:
        """Format report of all open circuit breakers"""
        if open_alerts_df.empty:
            return {
                'title': "📊 Open Alerts Report",
                'message': "No open short sale circuit breakers found at this time.",
                'color': 0x28a745  # Green for all clear
            }
        
        alert_lines = self._format_ticker_lines(
            open_alerts_df, 'Trigger Date', 'Trigger Time', 'Started'
        )
        
        return {
            'title': f"📊 Open Circuit Breaker Report ({len(open_alerts_df)} Found)",
            'message': '\n'.join(alert_lines),
            'color': 0x0099ff  # Blue for info
        }
    
    def format_scheduled_report(self, report_type: str, open_alerts_df: pd.DataFrame, 
                              total_today: int = 0, ended_today: int = 0) -> Dict[str, Any]:
        """Format scheduled summary reports (morning, market check, welcome)"""
        now_cst = datetime.now(self.cst)
        
        # Different titles and colors based on report type
        report_configs = {
            'morning': {
                'emoji': '🌅',
                'title_suffix': 'Good Morning Summary',
                'time_format': '%-I:%M %p CST',
                'color': 0xFFD700  # Gold
            },
            'market_check': {
                'emoji': '📊',
                'title_suffix': 'Market Check',
                'time_format': '%-I:%M %p CST',
                'color': 0x00BFFF  # Blue
            },
            'welcome': {
                'emoji': '🌙',
                'title_suffix': 'Welcome Alert',
                'time_format': '%-I:%M %p CST',
                'color': 0x9932CC  # Purple
            }
        }
        
        config = report_configs.get(report_type, report_configs['market_check'])
        
        title = f"{config['emoji']} {config['title_suffix']} - {now_cst.strftime('%B %d, %Y')}"
        
        message_parts = [
            f"**{config['title_suffix']} at {now_cst.strftime(config['time_format'])}**",
            ""
        ]
        
        # Add daily stats if provided
        if total_today > 0 or ended_today > 0:
            message_parts.extend([
                f"📈 **Today's Activity:**",
                f"• Total triggered: {total_today}",
                f"• Ended: {ended_today}",
                f"• Currently open: {total_today - ended_today}",
                ""
            ])
        
        # Add current open alerts
        if open_alerts_df.empty:
            message_parts.append("✅ **Current Status:** No open circuit breakers")
        else:
            alert_lines = self._format_ticker_lines(
                open_alerts_df, 'Trigger Date', 'Trigger Time', 'Started'
            )
            message_parts.append(f"🔴 **{len(open_alerts_df)} Currently Open:**")
            message_parts.extend(alert_lines)
        
        return {
            'title': title,
            'message': '\n'.join(message_parts),
            'color': config['color']
        }


class VolumeAlertFormatter(AlertFormatter):
    """Formatter for volume-based alerts (for future use)"""
    
    def format_volume_spike_alert(self, ticker: str, volume_data: Dict) -> Dict[str, Any]:
        """Format volume spike alert"""
        is_vip = ticker in self.vip_symbols
        vip_marker = "⭐ VIP " if is_vip else ""
        
        title = f"📈 {vip_marker}Volume Spike: {ticker}"
        message = f"**{ticker}** is experiencing unusual volume activity"
        
        return {
            'title': title,
            'message': message,
            'color': 0xFFD700 if is_vip else 0x00BFFF
        }


class PriceAlertFormatter(AlertFormatter):
    """Formatter for price-based alerts (for future use)"""
    
    def format_price_movement_alert(self, ticker: str, price_data: Dict) -> Dict[str, Any]:
        """Format price movement alert"""
        is_vip = ticker in self.vip_symbols
        vip_marker = "⭐ VIP " if is_vip else ""
        
        title = f"💰 {vip_marker}Price Alert: {ticker}"
        message = f"**{ticker}** has significant price movement"
        
        return {
            'title': title,
            'message': message,
            'color': 0xFFD700 if is_vip else 0xFF4500
        }


class AlertTemplateManager:
    """Central manager for all alert formatters"""
    
    def __init__(self, vip_symbols: List[str] = None):
        self.vip_symbols = vip_symbols or []
        
        # Initialize formatters
        self.short_sale = ShortSaleAlertFormatter(vip_symbols)
        self.volume = VolumeAlertFormatter(vip_symbols)
        self.price = PriceAlertFormatter(vip_symbols)
    
    def get_formatter(self, alert_type: str) -> AlertFormatter:
        """Get the appropriate formatter for an alert type"""
        formatters = {
            'short_sale': self.short_sale,
            'volume': self.volume,
            'price': self.price
        }
        
        if alert_type not in formatters:
            raise ValueError(f"Unknown alert type: {alert_type}")
        
        return formatters[alert_type]