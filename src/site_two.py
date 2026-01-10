import asyncio
import logging
from playwright.async_api import async_playwright
from .utils import Dashboard, safe_click, close_ads, Logger
from .ai_handler import AIHandler
from .stats_tracker import StatsTracker

class SiteTwoBot:
    def __init__(self, config):
        self.config = config
        self.logger = Logger()
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.running = False
        self.username = config['guest_profile']['username']
        self.user_reply_counts = {} # Track replies per user
        self.total_messages_sent = 0
        self.max_session_messages = config.get('bot', {}).get('max_session_messages', 500)
        self.max_daily_messages = config.get('bot', {}).get('max_daily_messages', 100)
        self.stats_tracker = StatsTracker()
        self.ai_handler = AIHandler(config)

    async def start(self, duration=None):
        """
        Starts the bot session.
        :param duration: Optional duration in seconds to run the bot.
        """
        self.playwright = await async_playwright().start()
        
        import os
        env_headless = os.getenv("HEADLESS", "false").lower() == "true"
        headless = env_headless or self.config['bot'].get('headless', False)
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            ignore_default_args=["--enable-automation"]
        )
        
        # Create context with user agent
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        self.page = await self.context.new_page()
        self.running = True
        
        try:
            if await self.guest_entry():
                await self.monitor_loop(duration)
            else:
                self.logger.error("Guest Entry Failed. Stopping.")
        except Exception as e:
            self.logger.error(f"Bot Crashed: {e}")
        finally:
            await self.stop()

    async def stop(self):
        self.running = False
        if self.context: await self.context.close()
        if self.playwright: await self.playwright.stop()

    async def guest_entry(self, duration=None):
        """
        Handles the specific 'Let's Chat' loop for Site 2.
        Updated to support direct Kiwi IRC link.
        """
        url = self.config['site_two']['url']
        self.logger.info(f"Navigating to {url}...")
        await self.page.goto(url)
        
        Dashboard.status("Entering Site 2...")

        # Wait for the Kiwi login form
        try:
            self.logger.info("Waiting for Kiwi Login Form...")
            # Selectors for Kiwi IRC login
            # Nick input usually has class .u-input or inside .kiwi-welcome-simple-form
            nick_input = self.page.locator(".kiwi-welcome-simple-form input.u-input, input.kiwi-welcome-simple-nick").first
            
            # Wait for it to be visible (timeout 15s)
            await nick_input.wait_for(state="visible", timeout=15000)
            self.logger.info("Found Nickname Input.")
            
            # Validate if we need to close a "welcome" modal or ensure focus
            if await self.page.locator(".kiwi-welcome-simple-error").is_visible():
                self.logger.warning("Detected generic error on load. Refreshing...")
                await self.page.reload()
                await nick_input.wait_for(state="visible", timeout=15000)

            Dashboard.status("Entering Nickname...")
            await nick_input.click()
            await nick_input.fill(self.username)
            
            # Simulate real user typing/interaction
            await self.page.wait_for_timeout(500)
            
            # Find Start Button
            # Selector: button.kiwi-welcome-simple-start
            start_btn = self.page.locator("button.kiwi-welcome-simple-start, button:has-text('Start')").first
            
            # Check if disabled (sometimes needs more input events)
            if await start_btn.get_attribute("disabled"):
                self.logger.info("Start button disabled, triggering input events...")
                await nick_input.press("End")
                await nick_input.type(" ")
                await self.page.wait_for_timeout(200)
                await nick_input.press("Backspace")
            
            await start_btn.click()
            self.logger.info("Clicked Start.")
            
            # Wait for chat to load
            # Check for a channel or the input bar
            self.logger.info("Waiting for Chat Interface...")
            chat_loaded_indicator = self.page.locator(".kiwi-controlinput-input, .kiwi-statebrowser-channels, .kiwi-header-name")
            await chat_loaded_indicator.first.wait_for(state="visible", timeout=20000)
            
            self.logger.info("Successfully entered chat!")
            return True

        except Exception as e:
            self.logger.error(f"Guest Entry/Monitor Failed: {e}")
            try:
                await self.page.screenshot(path="entry_failure.png")
            except: pass
            return False

    async def _close_overlays(self):
        """Checks for and closes Google Vignettes/Overlays."""
        try:
            # 1. Main Page Selectors
            targets = [
                 "div[aria-label='Close ad']", 
                 "div[aria-label='Close']",
                 "#dismiss-button",
                 "svg[aria-label='Close ad']",
                 "iframe[title='Ad']", # Generic ad frame
                 "iframe[name*='google']" # Google ad frame
            ]
            
            # Dismiss usage generic
            if await self.page.locator("#dismiss-button").count() > 0:
                 await self.page.click("#dismiss-button")
                 self.logger.info("Closed overlay via #dismiss-button")
                 return

            # 2. Iframe check (Vignettes are often in iframes)
            for frame in self.page.frames:
                 if "google" in frame.name or "vignette" in frame.name or "google" in frame.url:
                     try:
                         # Try to find a close button inside
                         close_btns = frame.locator("div[aria-label='Close ad'], svg[aria-label='Close ad'], #dismiss-button")
                         if await close_btns.count() > 0:
                             if await close_btns.first.is_visible():
                                 self.logger.info(f"Closing vignette in frame: {frame.name}")
                                 await close_btns.first.click()
                                 await self.page.wait_for_timeout(1000)
                                 return
                     except: pass
        except Exception as e:
            pass 

    async def monitor_loop(self, duration=None):
        """
        Requirements:
        1. Send message to main room every 5 mins.
        2. Respond to PMs.
        """
        self.logger.info("Starting Monitor Loop")
        Dashboard.status("Monitoring Chat...")
        
        self.logger.info("Waiting 30s before first broadcast...")
        await asyncio.sleep(10)

        last_broadcast_time = 0
        import time
        start_time = time.time()
        
        while self.running:
            # Check Duration
            if duration and (time.time() - start_time > duration):
                self.logger.info(f"Duration of {duration}s reached. Stopping bot.")
                self.running = False
                break
            try:
                # 0. Handle Vignettes/Ads
                await self._close_overlays()
                
                # Close any rogue pages that might have opened
                if len(self.context.pages) > 1:
                    for p in self.context.pages[1:]:
                        try:
                            if "allindiachat" not in p.url:
                                await p.close()
                                self.logger.info("Closed rogue popup in monitor loop.")
                        except: pass
                
                # 1. Broadcast Check
                current_time = time.time()
                if current_time - last_broadcast_time > 180: # 3 mins
                    self.logger.info("Sending Broadcast Message...")
                    Dashboard.outgoing("Broadcast: hello guys")
                    
                    # Ensure we are on the right tab
                    try:
                        # Selector variants for the channel tab
                        channel_tab = self.page.locator(".kiwi-statebrowser-channel[data-name='#allindiachat.com'], div[role='tab']:has-text('#allindiachat.com'), .kiwi-statebrowser-channel:has-text('allindiachat.com')").first
                        if await channel_tab.count() > 0:
                            await channel_tab.click()
                            self.logger.info("Switched to #allindiachat.com tab.")
                            await self.page.wait_for_timeout(500)
                    except Exception as e:
                        self.logger.warning(f"Could not switch tab: {e}")

                    # Find Input (Kiwi specific)
                    target_input = None
                    
                    # Try Main Input
                    # Updated based on user provided HTML: <div class="kiwi-ircinput-editor" ...>
                    target_input = self.page.locator(".kiwi-ircinput-editor").first
                    
                    if await target_input.is_visible():
                        await target_input.click()
                        # specific delay to ensure focus
                        await self.page.wait_for_timeout(100)
                        await target_input.fill("Hello")
                        await target_input.press("Enter")
                        last_broadcast_time = current_time
                        self.logger.info("Broadcast 'Hello' sent.")
                    else:
                        self.logger.warning("Main input (.kiwi-ircinput-editor) not found for broadcast. (Will retry in 30s)")
                        await asyncio.sleep(30) 
                        continue

                # 2. PM Check
                # Look for unread channels that are NOT the main channel (#allindiachat.com)
                # Selectors for unread: .kiwi-statebrowser-channel[data-name*='#'] is channel
                # We want channels that do NOT start with # (users) and have unread markers.
                # Usually .kiwi-statebrowser-channel--unread or similar.
                # Let's iterate all channels and check properties.
                
                try:
                    # Find all channel tabs
                    tabs = self.page.locator(".kiwi-statebrowser-channel")
                    count = await tabs.count()
                    
                    for i in range(count):
                        try:
                            tab = tabs.nth(i)
                            name = await tab.get_attribute("data-name", timeout=5000)
                            
                            # Skip main channel or server tab
                            if not name or name.startswith("#") or name == "*" or "allindiachat" in name:
                                continue
                        except Exception as e:
                            # Skip tabs that timeout or error
                            continue
                            
                        # Check for unread indicator
                        # Kiwi usually has a badge or a class.
                        # Common class: .kiwi-statebrowser-channel-unread or .kiwi-statebrowser-newmessage
                        # Or check for the unread counter badge: .kiwi-statebrowser-channel-label > .u-label
                        
                        # Updated Selectors based on HTML:
                        # <div data-name="ankurrs" class="kiwi-statebrowser-channel">
                        #   ... <div class="kiwi-statebrowser-channel-label kiwi-statebrowser-channel-label--highlight"> 3 </div>
                        
                        is_unread = False
                        
                        # Check for the specific highlight class on the label
                        label = tab.locator(".kiwi-statebrowser-channel-label")
                        if await label.count() > 0:
                            if await label.is_visible():
                                class_attr = await label.get_attribute("class") or ""
                                text_content = await label.inner_text()
                                
                                # Condition 1: Highlight class
                                if "highlight" in class_attr:
                                    is_unread = True
                                # Condition 2: Has a number > 0 (The HTML shows numbers like ' 5 ', ' 1 ', ' 3 ')
                                elif text_content and text_content.strip().isdigit() and int(text_content.strip()) > 0:
                                    is_unread = True
                        
                        if is_unread:
                            
                            # Initial Check for max replies
                            # We check BEFORE clicking to avoid unnecessary navigation if possible, 
                            # but we might simply ignore after clicking if logic requires.
                            # For now, let's keep the click to ensure we clear the unread state (optional) or just ignore.
                            
                            current_count = self.user_reply_counts.get(name, 0)
                            max_replies = self.config['site_two'].get('max_replies', 20)
                            
                            if current_count > max_replies:
                                self.logger.info(f"Ignoring {name} (Max replies sent).")
                                continue
                            
                            if self.total_messages_sent >= self.max_session_messages:
                                self.logger.warning("Max session messages reached. Stopping replies.")
                                return

                            # Check daily message limit
                            from datetime import datetime
                            today = datetime.now().strftime("%Y-%m-%d")
                            today_stats = self.stats_tracker.stats.get(today, {})
                            today_interactions = today_stats.get("interactions", 0) if isinstance(today_stats, dict) else today_stats
                            
                            if today_interactions >= self.max_daily_messages:
                                self.logger.warning(f"Max daily messages reached ({self.max_daily_messages}). Skipping reply to {name}.")
                                continue
                            self.logger.info(f"Found unread PM from {name}. Replying...")
                            await tab.click()
                            await self.page.wait_for_timeout(1000) # Wait for load
                            
                            # Random delay 2-10s between messages as requested
                            import random
                            min_delay = self.config['site_two'].get('reply_delay_min', 0)
                            max_delay = self.config['site_two'].get('reply_delay_max', 2)
                            delay = random.uniform(min_delay, max_delay)
                            self.logger.info(f"Waiting {delay:.1f}s before reply...")
                            await asyncio.sleep(delay)

                            # Determine Message
                            message_to_send = ""
                            
                            if current_count == max_replies:
                                message_to_send = "gtg, add me on instagram lets stay in touch " + self.config['site_two'].get('instagram_link', "")
                                self.logger.info(f"Sending Instagram Link to {name}!")
                            else:
                                # AI Generation Logic
                                try:
                                    # Scrape history from visible chat
                                    # Selectors: .kiwi-messagelist-message
                                    # We need to distinguish user vs bot (me)
                                    # .kiwi-messagelist-message--own (me) vs others
                                    
                                    history_elements = self.page.locator(".kiwi-messagelist-message")
                                    count = await history_elements.count()
                                    
                                    chat_history = []
                                    # Get last 10 messages max
                                    start_idx = max(0, count - 10)
                                    
                                    for i in range(start_idx, count):
                                        msg_el = history_elements.nth(i)
                                        # Target the body specifically to avoid time/nick
                                        body_el = msg_el.locator(".kiwi-messagelist-body")
                                        if await body_el.count() > 0:
                                            text = await body_el.inner_text()
                                        else:
                                            # Fallback if structure is different
                                            text = await msg_el.inner_text()
                                        
                                        # Simple role detection
                                        classes = await msg_el.get_attribute("class") or ""
                                        role = "assistant" if "kiwi-messagelist-message--own" in classes else "user"
                                        
                                        # Clean text (remove time/nick if mixed in, but usually inner_text is okay for now)
                                        # Kiwi might include nick in text, let's just use it raw for context.
                                        chat_history.append({"role": role, "content": text})
                                    
                                    if not chat_history:
                                        # Fallback if no history found (shouldn't happen if they PM'd)
                                        chat_history.append({"role": "user", "content": "Hello"})
                                    
                                    self.logger.info(f"Generating AI response for {name} with history val: {len(chat_history)}")
                                    generated_reply = self.ai_handler.generate_response(chat_history)
                                    
                                    # If None, error occurred - skip this message entirely
                                    if generated_reply is None:
                                        self.logger.warning(f"AI error occurred, skipping reply to {name}")
                                        error = getattr(self.ai_handler, 'last_error', None)
                                        if error:
                                            self.stats_tracker.increment_today(tokens=0, error=error)
                                        continue
                                    
                                    message_to_send = generated_reply
                                    
                                except Exception as ai_e:
                                    self.logger.error(f"AI Failed: {ai_e}")
                                    message_to_send = "Hello" # Fallback
                            
                            if not message_to_send:
                                continue

                            # Reuse message sending logic
                            pm_input = self.page.locator(".kiwi-ircinput-editor").first
                            if await pm_input.is_visible():
                                await pm_input.click()
                                await self.page.wait_for_timeout(100)
                                await pm_input.fill(message_to_send)
                                await pm_input.press("Enter")
                                
                                # Increment Count
                                self.user_reply_counts[name] = current_count + 1
                                self.total_messages_sent += 1
                                tokens = getattr(self.ai_handler, 'last_token_count', 0)
                                error = getattr(self.ai_handler, 'last_error', None)
                                self.stats_tracker.increment_today(tokens=tokens, error=error)
                                self.logger.info(f"Replied to {name} (Message: {message_to_send} ,Count: {self.user_reply_counts[name]}, Total: {self.total_messages_sent})")
                                
                                # Switch back to main channel to continue monitoring
                                main_tab = self.page.locator(".kiwi-statebrowser-channel[data-name='#allindiachat.com']").first
                                if await main_tab.count() > 0:
                                     await main_tab.click()
                            else:
                                self.logger.warning(f"Could not find input for PM {name}")

                except Exception as pm_e:
                    self.logger.error(f"Error in PM loop: {pm_e}")
                    
                await self.page.wait_for_timeout(2000)
                
            except Exception as e:
                self.logger.error(f"Monitor Loop Error: {e}")
                await self.page.wait_for_timeout(5000)
