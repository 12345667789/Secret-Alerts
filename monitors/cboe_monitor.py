import os
import logging
import pandas as pd
from google.cloud import firestore
from datetime import datetime

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
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        
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
                # Convert lists to Series for proper DataFrame creation
                df = pd.DataFrame({k: pd.Series(v) for k, v in data.items()})
                logging.info(f"Successfully loaded previous state. {len(df)} records found.")
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
            # Drop the temporary UniqueKey before saving
            df_for_storage = df_to_save.copy()
            if 'UniqueKey' in df_for_storage.columns:
                df_for_storage = df_for_storage.drop(columns=['UniqueKey'])
            
            # Convert all columns to native Python types for Firestore
            data_to_store = df_for_storage.astype(object).where(pd.notnull(df_for_storage), None).to_dict('list')
            
            self.doc_ref.set(data_to_store)
            logging.info(f"Saving {len(df_to_save)} records to Firestore")
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
            return df
        except Exception as e:
            logging.error(f"Error fetching or parsing CSV data: {e}")
            return None

    def process_data(self, df):
        """
        Processes the raw DataFrame from the short sale CSV.
        """
        if df is None or df.empty:
            return pd.DataFrame()
        
        required_columns = ['Symbol', 'Trigger Date', 'Trigger Time']
        if not all(col in df.columns for col in required_columns):
            logging.error(f"Missing one or more required columns. Available columns: {df.columns.tolist()}")
            return pd.DataFrame()

        # Create a unique key based on the trigger event
        df['UniqueKey'] = df['Symbol'].astype(str) + "_" + df['Trigger Date'].astype(str) + "_" + df['Trigger Time'].astype(str)
        return df

    def check_for_new_and_ended_breakers(self):
        """
        Main logic to find both new and recently ended circuit breakers.
        Returns two DataFrames: (new_breakers, ended_breakers).
        """
        logging.info("Checking for new and ended breakers...")
        current_df_raw = self.fetch_data()
        current_df = self.process_data(current_df_raw)
        
        new_breakers = pd.DataFrame()
        ended_breakers = pd.DataFrame()

        if current_df.empty:
            logging.warning("Current short sale data is empty. Skipping check.")
            return new_breakers, ended_breakers

        # --- FIX: Ensure 'UniqueKey' exists on previous_df before comparison ---
        if not self.previous_df.empty:
            self.previous_df = self.process_data(self.previous_df.copy())
            
            logging.info("Comparing with previous data...")
            # 1. Find NEW breakers (in current but not in previous)
            previous_keys = set(self.previous_df['UniqueKey'])
            new_breakers = current_df[~current_df['UniqueKey'].isin(previous_keys)].copy()
            
            # 2. Find ENDED breakers (were open in previous, now have an End Time in current)
            previously_open = self.previous_df[pd.isnull(self.previous_df['End Time'])]
            
            if not previously_open.empty:
                # Find the current status of the previously open tickers
                current_status_of_open = current_df.merge(previously_open[['UniqueKey']], on='UniqueKey', how='inner')
                # Find the ones that now have an end time
                ended_breakers = current_status_of_open[pd.notnull(current_status_of_open['End Time'])].copy()
        else:
            logging.info("No previous circuit breaker data to compare against. This run will set the baseline.")
            new_breakers = current_df.copy()

        # Save the new state for the next run
        self._save_state_to_firestore(current_df)
        self.previous_df = current_df # Update in-memory state

        logging.info("Check complete.")
        logging.info(f"Found {len(new_breakers)} new breakers and {len(ended_breakers)} ended breakers")
        return new_breakers, ended_breakers
