import pandas as pd
import logging
from google.cloud import firestore
import requests
from io import StringIO
from typing import Union, Tuple

class ShortSaleMonitor:
    """
    Monitors short sale circuit breaker data from CBOE, managing state via Firestore.
    This version is refactored for transactional state saving, controlled by the main app.
    """
    
    CBOE_URL = "https://www.cboe.com/us/equities/market_statistics/short_sale_circuit_breakers/downloads/BatsCircuitBreakers2025.csv"
    FIRESTORE_COLLECTION = 'app_config'
    FIRESTORE_DOC = 'short_sale_monitor_state'

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        try:
            self.db = firestore.Client()
            self.logger.info("Successfully connected to Firestore for Short Sale Monitor.")
        except Exception as e:
            self.logger.error(f"Failed to connect to Firestore: {e}", exc_info=True)
            self.db = None

    def fetch_data(self) -> Union[pd.DataFrame, None]:
        """
        Fetches the current short sale circuit breaker data from the CBOE URL.
        (No changes to this function)
        """
        self.logger.info(f"Fetching data from {self.CBOE_URL}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(self.CBOE_URL, headers=headers)
            response.raise_for_status()
            
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)
            
            self.logger.info(f"Successfully fetched {len(df)} records from CBOE.")
            return df
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during data fetching: {e}", exc_info=True)
        return None

    def _load_previous_state(self) -> Union[pd.DataFrame, None]:
        """
        Loads the previously stored state from Firestore.
        (No changes to this function)
        """
        if not self.db:
            return None
        try:
            doc_ref = self.db.collection(self.FIRESTORE_COLLECTION).document(self.FIRESTORE_DOC)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict().get('previous_breakers', [])
                self.logger.info(f"Successfully loaded previous state. {len(data)} records found.")
                return pd.DataFrame(data)
            else:
                self.logger.warning("No previous state document found in Firestore.")
        except Exception as e:
            self.logger.error(f"Error loading state from Firestore: {e}", exc_info=True)
        return pd.DataFrame()

    # --- NEW METHOD 1 of 3: Public method to save the state ---
    def save_state(self, df: pd.DataFrame):
        """
        Saves the provided DataFrame as the current state to Firestore.
        This is now controlled externally by main.py.
        """
        if not self.db or df is None:
            self.logger.warning("Save state skipped: No database connection or DataFrame is None.")
            return
        try:
            # Ensure NaN values are converted to None for Firestore compatibility
            df_cleaned = df.where(pd.notnull(df), None)
            records = df_cleaned.to_dict('records')
            doc_ref = self.db.collection(self.FIRESTORE_COLLECTION).document(self.FIRESTORE_DOC)
            doc_ref.set({'previous_breakers': records})
            self.logger.info(f"Saving {len(records)} records to Firestore state.")
        except Exception as e:
            self.logger.error(f"Error saving state to Firestore: {e}", exc_info=True)

    # --- NEW METHOD 2 of 3: The main logic function, replacing the old one ---
    def get_changes(self) -> Tuple[pd.DataFrame, pd.DataFrame, Union[pd.DataFrame, None]]:
        """
        Fetches latest data, compares with previous state, and returns the changes.
        This function DOES NOT save state; it only returns the data.
        """
        self.logger.info("Getting changes from CBOE...")
        previous_df = self._load_previous_state()
        current_df = self.fetch_data()

        if current_df is None:
            self.logger.error("Could not fetch current data. Aborting check.")
            return pd.DataFrame(), pd.DataFrame(), None

        # Prepare dataframes for comparison
        key_columns = ['Symbol', 'Trigger Date', 'Trigger Time']
        for df in [previous_df, current_df]:
            if df is not None and not df.empty:
                for col in key_columns:
                    if col in df.columns:
                        df[col] = df[col].astype(str)
                    else:
                        # This handles cases where the CSV might be missing a column temporarily
                        self.logger.warning(f"Key column '{col}' not found in dataframe. Comparison may be inaccurate.")
                        df[col] = ''

        new_breakers, ended_breakers = self._detect_changes(previous_df, current_df)
        
        self.logger.info(f"Check complete. Found {len(new_breakers)} new & {len(ended_breakers)} ended breakers.")
        return new_breakers, ended_breakers, current_df

    # --- HELPER METHOD 3 of 3: Unchanged, but used by get_changes ---
    def _detect_changes(self, old_df: pd.DataFrame, new_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Compares two dataframes to identify new and ended circuit breakers.
        (No changes to this function's logic)
        """
        if old_df is None or old_df.empty:
            return new_df.copy(), pd.DataFrame() # Return a copy to avoid SettingWithCopyWarning

        # Create a unique key for matching rows between the two dataframes
        old_df['UniqueKey'] = old_df['Symbol'].str.cat(old_df['Trigger Date']).str.cat(old_df['Trigger Time'])
        new_df['UniqueKey'] = new_df['Symbol'].str.cat(new_df['Trigger Date']).str.cat(new_df['Trigger Time'])

        # New breakers are rows with keys in the new_df that are not in the old_df
        new_breakers = new_df[~new_df['UniqueKey'].isin(old_df['UniqueKey'])].copy()
        
        # Ended breakers are rows that were previously open (End Time was null) but now have an End Time
        ended_breakers = pd.DataFrame()
        open_previously = old_df[old_df['End Time'].isnull()]
        if not open_previously.empty:
            # Find common rows that were previously open
            merged = pd.merge(open_previously, new_df, on='UniqueKey', how='inner', suffixes=('_old', ''))
            # From that merged set, find the ones that now have an end time
            ended = merged[merged['End Time'].notnull()]
            if not ended.empty:
                # Get the full row data for the ended breakers from the new dataframe
                ended_breakers = new_df[new_df['UniqueKey'].isin(ended['UniqueKey'])].copy()

        # Clean up the temporary key column before returning
        new_breakers.drop(columns=['UniqueKey'], inplace=True, errors='ignore')
        ended_breakers.drop(columns=['UniqueKey'], inplace=True, errors='ignore')

        return new_breakers, ended_breakers