"""
Centralized logging for the Secret_Alerts Trading System
"""

import logging
import sys
from datetime import datetime
from typing import Optional

class Logger:
    """Enhanced logging system for Secret_Alerts"""
    
    def __init__(self, name: str = "Secret_Alerts"):
        self.logger = logging.getLogger(name)
        self.setup_logging()
    
    def setup_logging(self):
        """Configure logging format and handlers"""
        if not self.logger.handlers:
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
            self.logger.setLevel(logging.INFO)
    
    def info(self, message: str, module: Optional[str] = None):
        """Log info message with optional module prefix"""
        if module:
            message = f"[{module}] {message}"
        self.logger.info(message)
        print(f"[INFO] {message}")  # Also print for immediate visibility
    
    def error(self, message: str, module: Optional[str] = None):
        """Log error message with optional module prefix"""
        if module:
            message = f"[{module}] {message}"
        self.logger.error(message)
        print(f"[ERROR] {message}")
    
    def warning(self, message: str, module: Optional[str] = None):
        """Log warning message with optional module prefix"""
        if module:
            message = f"[{module}] {message}"
        self.logger.warning(message)
        print(f"[WARNING] {message}")
    
    def debug(self, message: str, module: Optional[str] = None):
        """Log debug message with optional module prefix"""
        if module:
            message = f"[{module}] {message}"
        self.logger.debug(message)

# Global logger instance
logger = Logger()