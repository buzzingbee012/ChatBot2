import asyncio
import random
import logging
from .base_bot import BaseBot
from .utils import Dashboard

class IBBot(BaseBot):
    def __init__(self, config):
        super().__init__(config, bot_name="IBBot")
        self.selectors = config.get('selectors', {})
        self.allowed_domain = config['bot'].get('allowed_domain', 'chatib.us')

    async def entry_point(self):
        """Standard guest entry for Chatib."""
        entry_url = self.selectors.get('entry_url', "https://www.chatib.us/")
        self.logger.info(f"Navigating to {entry_url}...")
        
        try:
            # Aggressive script/popup blocking at session level
            await self.context.add_init_script("""
                window.__gpp = window.__gpp || function() { return ''; };
                window.__tcfapi = window.__tcfapi || function() { return ''; };
            """)

            # Block common ad/tracker domains to prevent popups
            async def block_ads(route):
                bad_domains = ["googleads", "doubleclick", "adnxs", "inmobi", "taboola", "outbrain"]
                if any(domain in route.request.url for domain in bad_domains):
                    await route.abort()
                else:
                    await route.continue_()
            
            await self.page.route("**/*", block_ads)

            await self.page.goto(entry_url)
            await self.page.wait_for_timeout(3000)

            # Check if already in
            if await self._check_exists(self.selectors.get('message_input')):
                self.logger.info("Already in chat.")
                return True

            Dashboard.status("Filling Guest Form...")
            
            # Username
            username = self.ai_handler.generate_username()
            self.logger.info(f"Using random username: {username}")
            await self.safe_type(self.selectors['username_input'], username)
            
            # Gender
            gender = self.config['guest_profile'].get('gender', 'Female')
            if gender.lower() == 'female':
                await self.page.check(self.selectors['gender_female_radio'])
            else:
                await self.page.check(self.selectors['gender_male_radio'])

            # Age
            age = str(self.config['guest_profile'].get('age', '32'))
            await self.page.select_option(self.selectors['age_dropdown'], age)

            # Country & State
            await self.page.select_option(self.selectors['country_dropdown'], self.config['guest_profile'].get('country', 'India'))
            await self.page.wait_for_timeout(2000) # Wait for states to load
            await self.page.select_option(self.selectors['state_dropdown'], self.config['guest_profile'].get('state', 'Delhi'))

            # Submit
            await self.page.click(self.selectors['start_chat_btn'])
            self.logger.info("Form submitted. Waiting for transition...")
            
            # Handle Agreement
            agree_sel = self.selectors.get('agree_btn', "button.agree")
            try:
                await self.page.wait_for_selector(agree_sel, timeout=10000)
                await self.page.click(agree_sel)
                self.logger.info("Clicked Agree.")
            except:
                self.logger.info("Agree button not found or skipped.")

            # Final check for inbox tab or message input
            await self.page.wait_for_timeout(5000)
            if await self._check_exists(self.selectors.get('inbox_tab')):
                 self.logger.info("Successfully entered Chatib!")
                 # Ensure Inbox is active
                 await self.page.click(self.selectors['inbox_tab'])
                 return True
            
            return False

        except Exception as e:
            self.logger.error(f"Entry Failed: {e}")
            return False

    async def handle_ads_and_popups(self):
        """Aggressive popup/overlay handling for Chatib."""
        try:
            # 1. Close extra pages
            if len(self.context.pages) > 1:
                for p in self.context.pages[1:]:
                    try:
                        if self.allowed_domain not in p.url:
                            self.logger.warning(f"Closing popup page: {p.url}")
                            await p.close()
                    except: pass

            # 2. Key-press Escape to clear modals
            await self.page.keyboard.press("Escape")

            # 3. JS Nuke common ad containers
            await self.page.evaluate("""
                () => {
                    const bad = ['.google-auto-placed', '#google_vignette', 'ins.adsbygoogle', 'iframe[id^="aswift"]'];
                    bad.forEach(s => {
                        document.querySelectorAll(s).forEach(el => el.remove());
                    });
                }
            """)

            # 4. Click specific dismiss buttons
            dismiss_sel = self.selectors.get('ad_dismiss_btn', '#dismiss-button')
            if await self._check_exists(dismiss_sel):
                await self.page.click(dismiss_sel)

        except: pass

    async def perform_broadcast(self):
        """No broadcast for Chatib in this implementation yet."""
        return False

    async def get_unread_chats(self):
        """Finds red badges in the inbox list."""
        chats = []
        try:
            badge_sel = self.selectors.get('unread_badge', ".meta-circle.red")
            item_sel = self.selectors.get('inbox_item', ".list-group-item")
            
            badges = await self.page.query_selector_all(badge_sel)
            for badge in badges:
                try:
                    # Find parent item
                    item = await badge.evaluate_handle("el => el.closest('.list-group-item')")
                    if item:
                        username = await item.evaluate("el => el.getAttribute('data-username')") or "Unknown"
                        chats.append({'name': username, 'element': item})
                except: continue
        except Exception as e:
            self.logger.error(f"Error checking unreads: {e}")
        return chats

    async def open_chat(self, chat_obj):
        """Clicks the inbox item."""
        try:
            await chat_obj['element'].click()
            return True
        except: return False

    async def wait_for_chat_load(self, name):
        """Verify chat header or history container text matches."""
        try:
            for _ in range(10): # 5 seconds
                # Check for the name in the active chat area
                # .chat-history often includes the name or it shows up in the 'write to...' area
                content = await self.page.evaluate("""
                    () => {
                        const h = document.querySelector('.chat-history') || document.querySelector('.msg_history');
                        return h ? h.innerText : '';
                    }
                """)
                if name.lower() in content.lower():
                    # Also wait for messages to settle
                    await asyncio.sleep(1)
                    return True
                await asyncio.sleep(0.5)
            return False
        except: return False

    async def get_chat_history(self):
        """Scrapes history from the chat window."""
        history = []
        try:
            # Chatib uses bubbles with 'incoming' or 'outgoing' classes usually
            # Note: Selectors might need refinement based on exact DOM
            bubbles = await self.page.query_selector_all(".message")
            count = len(bubbles)
            start_idx = max(0, count - 20)
            for i in range(start_idx, count):
                bubble = bubbles[i]
                try:
                    text = await bubble.inner_text()
                    classes = await bubble.get_attribute("class") or ""
                    role = "user" if "incoming" in classes else "assistant"
                    if text.strip():
                        history.append({"role": role, "content": text.strip()})
                except: continue
        except: pass
        
        if not history: 
            history.append({"role": "user", "content": "hello"}) # Fallback
        return history

    async def send_message(self, text):
        """Types and sends message."""
        try:
            input_sel = self.selectors.get('message_input', "#msg_content")
            if await self._check_exists(input_sel):
                await self.page.fill(input_sel, "") # Clear
                await self.page.type(input_sel, text, delay=50)
                await self.page.keyboard.press("Enter")
                
                # Check if still there (sometimes Enter doesn't work)
                await self.page.wait_for_timeout(500)
                val = await self.page.input_value(input_sel)
                if val:
                    await self.page.click(self.selectors.get('send_btn', ".msg_send_btn"))
                
                return True
        except: pass
        return False

    async def return_to_lobby(self):
        """Clicks the back to inbox button."""
        try:
            back_btn = self.selectors.get('back_to_inbox_btn', ".hide_messages")
            await self.page.click(back_btn)
            await self.page.wait_for_timeout(1000)
        except: pass
