import logging
import asyncio
import json
import os
import random
from .manychat_handler import ManyChatHandler
from .ai_handler import AIHandler

class ManyChatBot:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("WebMonitor")
        
        # ManyChat Config
        mc_config = config.get('manychat', {})
        self.api_token = mc_config.get('api_token')
        self.system_prompt = mc_config.get('prompt')
        
        # Persistent storage for manychat subscribers
        self.stats_file = "subscriber_stats.json"
        self.subscriber_counts = self._load_stats()
        
        if not self.api_token or "YOUR_MANYCHAT" in self.api_token:
            self.logger.warning("ManyChat API Token is missing or invalid.")
        
        self.mc_handler = ManyChatHandler(self.api_token)
        
        from .supabase_handler import SupabaseHandler
        self.supabase_handler = SupabaseHandler(config)

        # Initialize AI with ManyChat specific prompt if provided
        ai_config = config.copy()
        if self.system_prompt:
            if 'llm' not in ai_config: ai_config['llm'] = {}
            ai_config['llm']['system_prompt'] = self.system_prompt
            
        self.ai_handler = AIHandler(ai_config)

    def _load_stats(self):
        """Load subscriber message counts from file."""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading {self.stats_file}: {e}")
        return {}

    def _save_stats(self):
        """Save subscriber message counts to file."""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.subscriber_counts, f)
        except Exception as e:
            self.logger.error(f"Error saving {self.stats_file}: {e}")

    async def handle_message(self, subscriber_id, current_message=None, history=None):
        """
        Main entry point for handling a message from ManyChat.
        subscriber_id: The ID of the Instagram user.
        current_message: The latest message (if passed from webhook).
        history: Provided history (if passed from webhook).
        """
        self.logger.info(f"Processing message for subscriber: {subscriber_id}")
        
        # Track message count (persistent)
        current_count = self.subscriber_counts.get(str(subscriber_id), 0)
        
        # 1. Check for Link Forcing (Consistency with BaseBot)
        link_config = self.config.get('bot', {}).get('link_config', {})
        min_replies = link_config.get('min_replies_before_link', 10)
        max_replies = link_config.get('max_replies_before_link', 15)
        insta_link = self.config.get('instagram_link', "https://www.instagram.com/jasmin.sandhu.1")

        # 2. Get History early to allow evaluation
        if not history:
            history = self.mc_handler.get_conversation_history(subscriber_id)
            if not history and current_message:
                history = [{"role": "user", "content": current_message}]
                
        if not history:
            self.logger.warning(f"No history found for subscriber {subscriber_id}. Skipping.")
            return False

        should_force_link = False
        if current_count >= max_replies:
            should_force_link = True
        elif current_count >= min_replies:
            is_high_quality = self.ai_handler.evaluate_chatter(history)
            if is_high_quality:
                self.logger.info(f"AI evaluated {subscriber_id} as high quality. Forcing link.")
                should_force_link = True

        if should_force_link:
            reply_text = f"gtg, add me on instagram {insta_link}"
            self.logger.info(f"Forcing Instagram link for subscriber {subscriber_id} (count: {current_count})")
        else:
            # 3. Generate Response
            reply_text = self.ai_handler.generate_response(history)
        
        # 4. Validate Response
        if not reply_text:
            self.logger.error(f"Failed to generate valid response for {subscriber_id}.")
            return False
            
        # Clean response
        reply_text = reply_text.strip()
        if reply_text.lower().startswith("error") or "i cannot help" in reply_text.lower():
            self.logger.warning(f"AI returned error-like response: {reply_text}")
            return False

        # 5. Send Response
        result = self.mc_handler.send_message(subscriber_id, reply_text)
        if result:
            self.logger.info(f"Successfully sent reply to {subscriber_id}: {reply_text}")
            # Increment and save count
            self.subscriber_counts[str(subscriber_id)] = current_count + 1
            self._save_stats()
            
            # Save history to Supabase unconditionally
            if hasattr(self, 'supabase_handler') and self.supabase_handler.enabled:
                history.append({"role": "assistant", "content": reply_text})
                self.supabase_handler.save_chat_history(str(subscriber_id), "ManyChatBot", history)
                
            return True
        else:
            self.logger.error(f"Failed to send message to {subscriber_id} via ManyChat API.")
            return False
