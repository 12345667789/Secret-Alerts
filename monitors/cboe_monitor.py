import os
import logging
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import json

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ShortSaleMonitor:
    """
    Monitors the CBOE for new and ended short sale circuit breakers.
    """
    def __init__(self):
        """
        Initializes the monitor for short sale circuit breakers.
        """
        self.csv_url = "https://www.cboe.com/us/equities/market_statistics/short_sale_circuit_breakers/downloads/BatsCircuitBreakers2025.csv"
        self.user_agent = "Mozilla/5.0 (Windows NT 1.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        
        try:
            self.db = firestore.Client()
            self.doc_ref = self.db.collection('short_sale_monitor_state').document('previous_breakers')
            logging.info("Successfully connected to Firestore for Short Sale Monitor.")
        except Exception as e:
            logging.critical(f"Failed to connect to Firestore: {e}")
            raise
            
        self.previous_df = self._load_state_from_firestore()

    def _load_state_from_firestore(self):
        """Loads the last saved DataFrame from Firestore."""
        try:
            doc = self.doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                df = pd.DataFrame.from_dict(data)
                logging.info(f"Successfully loaded previous state. {len(df)} records found.")
                
                # Debug: Show some sample unique keys
                if not df.empty and 'UniqueKey' in df.columns:
                    sample_keys = df['UniqueKey'].head(3).tolist()
                    logging.info(f"Sample previous unique keys: {sample_keys}")
                
                return df
            else:
                logging.warning("No previous short sale state found in Firestore. Starting fresh.")
                return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error loading state from Firestore: {e}. Starting with an empty state.")
            return pd.DataFrame()

    def _save_state_to_firestore(self, df_to_save):
        """Saves the given DataFrame to Firestore."""
        if df_to_save.empty:
            logging.warning("Attempted to save an empty DataFrame. Skipping save.")
            return
        try:
            data_to_store = df_to_save.astype(object).to_dict('list')
            
            # Debug: Log how many records we're saving
            logging.info(f"Saving {len(df_to_save)} records to Firestore")
            if 'UniqueKey' in df_to_save.columns:
                sample_keys = df_to_save['UniqueKey'].head(3).tolist()
                logging.info(f"Sample saved unique keys: {sample_keys}")
            
            self.doc_ref.set(data_to_store)
            logging.info(f"Successfully saved {len(df_to_save)} short sale records to Firestore.")
        except Exception as e:
            logging.error(f"Could not save state to Firestore: {e}")

    def fetch_data(self):
        """
        Fetches the short sale circuit breaker CSV.
        """
        try:
            logging.info(f"Fetching data from {self.csv_url}")
            headers = {
                'User-Agent': self.user_agent,
                'Referer': 'https://www.cboe.com/us/equities/market_statistics/short_sale_circuit_breakers/'
            }
            df = pd.read_csv(self.csv_url, storage_options=headers)
            df.columns = df.columns.str.strip()
            
            logging.info(f"Successfully fetched {len(df)} records from CBOE")
            logging.info(f"Columns available: {df.columns.tolist()}")
            
            return df
        except Exception as e:
            logging.error(f"Error fetching or parsing CSV data: {e}")
            return None

    def process_data(self, df):
        """
        Processes the raw DataFrame from the short sale CSV.
        """
        if df is None:
            logging.warning("Cannot process None DataFrame")
            return pd.DataFrame()
        
        if df.empty:
            logging.warning("Cannot process empty DataFrame")
            return pd.DataFrame()
        
        required_columns = ['Symbol', 'Trigger Date', 'Trigger Time']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"Missing one or more required columns. Available columns: {df.columns.tolist()}")
            return pd.DataFrame()

        # Create a unique key based on the trigger event
        df['UniqueKey'] = df['Symbol'].astype(str) + "_" + df['Trigger Date'].astype(str) + "_" + df['Trigger Time'].astype(str)
        
        # Debug: Show some sample processed data
        sample_data = df[['Symbol', 'Trigger Date', 'Trigger Time', 'UniqueKey']].head(3)
        logging.info(f"Sample processed data:\n{sample_data.to_string()}")
        
        # Debug: Check for records without End Time (currently open)
        open_count = df[pd.isnull(df['End Time'])].shape[0] if 'End Time' in df.columns else 0
        closed_count = df[pd.notnull(df['End Time'])].shape[0] if 'End Time' in df.columns else 0
        logging.info(f"Current data: {open_count} open breakers, {closed_count} closed breakers")
        
        return df

    def check_for_new_and_ended_breakers(self):
        """
        Main logic to find both new and recently ended circuit breakers.
        Returns two DataFrames: (new_breakers, ended_breakers).
        """
        logging.info("Starting check for new and ended short sale circuit breakers...")
        current_df_raw = self.fetch_data()
        current_df = self.process_data(current_df_raw)
        
        new_breakers = pd.DataFrame()
        ended_breakers = pd.DataFrame()

        if current_df.empty:
            logging.warning("Current short sale data is empty. Skipping check.")
            return new_breakers, ended_breakers

        if not self.previous_df.empty:
            logging.info("Comparing with previous data...")
            
            # Debug: Show comparison info
            current_keys = set(current_df['UniqueKey'].tolist())
            previous_keys = set(self.previous_df['UniqueKey'].tolist())
            
            logging.info(f"Current unique keys: {len(current_keys)}")
            logging.info(f"Previous unique keys: {len(previous_keys)}")
            
            # 1. Find NEW breakers (in current but not in previous)
            new_keys = current_keys - previous_keys
            if new_keys:
                new_breakers = current_df[current_df['UniqueKey'].isin(new_keys)].copy()
                logging.info(f"Found {len(new_breakers)} new breakers with keys: {list(new_keys)[:5]}")
                
                # Debug: Show details of new breakers
                if not new_breakers.empty:
                    sample_new = new_breakers[['Symbol', 'Security Name', 'Trigger Date', 'Trigger Time']].head(3)
                    logging.info(f"Sample new breakers:\n{sample_new.to_string()}")
            
            # 2. Find ENDED breakers - more robust approach
            # Look for breakers that were open in previous but now have End Time
            if 'End Time' in self.previous_df.columns and 'End Time' in current_df.columns:
                previously_open = self.previous_df[pd.isnull(self.previous_df['End Time'])].copy()
                currently_with_end_time = current_df[pd.notnull(current_df['End Time'])].copy()
                
                logging.info(f"Previously open: {len(previously_open)}")
                logging.info(f"Currently with end time: {len(currently_with_end_time)}")
                
                if not previously_open.empty and not currently_with_end_time.empty:
                    # Find breakers that were open before but now have an end time
                    ended_keys = set(previously_open['UniqueKey']) & set(currently_with_end_time['UniqueKey'])
                    
                    if ended_keys:
                        ended_breakers = currently_with_end_time[currently_with_end_time['UniqueKey'].isin(ended_keys)].copy()
                        logging.info(f"Found {len(ended_breakers)} ended breakers with keys: {list(ended_keys)[:5]}")
                        
                        # Debug: Show details of ended breakers
                        if not ended_breakers.empty:
                            sample_ended = ended_breakers[['Symbol', 'Security Name', 'End Date', 'End Time']].head(3)
                            logging.info(f"Sample ended breakers:\n{sample_ended.to_string()}")
            
            # Final summary
            if not new_breakers.empty:
                logging.info(f"--- {len(new_breakers)} New Circuit Breakers Detected ---")
                for _, row in new_breakers.head(5).iterrows():
                    logging.info(f"NEW: {row['Symbol']} triggered at {row['Trigger Date']} {row['Trigger Time']}")
            
            if not ended_breakers.empty:
                logging.info(f"--- {len(ended_breakers)} Ended Circuit Breakers Detected ---")
                for _, row in ended_breakers.head(5).iterrows():
                    end_info = f"{row.get('End Date', 'N/A')} {row.get('End Time', 'N/A')}"
                    logging.info(f"ENDED: {row['Symbol']} ended at {end_info}")
            
            if new_breakers.empty and ended_breakers.empty:
                logging.info("No new or ended circuit breakers detected since last check.")
                
                # Debug: Show why no changes were detected
                logging.debug(f"Intersection of keys: {len(current_keys & previous_keys)}")
                logging.debug(f"Keys only in current: {len(current_keys - previous_keys)}")
                logging.debug(f"Keys only in previous: {len(previous_keys - current_keys)}")
        else:
            logging.info("No previous circuit breaker data to compare against. This run will set the baseline.")
            new_breakers = current_df.copy()
            logging.info(f"Setting baseline with {len(new_breakers)} breakers")

        # Save current state for next comparison
        self.previous_df = current_df.copy()
        self._save_state_to_firestore(self.previous_df)

        logging.info("Check complete.")
        return new_breakers, ended_breakers
    
    def get_debug_info(self):
        """Return debug information about the current state"""
        info = {
            'csv_url': self.csv_url,
            'has_previous_data': not self.previous_df.empty,
            'previous_record_count': len(self.previous_df),
        }
        
        if not self.previous_df.empty:
            info['previous_columns'] = self.previous_df.columns.tolist()
            if 'UniqueKey' in self.previous_df.columns:
                info['sample_previous_keys'] = self.previous_df['UniqueKey'].head(3).tolist()
        
        return info