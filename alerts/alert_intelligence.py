"""
Alert Intelligence Engine
Analyzes circuit breaker alerts for frequency, double mint patterns, and priority classification
"""

import pandas as pd
import re
from typing import Dict, List, Tuple
from datetime import datetime
import logging


class FrequencyAnalyzer:
    """Handles symbol frequency calculations from historical data"""
    
    @staticmethod
    def get_symbol_frequency(symbol: str, full_df: pd.DataFrame) -> int:
        """Count how many times this symbol appears in the dataset"""
        if full_df is None or full_df.empty:
            return 1
        
        frequency = len(full_df[full_df['Symbol'] == symbol])
        return max(frequency, 1)  # Minimum frequency is 1
    
    @staticmethod
    def get_frequency_tier(frequency: int) -> str:
        """Convert frequency to tier emoji"""
        if frequency >= 30:
            return "🚨🔥"  # Super hot
        elif frequency >= 20:
            return "🔥🔥"   # Very hot  
        elif frequency >= 15:
            return "🔥"     # Hot
        elif frequency >= 10:
            return "⚡"     # Active
        else:
            return "🔵"     # Standard


class DoubleMintDetector:
    """Detects same underlying asset activity on same day"""
    
    @staticmethod
    def extract_underlying_asset(symbol: str) -> str:
        """Extract the underlying asset from leveraged ETF symbols"""
        
        # Common patterns for T-Rex ETFs
        if symbol.startswith('TSL'):  # TSLT, TSLZ
            return 'TSLA'
        elif symbol.startswith('NVD'):  # NVDX, NVDQ
            return 'NVDA'
        elif symbol.startswith('MST'):  # MSTU, MSTZ
            return 'MSTR'
        elif symbol.startswith('ETU') or symbol.startswith('ETQ') or symbol.startswith('ETHU'):
            return 'ETH'
        elif symbol.startswith('BTC') or symbol.startswith('BITX'):
            return 'BTC'
        elif symbol.startswith('ROB'):  # ROBN
            return 'HOOD'
        elif symbol.startswith('QBT') or symbol.startswith('QUB'):  # QBTX, QUBX
            return 'QUANTUM'
        elif symbol.startswith('ARM'):  # ARMU
            return 'ARM'
        elif symbol.startswith('RBL'):  # RBLU
            return 'RBLX'
        elif symbol.startswith('PLT'):  # PLTW
            return 'PLTR'
        elif symbol.startswith('DJT'):  # DJTU
            return 'DJT'
        elif symbol.startswith('UVI') or symbol.startswith('SVIX'):  # UVIX, UVXY
            return 'VIX'
        
        # CRWV patterns (the missing ones!)
        elif symbol.startswith('CWV') or symbol.startswith('CRWU'):  # CWVX, CRWU
            return 'CRWV'
        
        # SMR patterns 
        elif symbol.startswith('SMU') or symbol.startswith('SMUP'):  # SMU, SMUP
            return 'SMR'
        
        # Generic pattern matching for other cases
        elif len(symbol) >= 4:
            # Try to extract base from common patterns like ABCX, ABCU, ABCZ
            base = symbol[:-1]  # Remove last character
            if base.endswith('P') or base.endswith('U') or base.endswith('T') or base.endswith('Z'):
                return base[:-1]  # Remove suffix like P, U, T, Z
            return base
        
        # If no pattern matches, return the symbol itself
        return symbol
    
    @staticmethod
    def detect_double_mint(symbol: str, trigger_date: str, full_df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        Detect if same underlying asset has multiple circuit breakers on same day
        Returns (is_double_mint, list_of_related_symbols)
        """
        if full_df is None or full_df.empty:
            return False, []
        
        underlying = DoubleMintDetector.extract_underlying_asset(symbol)
        
        # Find all symbols with same underlying on same date
        same_date_df = full_df[full_df['Trigger Date'] == trigger_date]
        
        related_symbols = []
        for _, row in same_date_df.iterrows():
            row_symbol = row['Symbol']
            row_underlying = DoubleMintDetector.extract_underlying_asset(row_symbol)
            
            if row_underlying == underlying and row_symbol != symbol:
                related_symbols.append(row_symbol)
        
        is_double_mint = len(related_symbols) > 0
        
        return is_double_mint, related_symbols


class PriorityClassifier:
    """Classifies alerts by trading importance and priority"""
    
    def __init__(self, vip_symbols: List[str]):
        self.vip_symbols = [s.upper() for s in vip_symbols]
    
    def classify_priority(self, symbol: str, frequency: int, is_double_mint: bool) -> str:
        """
        Classify alert priority based on symbol, frequency, and double mint status
        Returns: VIP, HIGH, STANDARD
        """
        symbol_upper = symbol.upper()
        
        # VIP symbols get VIP priority
        if symbol_upper in self.vip_symbols:
            return "VIP"
        
        # High frequency tickers get HIGH priority
        if frequency >= 15:
            return "HIGH"
        
        # Double mint gets elevated priority
        if is_double_mint and frequency >= 5:
            return "HIGH"
        
        return "STANDARD"
    
    def get_priority_emoji(self, priority: str) -> str:
        """Get emoji for priority level"""
        if priority == "VIP":
            return "💎"
        elif priority == "HIGH":
            return "🔥"
        else:
            return "🔵"


class AlertIntelligenceEngine:
    """
    Main intelligence engine that coordinates all analysis
    """
    
    def __init__(self, vip_symbols: List[str]):
        self.frequency_analyzer = FrequencyAnalyzer()
        self.double_mint_detector = DoubleMintDetector()
        self.priority_classifier = PriorityClassifier(vip_symbols)
        
        logging.info(f"AlertIntelligenceEngine initialized with VIP symbols: {vip_symbols}")
    
    def analyze_alert(self, symbol: str, trigger_date: str, full_df: pd.DataFrame) -> Dict:
        """
        Perform complete intelligence analysis on an alert
        
        Args:
            symbol: The circuit breaker symbol (e.g., 'TSLT')
            trigger_date: Date when circuit breaker triggered (e.g., '2025-08-12')
            full_df: Complete CBOE dataset for analysis
            
        Returns:
            Dict with intelligence analysis results
        """
        try:
            # Frequency analysis
            frequency = self.frequency_analyzer.get_symbol_frequency(symbol, full_df)
            frequency_tier = self.frequency_analyzer.get_frequency_tier(frequency)
            
            # Double mint detection
            is_double_mint, related_symbols = self.double_mint_detector.detect_double_mint(
                symbol, trigger_date, full_df
            )
            
            # Priority classification
            priority = self.priority_classifier.classify_priority(symbol, frequency, is_double_mint)
            priority_emoji = self.priority_classifier.get_priority_emoji(priority)
            
            # Build analysis summary
            summary_parts = [f"{frequency}x frequency"]
            if is_double_mint:
                summary_parts.append(f"🍃 Double Mint ({', '.join(related_symbols)})")
            
            analysis_summary = f"{frequency_tier} {' | '.join(summary_parts)}"
            
            # Build enhanced details
            underlying = self.double_mint_detector.extract_underlying_asset(symbol)
            enhanced_details = f"{priority_emoji} {symbol}"
            if underlying != symbol:
                enhanced_details += f" ({underlying})"
            enhanced_details += f" - {frequency}x"
            if is_double_mint:
                enhanced_details += " 🍃"
            
            result = {
                'frequency': frequency,
                'frequency_tier': frequency_tier,
                'is_double_mint': is_double_mint,
                'related_symbols': related_symbols,
                'underlying_asset': underlying,
                'priority': priority,
                'priority_emoji': priority_emoji,
                'analysis_summary': analysis_summary,
                'enhanced_details': enhanced_details
            }
            
            logging.info(f"Intelligence analysis for {symbol}: {priority} priority, {frequency}x frequency, double_mint={is_double_mint}")
            
            return result
            
        except Exception as e:
            logging.error(f"Error in intelligence analysis for {symbol}: {e}")
            # Return safe defaults
            return {
                'frequency': 1,
                'frequency_tier': '🔵',
                'is_double_mint': False,
                'related_symbols': [],
                'underlying_asset': symbol,
                'priority': 'STANDARD',
                'priority_emoji': '🔵',
                'analysis_summary': '1x frequency',
                'enhanced_details': f'🔵 {symbol} - 1x'
            }
    
    def analyze_batch(self, new_breakers_df: pd.DataFrame, full_df: pd.DataFrame) -> List[Dict]:
        """
        Analyze multiple alerts in batch
        
        Args:
            new_breakers_df: DataFrame of new circuit breakers to analyze
            full_df: Complete CBOE dataset for analysis
            
        Returns:
            List of intelligence analysis results
        """
        results = []
        
        for _, row in new_breakers_df.iterrows():
            symbol = row['Symbol']
            trigger_date = row['Trigger Date']
            
            analysis = self.analyze_alert(symbol, trigger_date, full_df)
            analysis['row_data'] = row.to_dict()  # Include original row data
            results.append(analysis)
        
        return results


# Utility functions for easy import
def create_intelligence_engine(vip_symbols: List[str]) -> AlertIntelligenceEngine:
    """Factory function to create intelligence engine"""
    return AlertIntelligenceEngine(vip_symbols)


def quick_analyze(symbol: str, trigger_date: str, full_df: pd.DataFrame, 
                 vip_symbols: List[str] = None) -> Dict:
    """Quick analysis function for single alerts"""
    if vip_symbols is None:
        vip_symbols = ['TSLA', 'NVDA', 'AAPL', 'MSTR', 'GME', 'AMC']
    
    engine = AlertIntelligenceEngine(vip_symbols)
    return engine.analyze_alert(symbol, trigger_date, full_df)