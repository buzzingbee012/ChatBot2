import asyncio
import random
import logging
from .base_bot import BaseBot
from .utils import Dashboard

class IBBot(BaseBot):
    def __init__(self, config, instance_id=1):
        super().__init__(config, bot_name=f"IBBot-{instance_id}")
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

            # Randomize Country & State
            locations = [
                {"country": "India", "state": "Delhi"},
                {"country": "India", "state": "Maharashtra"},
                {"country": "India", "state": "Karnataka"}
            ]
            loc = random.choice(locations)
            self.logger.info(f"Selected Location: {loc['country']}, {loc['state']}")

            # Country & State
            await self.page.select_option(self.selectors['country_dropdown'], loc['country'])
            await self.page.wait_for_timeout(2000) # Wait for states to load
            await self.page.select_option(self.selectors['state_dropdown'], loc['state'])

            # Check button state before click
            btn_sel = self.selectors['start_chat_btn']
            is_disabled = await self.page.is_disabled(btn_sel)
            if is_disabled:
                 self.logger.warning(f"Start Chat button is DISABLED. Triggering events...")
                 # Try to force trigger events
                 await self.page.dispatch_event(self.selectors['username_input'], 'blur')
                 await self.page.dispatch_event(self.selectors['age_dropdown'], 'change')
                 await self.page.wait_for_timeout(1000)
                 
                 # Check again
                 if await self.page.is_disabled(btn_sel):
                     self.logger.error("Button still disabled. Capturing state...")
                     await self.page.screenshot(path="ib_entry_disabled.png")

            # Check for Username availablity / Error
            for retry in range(3):
                # Check for error text adjacent to input
                is_error = await self.page.locator(".username_check_msg:has-text('taken'), .text-danger:has-text('taken')").count() > 0
                
                # Also check validation state
                btn_disabled = await self.page.is_disabled(self.selectors['start_chat_btn'])
                
                if is_error or btn_disabled:
                     # Check if it's specifically a username issue
                     error_text = await self.page.locator(".username_check_msg, .text-danger").first.inner_text() if await self.page.locator(".username_check_msg, .text-danger").count() > 0 else ""
                     
                     if "taken" in error_text.lower() or btn_disabled:
                         self.logger.warning(f"Username '{username}' might be taken (Error: {error_text}). Retrying...")
                         username = self.ai_handler.generate_username()
                         await self.safe_type(self.selectors['username_input'], username)
                         await self.page.dispatch_event(self.selectors['username_input'], 'blur')
                         await self.page.wait_for_timeout(1000)
                         continue
                break

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
            try:
                await self.page.screenshot(path="ib_entry_error.png")
            except: pass
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
                try:
                    await self.page.click(dismiss_sel, timeout=1000)
                except: pass

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
        # print(f"DEBUG: Checking context for {name}") 
        try:
            selectors = [
                 ".msg_head", # Likely header container
                 ".card-header",
                 ".user_name",
                 ".chat-history", 
                 ".msg_history", 
                 ".panel-heading", 
                 ".top_spac", 
                 "h4", 
                 ".media-heading", 
                 ".active-chat-title",
                 "#msg_history"
            ]

            msg_history_content = ""

            for i in range(10): # 1 second max (10 × 0.1s)
                # Check for the name in likely header elements
                msg_history_content = "" # Reset for this iteration
                for sel in selectors:
                     try:
                         element = await self.page.query_selector(sel)
                         if element:
                             text = await element.inner_text()
                             # Save content for fallback check
                             if "msg_history" in sel or "chat-history" in sel: 
                                 msg_history_content = text
                             
                             if name.lower() in text.lower():
                                 return True
                     except: pass
                
                # Check page title
                title = await self.page.title()
                if name.lower() in title.lower():
                    return True

                # FAST FALLBACK: If chat history is loaded, proceed immediately
                if len(msg_history_content) > 5:
                    return True

                await asyncio.sleep(0.1) # Faster polling

            # Debug: Log what we found to help fix it
            debug_info = []
            for sel in selectors:
                try:
                    el = await self.page.query_selector(sel)
                    if el: debug_info.append(f"{sel}: '{await el.inner_text()}'")
                except: pass
            
            # Failed to verify context within timeout
            msg = f"Context Verification Failed for '{name}'. Found headers: {debug_info}"
            self.logger.warning(msg)
            return False
        except Exception as e:
             self.logger.error(f"Wait load error: {e}")
             print(f"DEBUG ERROR: {e}")
             return False

    async def get_chat_history(self):
        """Scrapes history from the chat window."""
        history = []
        try:
            # Chatib uses specific classes for messages
            # Incoming: .incoming_msg -> .received_msg -> .received_withd_msg -> p
            # Outgoing: .outgoing_msg -> .sent_msg -> p (assumed based on standard template)
            
            # Select both types
            all_msgs = await self.page.query_selector_all(".incoming_msg, .outgoing_msg")
            
            # Limit history to last 20 messages
            count = len(all_msgs)
            start_idx = max(0, count - 20)
            
            # Select both types
            all_msgs = await self.page.query_selector_all(".incoming_msg, .outgoing_msg")
            
            # Limit history to last 20 messages
            count = len(all_msgs)
            start_idx = max(0, count - 20)
            
            for i in range(start_idx, count):
                msg_el = all_msgs[i]
                try:
                    # Check class to determine role
                    classes = await msg_el.get_attribute("class") or ""
                    role = "user" if "incoming_msg" in classes else "assistant"
                    
                    # Extract text from paragraph
                    p_tag = await msg_el.query_selector("p")
                    if p_tag:
                         text = await p_tag.inner_text()
                         if text and text.strip():
                             history.append({"role": role, "content": text.strip()})
                except: continue
        except Exception as e:
            self.logger.error(f"History scrape error: {e}")
        
        # DEBUG LOGGING to verify context
        if history:
            self.logger.info(f"Scraped History ({len(history)} msgs): {[h['content'][:20] for h in history]}")
        else:
             self.logger.warning("Scraped History is EMPTY. Using fallback.")

        if not history: 
            history.append({"role": "user", "content": "hello"}) # Fallback
        return history

    async def send_message(self, text):
        """Sends message by typing into contenteditable div and clicking send."""
        try:
            # Target the visible contenteditable div, NOT the hidden input
            input_sel = "#contenteditablediv"
            hidden_input = "#msg_content"
            
            self.logger.info(f"Typing message to contenteditable: '{text}'")
            
            # Focus and clear
            await self.page.click(input_sel)
            await self.page.evaluate(f"document.querySelector('{input_sel}').innerText = ''")
            
            # Type visibly (Instant)
            await self.page.type(input_sel, text, delay=0)
            
            # Small delay for sync to hidden input
            await self.page.wait_for_timeout(200)
            
            self.logger.info(f"Text typed, clicking Send button")
            
            # Click the send button 
            await self.page.click('.msg_send_btn', force=True)
            
            # Wait for send
            await self.page.wait_for_timeout(1000)
            
            # Verify input was cleared (check hidden input value)
            verification = await self.page.evaluate("""
                () => {
                    const hiddenVal = $('#msg_content').val();
                    const divText = document.querySelector('#contenteditablediv').innerText;
                    return {
                        hiddenInputCleared: !hiddenVal || hiddenVal === '',
                        divCleared: !divText || divText.trim() === '',
                        hiddenVal: hiddenVal,
                        divText: divText
                    };
                }
            """)
            
            self.logger.info(f"Verification: {verification}")
            
            if verification.get('divCleared'):
                self.logger.info(f"[OK] Message sent - input cleared")
            else:
                self.logger.warning(f"[WARN] Input not cleared")
            
            return True
                
        except Exception as e:
            self.logger.error(f"Send Message Error: {e}")
            return False

    async def return_to_lobby(self):
        """Clicks the back to inbox button."""
        try:
            back_btn = self.selectors.get('back_to_inbox_btn', ".hide_messages")
            await self.page.click(back_btn, timeout=1000)
            await self.page.wait_for_timeout(100)
        except: pass
