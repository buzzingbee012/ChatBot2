import asyncio
import logging
import time
import random
from abc import ABC, abstractmethod
from playwright.async_api import async_playwright
from .utils import Dashboard, Logger
from .ai_handler import AIHandler
from .stats_tracker import StatsTracker

class BaseBot(ABC):
    def __init__(self, config, bot_name="Bot"):
        self.config = config
        self.logger = Logger(name=bot_name)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.running = False
        
        # Shared tracking
        self.user_reply_counts = {} 
        self.total_messages_sent = 0
        self.max_session_messages = config.get('bot', {}).get('max_session_messages', 500)
        self.max_daily_messages = config.get('bot', {}).get('max_daily_messages', 100)
        self.max_replies_per_user = config.get('bot', {}).get('max_replies_per_user', 20)
        
        self.stats_tracker = StatsTracker()
        self.ai_handler = AIHandler(config)

    async def start(self, duration=None):
        """Standard lifecycle start."""
        self.playwright = await async_playwright().start()
        import os
        env_headless = os.getenv("HEADLESS", "false").lower() == "true"
        headless = env_headless or self.config['bot'].get('headless', False)
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            ignore_default_args=["--enable-automation"]
        )
        
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(5000) # Prevents 30s hangs
        
        # Global Popup Handler: Close any new pages/tabs immediately
        self.context.on("page", self._handle_popup)
        
        self.running = True
        
        try:
            if await self.entry_point(): # Renamed from guest_entry to generic
                await self.monitor_loop(duration)
            else:
                self.logger.error("Entry/Login Failed. Stopping.")
        except Exception as e:
            self.logger.error(f"Bot Crashed: {e}")
            import traceback
            traceback.print_exc()

    async def _handle_popup(self, popup):
        """Automatically closes unwanted popups."""
        try:
            target_url = popup.url
            self.logger.warning(f"Popup detected: {target_url}. Closing...")
            await popup.close()
            self.logger.info("Popup closed successfully.")
        except Exception as e:
            self.logger.error(f"Failed to close popup: {e}")

    async def stop(self):
        self.running = False
        if self.context: 
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright: 
            await self.playwright.stop()

    # --- Helper Methods ---
    async def _check_exists(self, selector, timeout=1000):
        """Checks if a selector exists without throwing error."""
        try:
            if not selector: return False
            # Wait briefly
            await self.page.wait_for_selector(selector, state='attached', timeout=timeout)
            return True
        except:
            return False

    async def safe_click(self, selector, timeout=5000):
        """Clicks if exists, else logs warning."""
        try:
            if await self._check_exists(selector, timeout):
                await self.page.click(selector)
                return True
            else:
                self.logger.warning(f"Click failed - element not found: {selector}")
                return False
        except Exception as e:
            self.logger.error(f"Click Error for {selector}: {e}")
            return False

    async def safe_type(self, selector, text, timeout=5000):
        """Types if exists."""
        try:
            if await self._check_exists(selector, timeout):
                await self.page.fill(selector, text)
                return True
            else:
                self.logger.warning(f"Type failed - element not found: {selector}")
                return False
        except Exception as e:
            self.logger.error(f"Type Error for {selector}: {e}")
            return False

    async def monitor_loop(self, duration=None):
        """Common logic loop."""
        self.logger.info("Starting Monitor Loop")
        Dashboard.status("Monitoring Chat...")
        
        # Initial wait
        self.logger.info("Waiting 0.5s before first loop...")
        await asyncio.sleep(0.5)  # Reduced from 3s for faster initial response

        import time
        start_time = time.time()
        last_broadcast_time = 0
        
        while self.running:
            if duration and (time.time() - start_time > duration):
                self.logger.info("Duration reached.")
                break
                
            try:
                # 0. Maintenance
                await self.handle_ads_and_popups()
                
                # 1. Broadcast (Every 2-3 mins)
                # We add some randomness to avoid exact detection
                current_time = time.time()
                if current_time - last_broadcast_time > (self.config['bot'].get('broadcast_interval', 180)):
                    last_broadcast_time = current_time # Reset timer regardless of success
                    await self.perform_broadcast()
                
                # 2. PM Checking
                await self.process_pms()
                
                await asyncio.sleep(0.1)  # Poll interval - reduced from 0.25s for faster detection
                
            except Exception as e:
                self.logger.error(f"Loop Error: {e}")
                await asyncio.sleep(0.1)  # Reduced from 0.25s

    async def _generate_reply(self, name, history, current_count):
        """Generate AI reply for a single user (can run in parallel)."""
        try:
            if current_count == self.max_replies_per_user:
                return "gtg, add me on instagram " + self.config.get('instagram_link', "https://instagram.com/jasmin.sandhu.1")
            else:
                generated = self.ai_handler.generate_response(history)
                return generated if generated else None
        except Exception as e:
            self.logger.error(f"AI generation error for {name}: {e}")
            return None

    async def process_pms(self):
        """Check for PMs and reply with parallel AI generation."""
        try:
            # Step 1: Get list of unread conversations/users
            unreads = await self.get_unread_chats()
            
            if not unreads:
                return
            
            # Step 2: Collect all chat histories (must be sequential - UI limitation)
            chat_data = []
            for chat in unreads:
                name = chat['name']
                
                # Check Global Limits
                if self.total_messages_sent >= self.max_session_messages:
                    break
                
                # Check Per-User Limit
                current_count = self.user_reply_counts.get(name, 0)
                if current_count > self.max_replies_per_user:
                    continue
                
                # Open chat and verify context
                if not await self.open_chat(chat):
                    continue
                
                if not await self.wait_for_chat_load(name):
                    self.logger.warning(f"Failed to verify chat context for {name}")
                    continue
                
                # Get chat history
                history = await self.get_chat_history()
                
                chat_data.append({
                    'name': name,
                    'chat': chat,
                    'history': history,
                    'current_count': current_count
                })
                
                # Return to lobby for next chat
                await self.return_to_lobby()
            
            if not chat_data:
                return
            
            # Step 3: Generate ALL AI responses in parallel (FAST!)
            self.logger.info(f"Generating {len(chat_data)} AI responses in parallel...")
            tasks = [
                self._generate_reply(data['name'], data['history'], data['current_count'])
                for data in chat_data
            ]
            responses = await asyncio.gather(*tasks)
            
            # Step 4: Send messages (must be sequential - UI limitation)
            for data, reply_text in zip(chat_data, responses):
                name = data['name']
                current_count = data['current_count']
                history = data['history']
                chat = data['chat']
                
                if not reply_text:
                    self.logger.warning(f"Skipping reply to {name} - AI generation failed/empty.")
                    continue
                
                # Open chat again
                if not await self.open_chat(chat):
                    continue
                
                if not await self.wait_for_chat_load(name):
                    self.logger.warning(f"Failed to verify chat context for {name} during send")
                    continue
                
                # Send the pre-generated reply
                if await self.send_message(reply_text):
                    self.user_reply_counts[name] = current_count + 1
                    self.total_messages_sent += 1
                    
                    # Track Stats
                    tokens = getattr(self.ai_handler, 'last_token_count', 0)
                    self.stats_tracker.increment_today(tokens=tokens, bot_name=self.logger.name)
                    
                    # Get last user message for clean logging
                    last_user_msg = next((m['content'] for m in reversed(history) if m['role'] == 'user'), "N/A")
                    self.logger.info(f"Replied to {name}: User: \"{last_user_msg}\" | AI: \"{reply_text}\"")
                
                # Return to lobby for next send
                await self.return_to_lobby()
                
        except Exception as e:
            self.logger.error(f"PM Process Error: {e}")

    # --- Abstract Methods ---
    
    @abstractmethod
    async def entry_point(self):
        """Login or Guest Entry."""
        pass

    @abstractmethod
    async def handle_ads_and_popups(self):
        """Close overlays."""
        pass

    @abstractmethod
    async def perform_broadcast(self):
        """Send broadcast message. Return True if sent."""
        pass

    @abstractmethod
    async def get_unread_chats(self):
        """Return list of unread chat identifiers: [{'name': '...', 'element': ...}]"""
        pass

    @abstractmethod
    async def open_chat(self, chat_obj):
        """Switch context to this chat."""
        pass

    @abstractmethod
    async def wait_for_chat_load(self, name):
        """Verify chat header matches expected name."""
        pass

    @abstractmethod
    async def get_chat_history(self):
        """Return list of msg dicts [{'role': 'user', 'content': '...'}, ...]"""
        pass

    @abstractmethod
    async def send_message(self, text):
        """Type and send message in current context."""
        pass

    @abstractmethod
    async def return_to_lobby(self):
        """Go back to main view if needed."""
        pass
