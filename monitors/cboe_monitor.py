import pandas as pd
import logging
from google.cloud import firestore
import requests
from io import StringIO

class ShortSaleMonitor:
    """
    Monitors short sale circuit breaker data from CBOE, managing state via Firestore database.
    """
    
    CBOE_URL = "https://www.cboe.com/us/equities/market_statistics/short_sale_circuit_breakers/downloads/BatsCircuitBreakers2025.csv"
    FIRESTORE_COLLECTION = 'app_config'
    FIRESTORE_DOC = 'short_sale_monitor_state'

    def __init__(self):
        # CORRECT PLACEMENT: The logger must be initialized inside the __init__ method.
        self.logger = logging.getLogger(__name__)
        try:
            self.db = firestore.Client()
            self.logger.info("Successfully connected to Firestore for Short Sale Monitor.")
        except Exception as e:
            self.logger.error(f"Failed to connect to Firestore: {e}", exc_info=True)
            self.db = None

    def fetch_data(self) -> pd.DataFrame | None:
        """
        Fetches the current short sale circuit breaker data from the CBOE URL.
        """
        self.logger.info(f"Fetching data from {self.CBOE_URL}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
            response = requests.get(self.CBOE_URL, headers=headers)
            response.raise_for_status()
            
            csv_data = StringIO(response.text)
            df = pd.read_csv(csv_data)
            
            self.logger.info(f"Successfully fetched {len(df)} records from CBOE.")
            return df
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during data fetching: {e}", exc_info=True)
        return None

    def _load_previous_state(self) -> pd.DataFrame | None:
        """
        Loads the previously stored state from Firestore.
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

    def _save_current_state(self, df: pd.DataFrame):
        """
        Saves the current state to Firestore.
        """
        if not self.db:
            return
        try:
            df_cleaned = df.where(pd.notnull(df), None)
            records = df_cleaned.to_dict('records')
            doc_ref = self.db.collection(self.FIRESTORE_COLLECTION).document(self.FIRESTORE_DOC)
            doc_ref.set({'previous_breakers': records})
            self.logger.info(f"Saving {len(records)} records to Firestore.")
        except Exception as e:
            self.logger.error(f"Error saving state to Firestore: {e}", exc_info=True)

    def check_for_new_and_ended_breakers(self):
        """
        Fetches the latest data, compares it with the previous state,
        and returns dataframes of new and ended breakers.
        """
        self.logger.info("Checking for new and ended breakers...")
        previous_df = self._load_previous_state()
        current_df = self.fetch_data()

        if current_df is None:
            self.logger.error("Could not fetch current data. Aborting check.")
            return pd.DataFrame(), pd.DataFrame()

        key_columns = ['Symbol', 'Trigger Date', 'Trigger Time']
        for df in [previous_df, current_df]:
            if df is not None and not df.empty:
                for col in key_columns:
                    if col in df.columns:
                        df[col] = df[col].astype(str)
                    else:
                        self.logger.error(f"Key column '{col}' not found in dataframe. Comparison may be inaccurate.")
                        df[col] = ''

        new_breakers, ended_breakers = self._detect_changes(previous_df, current_df)
        
        self._save_current_state(current_df)
        
        self.logger.info(f"Check complete. Found {len(new_breakers)} new breakers & {len(ended_breakers)} ended breakers")
        return new_breakers, ended_breakers

    def _detect_changes(self, old_df: pd.DataFrame, new_df: pd.DataFrame) -> (pd.DataFrame, pd.DataFrame):
        """
        Compares two dataframes to identify new and ended circuit breakers.
        """
        if old_df is None or old_df.empty:
            return new_df, pd.DataFrame()

        old_df['UniqueKey'] = old_df['Symbol'] + old_df['Trigger Date'] + old_df['Trigger Time']
        new_df['UniqueKey'] = new_df['Symbol'] + new_df['Trigger Date'] + new_df['Trigger Time']

        new_breakers = new_df[~new_df['UniqueKey'].isin(old_df['UniqueKey'])].copy()
        ended_breakers = pd.DataFrame()
        
        open_previously = old_df[old_df['End Time'].isnull()]
        if not open_previously.empty:
            merged = pd.merge(open_previously, new_df, on='UniqueKey', how='inner', suffixes=('_old', ''))
            ended = merged[merged['End Time'].notnull()]
            if not ended.empty:
                ended_breakers = new_df[new_df['UniqueKey'].isin(ended['UniqueKey'])].copy()

        new_breakers = new_breakers.drop(columns=['UniqueKey'], errors='ignore')
        ended_breakers = ended_breakers.drop(columns=['UniqueKey'], errors='ignore')

        return new_breakers, ended_breakers