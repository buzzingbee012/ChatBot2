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
        # Set a longer default timeout to handle 10 parallel instances
        self.page.set_default_timeout(15000) 

        # Resource Saver: Block images, media, and fonts to save CPU/Bandwidth
        async def block_media(route):
            if route.request.resource_type in ["image", "media", "font"]:
                await route.abort()
            else:
                await route.continue_()
        
        await self.page.route("**/*", block_media)
        
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
    async def _check_exists(self, selector, timeout=2000):
        """Checks if a selector exists without throwing error."""
        try:
            if not selector: return False
            # Wait briefly
            await self.page.wait_for_selector(selector, state='attached', timeout=timeout)
            return True
        except:
            return False

    async def js_click(self, selector):
        """Force a click via JS to bypass overlays and actionability checks."""
        try:
            await self.page.evaluate(f"document.querySelector('{selector}').click()")
            return True
        except:
            return False

    async def js_press_enter(self, selector):
        """Force an Enter keypress via JS events."""
        try:
            await self.page.evaluate(f"""
                (sel) => {{
                    const el = document.querySelector(sel);
                    if (!el) return;
                    const ev = new KeyboardEvent('keydown', {{
                        key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true
                    }});
                    el.dispatchEvent(ev);
                }}
            """, selector)
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
                
                # 1. Broadcast (Every 5 mins with Jitter)
                current_time = time.time()
                import random
                jitter = random.randint(-30, 30)
                if current_time - last_broadcast_time > (self.config['bot'].get('broadcast_interval', 300) + jitter):
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
            # New Link Forcing Logic
            link_config = self.config.get('bot', {}).get('link_config', {})
            min_replies = link_config.get('min_replies_before_link', 10)
            max_replies = link_config.get('max_replies_before_link', 15)
            force_prob = link_config.get('force_link_probability', 0.3)
            
            insta_link = self.config.get('instagram_link', "https://www.instagram.com/jas.sandhu.012")
            
            # Force link if we hit the limit or randomly after min_replies
            should_force_link = False
            if current_count >= max_replies:
                should_force_link = True
            elif current_count >= min_replies:
                if random.random() < force_prob:
                    should_force_link = True
            
            if should_force_link:
                self.logger.info(f"Forcing Instagram link for {name} (count: {current_count})")
                return f"gtg, add me on instagram {insta_link}"
            else:
                generated = self.ai_handler.generate_response(history)
                return generated if generated else None
        except Exception as e:
            self.logger.error(f"AI generation error for {name}: {e}")
            return None

    async def process_pms(self):
        """Check for PMs and reply using Parallel Thinking (batch generation)."""
        try:
            # Step 1: Discover all unreads
            unreads = await self.get_unread_chats()
            if not unreads:
                return
            
            # Step 2: Prioritize existing chatters
            unreads.sort(key=lambda x: self.user_reply_counts.get(x['name'], 0), reverse=True)
            
            # Step 3: Scrape Phase (Gather all context)
            chat_data = []
            for chat in unreads:
                name = chat['name']
                
                # Check Global Limits
                if self.total_messages_sent >= self.max_session_messages:
                    break
                
                # Check Per-User Limit
                current_count = self.user_reply_counts.get(name, 0)
                if current_count >= self.max_replies_per_user:
                    continue
                
                # Open, Read, and Store
                if not await self.open_chat(chat):
                    continue
                    
                if not await self.wait_for_chat_load(name):
                    await self.return_to_lobby()
                    continue
                
                history = await self.get_chat_history()
                if history:
                    chat_data.append({
                        'name': name,
                        'chat': chat,
                        'history': history,
                        'current_count': current_count
                    })
                
                # Fast exit back to lobby
                await self.return_to_lobby()
            
            if not chat_data:
                return
            
            # Step 4: Parallel Thinking Phase (Generate all AI responses at once)
            self.logger.info(f"Generating {len(chat_data)} responses in parallel...")
            tasks = [
                self._generate_reply(data['name'], data['history'], data['current_count'])
                for data in chat_data
            ]
            replies = await asyncio.gather(*tasks)
            
            # Step 5: Send Phase (Execute replies sequentially with realistic typing)
            for data, reply_text in zip(chat_data, replies):
                if not reply_text:
                    continue
                
                name = data['name']
                chat = data['chat']
                
                # Re-open chat
                if not await self.open_chat(chat):
                    continue
                
                # Rapid verification (since we just checked it)
                if not await self.wait_for_chat_load(name):
                    await self.return_to_lobby()
                    continue
                
                # Type and Send
                last_user_msg = "Unknown"
                for h in reversed(data['history']):
                    if h['role'] == 'user':
                        last_user_msg = h['content']
                        break
                
                self.logger.info(f"[{self.username}] Chatter: '{last_user_msg}' -> AI: '{reply_text}'")
                if await self.send_message(reply_text):
                    self.user_reply_counts[name] = data['current_count'] + 1
                    self.total_messages_sent += 1
                    
                    # Track Stats
                    tokens = getattr(self.ai_handler, 'last_token_count', 0)
                    self.stats_tracker.increment_today(tokens=tokens, bot_name=self.logger.name)
                
                # Immediate exit/transition
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
