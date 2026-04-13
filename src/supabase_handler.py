import os
import logging
from supabase import create_client, Client

class SupabaseHandler:
    def __init__(self, config):
        self.logger = logging.getLogger("SupabaseHandler")
        self.enabled = config.get('supabase', {}).get('enabled', False)
        self.client: Client = None
        
        if self.enabled:
            try:
                url = os.getenv('SUPABASE_URL') or config['supabase'].get('url')
                key = os.getenv('SUPABASE_ANON_KEY') or config['supabase'].get('key')
                
                if not url or not key or "YOUR_SUPABASE_URL" in url:
                    self.logger.warning("Supabase enabled but URL/Key not set. Cloud sync disabled.")
                    self.enabled = False
                    return

                self.client = create_client(url, key)
                self.logger.info("Supabase connected.")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize Supabase: {e}")
                self.enabled = False

    def update_stats(self, stats_data):
        """
        Push the entire stats dictionary to Supabase.
        We store it in the 'app_data' table under the key 'stats'.
        """
        if not self.enabled or not self.client:
            return

        try:
            self.client.table('app_data').upsert({'key': 'stats', 'value': stats_data}).execute()
            self.logger.debug("Stats synced to Supabase.")
        except Exception as e:
            self.logger.error(f"Failed to sync stats to Supabase: {e}")

    def get_stats(self):
        """
        Fetch stats from Supabase.
        """
        if not self.enabled or not self.client:
            return {}
        
        try:
            response = self.client.table('app_data').select('value').eq('key', 'stats').execute()
            if response.data:
                return response.data[0].get('value', {})
            return {}
        except Exception as e:
            self.logger.error(f"Failed to fetch stats from Supabase: {e}")
            return {}

    def save_chat_history(self, user_name, bot_name, history):
        """
        Save exhausted chat history.
        """
        if not self.enabled or not self.client:
            return
            
        try:
            payload = {
                'user_name': user_name,
                'bot_name': bot_name,
                'history': history
            }
            # Bulletproof save method to avoid upsert primary key conflicts
            response = self.client.table('exhausted_chats').select('user_name').eq('user_name', user_name).execute()
            if response.data:
                self.client.table('exhausted_chats').update({'history': history}).eq('user_name', user_name).execute()
            else:
                self.client.table('exhausted_chats').insert(payload).execute()
                
            self.logger.info(f"Chat history saved for user: {user_name}")
        except Exception as e:
            self.logger.error(f"Failed to save chat history to Supabase: {e}")
