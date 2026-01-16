import asyncio
import random
from .base_bot import BaseBot
from .utils import Dashboard

class SiteTwoBot(BaseBot):
    def __init__(self, config):
        super().__init__(config, bot_name="SiteTwoBot")
        self.username = config['guest_profile']['username']
        # Site specific config
        self.site_config = config['site_two']
        self.max_replies_per_user = self.site_config.get('max_replies', 20)

    async def entry_point(self):
        """Legacy guest_entry logic."""
        url = self.site_config['url']
        self.logger.info(f"Navigating to {url}...")
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
            
            await start_btn.click()
            self.logger.info("Clicked Start.")
            
            chat_loaded = self.page.locator(".kiwi-controlinput-input, .kiwi-statebrowser-channels, .kiwi-header-name")
            await chat_loaded.first.wait_for(state="visible", timeout=20000)
            
            self.logger.info("Successfully entered chat!")
            return True

        except Exception as e:
            self.logger.error(f"Entry Failed: {e}")
            return False

    async def handle_ads_and_popups(self):
        """Checks for and closes Google Vignettes/Overlays."""
        # Extracted existing logic
        try:
            if await self.page.locator("#dismiss-button").count() > 0:
                 await self.page.click("#dismiss-button")
                 return

            for frame in self.page.frames:
                 if "google" in frame.name or "vignette" in frame.name or "google" in frame.url:
                     try:
                         close_btns = frame.locator("div[aria-label='Close ad'], svg[aria-label='Close ad'], #dismiss-button")
                         if await close_btns.count() > 0:
                             if await close_btns.first.is_visible():
                                 await close_btns.first.click()
                                 return
                     except: pass
            
            # Close rogue pages
            if len(self.context.pages) > 1:
                for p in self.context.pages[1:]:
                     try:
                         if "allindiachat" not in p.url: await p.close()
                     except: pass
        except: pass 

    async def perform_broadcast(self):
        """Send broadcast to main room."""
        self.logger.info("Sending Broadcast Message...")
        Dashboard.outgoing("Broadcast: hello guys")
        
        # Switch to #allindiachat.com
        try:
            channel_tab = self.page.locator(".kiwi-statebrowser-channel[data-name='#allindiachat.com'], div[role='tab']:has-text('#allindiachat.com')").first
            if await channel_tab.count() > 0:
                await channel_tab.click()
                await self.page.wait_for_timeout(500)
        except: pass

        # Send
        target_input = self.page.locator(".kiwi-ircinput-editor").first
        if await target_input.is_visible():
            await target_input.click()
            await target_input.fill("Hello")
            await target_input.press("Enter")
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
            await chat_obj['element'].click()
            await self.page.wait_for_timeout(1000)
            return True
        except: return False

    async def get_chat_history(self):
        """Scrape messages."""
        chat_history = []
        try:
            history_elements = self.page.locator(".kiwi-messagelist-message")
            count = await history_elements.count()
            start_idx = max(0, count - 10)
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

    async def send_message(self, text):
        try:
            pm_input = self.page.locator(".kiwi-ircinput-editor").first
            if await pm_input.is_visible():
                await pm_input.click()
                await pm_input.fill(text)
                await pm_input.press("Enter")
                return True
        except: pass
        return False

    async def return_to_lobby(self):
        """Return to main room."""
        try:
             main_tab = self.page.locator(".kiwi-statebrowser-channel[data-name='#allindiachat.com']").first
             if await main_tab.count() > 0: await main_tab.click()
        except: pass
