import asyncio
from .base_bot import BaseBot
from .utils import Dashboard

class WireBot(BaseBot):
    def __init__(self, config, instance_id=1):
        super().__init__(config, bot_name=f"WireBot-{instance_id}")
        self.ai = self.ai_handler # Alias for compatibility
        wc_config = config.get('wireclub', {})
        self.max_replies_per_user = wc_config.get('max_replies', self.max_replies_per_user)
        self.username = wc_config.get('email') or wc_config.get('username')
        self.password = wc_config.get('password')
        self.selectors = wc_config.get('selectors', {})

    async def entry_point(self):
        """Handles login to Wireclub."""
        if not self.username or not self.password:
            self.logger.error("No credentials for Wireclub.")
            return False

        url = self.config['wireclub'].get('url', "https://www.wireclub.com/")
        
        while True:
            self.logger.info(f"Navigating to {url}...")
            try:
                await self.page.goto(url, timeout=60000)
            except Exception as e:
                self.logger.error(f"Navigation Timeout/Error: {e}")
                return False
                
            try:
                # Check if already logged in
                if await self._check_exists("form[action='/logout']") or await self._check_exists(".user-link"):
                    self.logger.info("Already logged in.")
                else:
                    # Login
                    login_sel = self.selectors.get('login_btn', 'a.header-link.sign-in')
                    if await self._check_exists(login_sel):
                        await self.page.click(login_sel)
                        
                        # Fill
                        await self.page.fill(self.selectors.get('username_input', "#email"), self.username)
                        await self.page.fill(self.selectors.get('password_input', "#password"), self.password)
                        
                        submit_sel = self.selectors.get('submit_btn', "input.submit.button.feature-buttons")
                        await self.page.wait_for_selector(submit_sel, state='visible')
                        
                        self.logger.info("Submitting Login and waiting for navigation...")
                        try:
                            async with self.page.expect_navigation(timeout=30000):
                                await self.page.click(submit_sel)
                            self.logger.info("Login navigation finished.")
                        except Exception as nav_e:
                            self.logger.warning(f"Login navigation wait check: {nav_e}. Proceeding...")
                            await self.page.wait_for_load_state('networkidle', timeout=10000)

                    # Captcha Handling
                    if await self._check_exists("#captcha-text"):
                        self.logger.warning("Captcha Detected! Killing browser session and waiting 2 minutes...")
                        await self.page.close()
                        await self.context.clear_cookies()
                        await asyncio.sleep(120)
                        
                        self.logger.info("Restarting login attempt...")
                        self.page = await self.context.new_page()
                        continue
                    
                # Ensure we navigate to the lobby for operations
                lobby_url = self.selectors.get('room_url', "https://www.wireclub.com/chat/room/private_chat_lobby")
                if "private_chat_lobby" not in self.page.url:
                    self.logger.info(f"Navigating to {lobby_url}...")
                    try:
                        await self.page.goto(lobby_url)
                        await self.page.wait_for_load_state('networkidle', timeout=15000)
                    except Exception as le:
                        self.logger.warning(f"Lobby navigation warning: {le}")
                
                return True
            except Exception as e:
                self.logger.error(f"Login Error: {e}")
                try:
                    await self.page.screenshot(path="login_error.png")
                    with open("login_error.html", "w", encoding="utf-8") as f:
                        f.write(await self.page.content())
                except:
                    pass
                return False

    async def handle_ads_and_popups(self):
        """Wireclub ads/modals."""
        # TODO: Identify specific popups
        pass

    async def perform_broadcast(self):
        """Sends a broadcast message to the main room."""
        try:
            # Ensure we are in the room
            if "private_chat_lobby" not in self.page.url:
                 await self.page.goto(self.selectors['room_url'])
                 await self.page.wait_for_load_state('networkidle')
            
            msg = self.ai.get_next_message()
            self.logger.info(f"Broadcasting: {msg}")
            
            input_sel = self.selectors.get('room_input')
            send_sel = self.selectors.get('room_send')
            
            if await self._check_exists(input_sel):
                await self.safe_type(input_sel, msg)
                await self.safe_click(send_sel)
                self.stats_tracker.increment_today(bot_name=self.logger.name)
                return True
            else:
                self.logger.warning("Broadcast input not found.")
                
        except Exception as e:
            self.logger.error(f"Error performing broadcast: {e}")

    async def get_unread_chats(self):
        """Returns a list of unread chat identifiers (e.g. element IDs)."""
        unread_sel = self.selectors.get('pm_notification', '.notification') # Fallback
        # We need to find elements that imply a specific chat session
        # The selector in config is '.private-chat-session.notification'
        elements = await self.page.query_selector_all(self.selectors.get('pm_notification'))
        chat_ids = []
        for el in elements:
            # Get the ID of the session element, e.g. "private-chat-UserXYZ"
            uid = await el.get_attribute("id")
            if uid:
                chat_ids.append({'name': uid, 'id': uid})
        
        if chat_ids:
            # self.logger.debug(f"Found unread chats: {chat_ids}")
            pass
        return chat_ids

    async def open_chat(self, chat_obj):
        """Opens/Focuses the chat for the given chat_obj (dict)."""
        chat_id = chat_obj.get('id', chat_obj.get('name'))
        self.current_chat_id = chat_id
        # Click to focus
        await self.safe_click(f"#{chat_id}")
        return True

    async def wait_for_chat_load(self, name):
        """Verify session container is visible."""
        if not self.current_chat_id: return False
        try:
            # Wait for body to be visible
            await self.page.wait_for_selector(f"#{self.current_chat_id} .chat-body", state='visible', timeout=5000)
            return True
        except:
            return False

    async def get_chat_history(self):
        """Scrapes text from the current chat window using specific HTML structure."""
        if not hasattr(self, 'current_chat_id') or not self.current_chat_id:
            return []
        
        # Based on user-provided HTML:
        # Container: .chat-body .content
        # Messages: .message that are .partner or .self
        
        # We still try candidates to find the container, but prioritize the known one
        candidates = [
            '.chat-body .content', # Confirmed by user HTML
            self.selectors.get('pm_history', '.conversation-history'),
            '.conversation', 
            '.messages',
            '.chat-messages', 
            '.chat-log'
        ]
        candidates = list(dict.fromkeys(candidates))
        
        messages = []
        
        for selector in candidates:
            sel = f"#{self.current_chat_id} {selector}"
            self.logger.debug(f"debug: trying history selector: {sel}")
            
            try:
                # Check if container exists
                container = await self.page.query_selector(sel)
                if not container:
                    continue

                # If we found the specific Wireclub container, try to parse individual messages for better context
                # User HTML: <div class="partner message">...</div>
                msg_elements = await container.query_selector_all(".message")
                
                if msg_elements:
                    # self.logger.debug(f"Found {len(msg_elements)} structured messages in {selector}")
                    for el in msg_elements:
                        try:
                            # Text is usually in .message-body
                            body = await el.query_selector(".message-body")
                            text = await body.inner_text() if body else await el.inner_text()
                            
                            # Determine Role
                            # Check class for 'self' or 'partner'
                            classes = await el.get_attribute("class") or ""
                            role = "assistant" if "self" in classes else "user"
                            
                            if text and text.strip():
                                messages.append({"role": role, "content": text.strip()})
                        except:
                            continue
                    
                    if messages:
                        return messages
                
                # Fallback: exact parsing failed, just grab text lines
                raw_text = await container.inner_text()
                if raw_text and len(raw_text.strip()) > 0:
                    self.logger.info(f"Fallback Scraping ({len(raw_text)} chars): {raw_text[:50]}...")
                    lines = raw_text.split('\n')
                    for line in lines:
                        if line.strip():
                            # Assume user if we don't know
                            messages.append({"role": "user", "content": line.strip()})
                    return messages

            except Exception as e:
                self.logger.error(f"Error parsing history with {selector}: {e}")
                continue

        self.logger.warning(f"Failed to find history for {self.current_chat_id}")
        return []

    async def send_message(self, text):
        """Sends a message to the CURRENTLY OPEN chat."""
        if not hasattr(self, 'current_chat_id') or not self.current_chat_id:
            self.logger.error("No current chat ID to send message to.")
            return

        # Scope input to the current chat ID
        input_sel = f"#{self.current_chat_id} {self.selectors.get('pm_input')}"
        
        try:
            await self.safe_type(input_sel, text)
            await self.page.keyboard.press("Enter")
            self.stats_tracker.increment_today(bot_name=self.logger.name)
            return True
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")

    async def return_to_lobby(self):
        """Closes or minimizes the current chat."""
        if hasattr(self, 'current_chat_id') and self.current_chat_id:
            # Click the close button on the tab
            # Selector: #{id} .close
            # close_sel = f"#{self.current_chat_id} .close"
            # await self.safe_click(close_sel)
            
            # User requested NOT to close the window.
            # We just de-select it from our internal tracking so we can process others if needed.
            self.current_chat_id = None
