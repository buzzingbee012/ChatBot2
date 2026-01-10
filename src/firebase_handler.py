import firebase_admin
from firebase_admin import credentials, db
import logging
import os

class FirebaseHandler:
    def __init__(self, config):
        self.logger = logging.getLogger("FirebaseHandler")
        self.enabled = config.get('firebase', {}).get('enabled', False)
        self.db_ref = None
        
        if self.enabled:
            try:
                cred_path = config['firebase'].get('cred_path', 'serviceAccountKey.json')
                db_url = config['firebase'].get('db_url')
                
                if not db_url or "YOUR_DATABASE" in db_url:
                    self.logger.warning("Firebase enabled but DB URL not set. Cloud sync disabled.")
                    self.enabled = False
                    return

                if not os.path.exists(cred_path):
                    self.logger.warning(f"Firebase credentials not found at {cred_path}. Cloud sync disabled.")
                    self.enabled = False
                    return

                # Initialize only if not already initialized
                if not firebase_admin._apps:
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred, {
                        'databaseURL': db_url
                    })
                    self.logger.info("Firebase App Initialized.")
                
                self.db_ref = db.reference('stats')
                self.logger.info("Firebase connected to 'stats' node.")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize Firebase: {e}")
                self.enabled = False

    def update_stats(self, stats_data):
        """
        Push the entire stats dictionary to Firebase.
        """
        if not self.enabled or not self.db_ref:
            return

        try:
            self.db_ref.set(stats_data)
            self.logger.debug("Stats synced to Firebase.")
        except Exception as e:
            self.logger.error(f"Failed to sync stats to Firebase: {e}")

    def get_stats(self):
        """
        Fetch stats from Firebase.
        """
        if not self.enabled or not self.db_ref:
            return {}
        
        try:
            data = self.db_ref.get()
            return data if data else {}
        except Exception as e:
            self.logger.error(f"Failed to fetch stats from Firebase: {e}")
            return {}
