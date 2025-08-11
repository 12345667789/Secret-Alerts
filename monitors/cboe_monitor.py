import os
import logging
import pandas as pd
import requests
from google.cloud import firestore

# --- Configure Logging ---
# Basic configuration for logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CBOEMonitor:
    """
    Monitors the CBOE for unusual options volume by comparing the current
    day's volume with the previous state, persisting state in Firestore.
    """
    def __init__(self):
        """
        Initializes the monitor, sets up the Firestore connection,
        and loads the last known state.
        """
        self.url = "https://www.cboe.com/us/options/market_statistics/daily/"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        
        # --- NEW: Firestore Initialization ---
        # Initialize the Firestore client. It will automatically use the
        # project credentials when running in a Google Cloud environment.
        try:
            self.db = firestore.Client()
            # Define a document reference. This is like a pointer to a specific
            # document in our database where we'll store the DataFrame.
            # Collection: 'cboe_monitor_state', Document: 'previous_df'
            self.doc_ref = self.db.collection('cboe_monitor_state').document('previous_df')
            logging.info("Successfully connected to Firestore.")
        except Exception as e:
            logging.critical(f"Failed to connect to Firestore: {e}")
            # If we can't connect to the DB, we can't continue.
            raise
            
        # --- MODIFIED: Load state from Firestore instead of initializing empty ---
        self.previous_df = self._load_state_from_firestore()

    def _load_state_from_firestore(self):
        """
        Loads the last saved DataFrame from Firestore.
        If no state is found (e.g., first run), returns an empty DataFrame.
        """
        try:
            logging.info(f"Attempting to load state from Firestore document: {self.doc_ref.path}")
            doc = self.doc_ref.get()
            if doc.exists:
                # The document exists, so we convert its data back to a DataFrame.
                # We stored it as a dictionary, so we can recreate it from that.
                data = doc.to_dict()
                df = pd.DataFrame.from_dict(data)
                logging.info(f"Successfully loaded previous state. {len(df)} records found.")
                return df
            else:
                # This will happen on the very first run.
                logging.warning("No previous state found in Firestore. Starting fresh.")
                return pd.DataFrame()
        except Exception as e:
            logging.error(f"Error loading state from Firestore: {e}. Starting with an empty state.")
            return pd.DataFrame()

    def _save_state_to_firestore(self, df_to_save):
        """
        Saves the given DataFrame to Firestore, overwriting any existing state.
        """
        if df_to_save.empty:
            logging.warning("Attempted to save an empty DataFrame. Skipping save.")
            return
            
        try:
            # Convert the DataFrame to a dictionary format that Firestore understands.
            # The 'to_dict("list")' format is generally safe and works well.
            data_to_store = df_to_save.astype(object).to_dict('list')

            self.doc_ref.set(data_to_store)
            logging.info(f"Successfully saved {len(df_to_save)} records to Firestore.")
        except Exception as e:
            logging.error(f"Could not save state to Firestore: {e}")

    def fetch_data(self):
        """
        Fetches the options volume data from the CBOE website.
        """
        try:
            logging.info(f"Fetching data from {self.url}")
            headers = {'User-Agent': self.user_agent}
            response = requests.get(self.url, headers=headers)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            tables = pd.read_html(response.content)
            # Assuming the target table is the first one
            return tables[0]
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching data: {e}")
            return None

    def process_data(self, df):
        """
        Processes the raw DataFrame to clean it up.
        """
        if df is None:
            return pd.DataFrame()
        df.columns = ['Symbol', 'Calls_Volume', 'Puts_Volume', 'Total_Volume']
        df['Total_Volume'] = pd.to_numeric(df['Total_Volume'], errors='coerce')
        df = df.dropna(subset=['Total_Volume'])
        df = df[df['Symbol'].str.match(r'^[A-Z]+$')]
        return df

    def check_for_unusual_volume(self):
        """
        Main logic to fetch, process, and compare data.
        Returns a DataFrame of new symbols found.
        """
        logging.info("Starting check for unusual options volume...")
        current_df_raw = self.fetch_data()
        current_df = self.process_data(current_df_raw)
        new_symbols = pd.DataFrame() # Default to empty DataFrame

        if current_df.empty:
            logging.warning("Current data is empty. Skipping check.")
            # Save the (empty) current state to not lose the previous state
            self._save_state_to_firestore(self.previous_df)
            return new_symbols

        if not self.previous_df.empty:
            # Merge the dataframes to easily find new symbols
            merged_df = current_df.merge(self.previous_df, on='Symbol', how='left', indicator=True)
            new_symbols = merged_df[merged_df['_merge'] == 'left_only'][['Symbol', 'Total_Volume_x']]
            new_symbols = new_symbols.rename(columns={'Total_Volume_x': 'Total_Volume'})


            if not new_symbols.empty:
                logging.info(f"--- {len(new_symbols)} New Symbols Detected ---")
            else:
                logging.info("No new symbols detected since last check.")
        else:
            logging.info("No previous data to compare against. This run will set the baseline.")

        # Update the state for the next run
        self.previous_df = current_df
        
        # Save the new state to Firestore
        self._save_state_to_firestore(self.previous_df)

        logging.info("Check complete.")
        return new_symbols

if __name__ == '__main__':
    # This part is for direct testing of the monitor
    monitor = CBOEMonitor()
    new_data = monitor.check_for_unusual_volume()
    if not new_data.empty:
        print("Found new symbols:")
        print(new_data)
