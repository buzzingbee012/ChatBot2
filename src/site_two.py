import asyncio
import random
from .base_bot import BaseBot
from .utils import Dashboard

class SiteTwoBot(BaseBot):
    def __init__(self, config, instance_id=1):
        super().__init__(config, bot_name=f"SiteTwoBot-{instance_id}")
        self.username = self.ai_handler.generate_username()
        if self.username:
            self.username += "_f"
        else:
             self.username = config['guest_profile']['username'] + "_f"
             
        # Site specific config
        self.site_config = config['site_two']
        self.max_replies_per_user = self.site_config.get('max_replies', 20)

    async def entry_point(self):
        """Legacy guest_entry logic."""
        url = self.site_config['url']
        self.logger.info(f"Navigating to {url} with username: {self.username}...")
        await self.page.goto(url)
        
        Dashboard.status("Entering Site 2...")

        # Wait for the Kiwi login form
        try:
            self.logger.info("Waiting for Kiwi Login Form...")
            nick_input = self.page.locator(".kiwi-welcome-simple-form input.u-input, input.kiwi-welcome-simple-nick").first
            await nick_input.wait_for(state="visible", timeout=15000)
            
            # Error check
            if await self.page.locator(".kiwi-welcome-simple-error").is_visible():
                await self.page.reload()
                await nick_input.wait_for(state="visible", timeout=15000)

            Dashboard.status("Entering Nickname...")
            await nick_input.click()
            await nick_input.fill(self.username)
            await self.page.wait_for_timeout(500)
            
            start_btn = self.page.locator("button.kiwi-welcome-simple-start, button:has-text('Start')").first
            
            # Handle disabled button
            if await start_btn.get_attribute("disabled"):
                await nick_input.press("End")
                await nick_input.type(" ")
                await self.page.wait_for_timeout(200)
                await nick_input.press("Backspace")
            
            await start_btn.click(force=True)
            self.logger.info("Clicked Start.")
            
            # Wait for any element that signals we are in the chat
            for i in range(20): # 20 second max
                if await self.page.locator(".kiwi-controlinput-input, .kiwi-statebrowser-channels, .kiwi-header-name").first.is_visible():
                    self.logger.info("Successfully entered chat!")
                    return True
                await asyncio.sleep(1)
            
            self.logger.error("Timeout waiting for chat interface to appear.")
            return False

        except Exception as e:
            self.logger.error(f"Entry Failed: {e}")
            return False

    async def handle_ads_and_popups(self):
        """Aggressive overlay and ad removal for Kiwi IRC."""
        try:
             # 1. Nuke persistent ad iframes/containers and Kiwi modals
             await self.page.evaluate("""
                 () => {
                     const selectors = [
                         'iframe[id^="aswift"]', 'ins.adsbygoogle', '#google_vignette',
                         '.kiwi-confirm-button', '.modal-close', '.button-close',
                         '.kiwi-error-modal', '.kiwi-reconnect-button', '.kiwi-welcome'
                     ];
                     selectors.forEach(s => {
                         document.querySelectorAll(s).forEach(el => el.remove());
                     });
                     // Force pointer events back on to the body
                     document.body.style.pointerEvents = 'auto';
                     document.documentElement.style.pointerEvents = 'auto';
                 }
             """)

             # 2. Key-press Escape as fallback
             await self.page.keyboard.press("Escape")
             
             # 3. Close rogue pages
             if len(self.context.pages) > 1:
                for p in self.context.pages[1:]:
                     try:
                         if "allindiachat" not in p.url: await p.close()
                     except: pass
        except: pass 

    async def perform_broadcast(self):
        """Send flirty AI-generated broadcast to main room (attraction)."""
        msg = await self.ai_handler.generate_lobby_message()
        self.logger.info(f"[{self.username}] Sending AI Broadcast: {msg}")
        
        # Switch to #allindiachat.com
        try:
            channel_tab = self.page.locator(".kiwi-statebrowser-channel[data-name='#allindiachat.com'], div[role='tab']:has-text('#allindiachat.com')").first
            if await channel_tab.count() > 0:
                # Use force=True to bypass invisible overlays
                await channel_tab.click(force=True, timeout=5000)
                await asyncio.sleep(0.5)
        except: pass

        # Send
        target_input = self.page.locator(".kiwi-ircinput-editor").first
        if await target_input.count() > 0:
            # Ensure it's not hidden by some weird CSS before trying
            await self._type_naturally(target_input, msg)
            try:
                await target_input.press("Enter", timeout=5000)
            except:
                self.logger.warning("Locator.press Enter failed. Falling back to JS-Enter.")
                await self.js_press_enter(".kiwi-ircinput-editor")
            self.logger.info("Broadcast sent.")
            return True
        return False

    async def get_unread_chats(self):
        """Finds unread PM tabs."""
        chats = []
        try:
            tabs = self.page.locator(".kiwi-statebrowser-channel")
            count = await tabs.count()
            
            for i in range(count):
                tab = tabs.nth(i)
                try:
                    name = await tab.get_attribute("data-name", timeout=1000)
                    if not name or name.startswith("#") or name == "*" or "allindiachat" in name:
                        continue # Skip channels
                        
                    # Check unread
                    label = tab.locator(".kiwi-statebrowser-channel-label")
                    is_unread = False
                    if await label.count() > 0 and await label.is_visible():
                        class_attr = await label.get_attribute("class") or ""
                        text = await label.inner_text()
                        if "highlight" in class_attr or (text.strip().isdigit() and int(text.strip()) > 0):
                            is_unread = True
                    
                    if is_unread:
                        chats.append({'name': name, 'element': tab})
                except: continue
        except Exception as e:
            self.logger.error(f"Error checking unreads: {e}")
            
        return chats

    async def open_chat(self, chat_obj):
        """Clicks the tab."""
        try:
            # Use force=True to bypass invisible overlays
            await chat_obj['element'].click(force=True)
            return True
        except: return False

    async def wait_for_chat_load(self, name):
        """Verify chat header matches expected name."""
        try:
            # Check 1: Active Tab Data Attribute (Most reliable in Kiwi)
            active_tab = self.page.locator(".kiwi-statebrowser-channel.kiwi-statebrowser-channel--active")
            
            for i in range(10): # Optimized: 1 second max (10 × 0.1s)
                # Try getting data-name from active tab
                if await active_tab.count() > 0:
                    active_name = await active_tab.get_attribute("data-name")
                    if active_name and (name.lower() == active_name.lower() or name.lower() in active_name.lower()):
                         return True
                
                # Check Header as fallback
                header = self.page.locator(".kiwi-header-name").first
                if await header.is_visible():
                     h_text = await header.inner_text()
                     if name.lower() in h_text.lower():
                          return True

                await asyncio.sleep(0.1)  # Faster polling
            
            return False
        except Exception as e:
            self.logger.error(f"Wait load error: {e}")
            return False

    async def get_chat_history(self):
        """Scrape messages."""
        chat_history = []
        try:
            history_elements = self.page.locator(".kiwi-messagelist-message")
            count = await history_elements.count()
            start_idx = max(0, count - 15) # Reduced from 20 for speed
            for i in range(start_idx, count):
                msg_el = history_elements.nth(i)
                body_el = msg_el.locator(".kiwi-messagelist-body")
                text = await body_el.inner_text() if await body_el.count() > 0 else await msg_el.inner_text()
                
                classes = await msg_el.get_attribute("class") or ""
                role = "assistant" if "kiwi-messagelist-message--own" in classes else "user"
                chat_history.append({"role": role, "content": text})
        except: pass
        
        if not chat_history: chat_history.append({"role": "user", "content": "Hello"})
        return chat_history

    async def _type_naturally(self, locator, text):
        """
        Type text character by character at natural human speed.
        Simulates realistic typing patterns with variable delays.
        """
        try:
            # Focusing is often safer than clicking when overlays are present
            await locator.focus()
            # Clear existing text via evaluate to be sure
            await locator.evaluate("el => el.innerText = ''")
            
            for i, char in enumerate(text):
                # 30-70ms per character is the human "sweet spot"
                base_delay = random.uniform(0.03, 0.07)
                
                if char in '.!?,;':
                    base_delay += random.uniform(0.2, 0.4)
                
                await locator.type(char)
                await asyncio.sleep(base_delay)
            return True
        except Exception as e:
            self.logger.warning(f"Typing simulation failed: {e}. Falling back to direct evaluate.")
            try:
                # Direct JS injection as absolute fallback
                await locator.evaluate(f"(el, t) => {{ el.innerText = t; el.dispatchEvent(new Event('input', {{ bubbles: true }})); }}", text)
                return True
            except:
                return False

    async def send_message(self, text):
        try:
            pm_input = self.page.locator(".kiwi-ircinput-editor").first
            if await pm_input.count() > 0:
                # Use natural typing instead of instant fill
                await self._type_naturally(pm_input, text)
                await pm_input.press("Enter")
                return True
        except: pass
        return False

    async def return_to_lobby(self):
        """Return to lobby only if needed. In SiteTwo (Kiwi), we can often stay in PMs."""
        # For now, we still return to lobby to see the unread markers on the left
        # But we make it much faster.
        try:
             main_tab = self.page.locator(".kiwi-statebrowser-channel[data-name='#allindiachat.com']").first
             if await main_tab.count() > 0: 
                 await main_tab.click()
                 await asyncio.sleep(0.1) # Minimum wait
        except: pass
