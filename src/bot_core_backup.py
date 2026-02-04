import asyncio
import logging
import json
import os
import random
from playwright.async_api import async_playwright
from .utils import Logger, random_delay
from .ai_handler import AIHandler

class ChatBot:
    def __init__(self, config):
        self.config = config
        self.logger = Logger(config['bot'].get('log_file', 'conversation_logs.txt'))
        self.ai = AIHandler(config)
        self.browser = None
        self.context = None
        self.page = None
        self.running = False

    async def start(self):
        """Initializes Playwright and starts the browser."""
        self.playwright = await async_playwright().start()
        headless = self.config['bot'].get('headless', True)
        self.browser = await self.playwright.chromium.launch(headless=headless)
        
        # Custom logic: If we want fresh guest entries, we shouldn't load old sessions.
        # But if you want to persist, you can uncomment this.
        # For now, we will forcing a FRESH session every time to avoid "User already exists".
        if os.path.exists('session.json'):
             try:
                 os.remove('session.json')
                 self.logger.info("Deleted old session file.")
             except:
                 pass

        self.context = await self.browser.new_context()
        self.logger.info("Starting new session.")
        
        # Create main page FIRST
        self.page = await self.context.new_page()

        # AGGRESSIVE POPUP BLOCKER
        # Attach handler AFTER creating main page so it doesn't trigger for it.
        async def handle_popup(popup):
            if popup != self.page:
                self.logger.warning(f"Popup detected! Closing: {popup.url}")
                await popup.close()
            
        self.context.on("page", handle_popup)
        
        # NAVIGATION LOCK: Prevent main page from redirecting to other sites
        async def route_handler(route):
            request = route.request
            allowed_domain = self.config['bot'].get('allowed_domain', 'chatib.us')
            # Only restrict MAIN FRAME navigation (resource_type='document')
            if request.resource_type == "document":
                # Allow about:blank, allow main domain, and CRITICAL CMP scripts
                if allowed_domain not in request.url and "about:blank" not in request.url:
                    # Allow zm-inmobi (CMP) to prevent "window.__gpp is not a function" crash
                    if "inmobi.com" in request.url:
                         await route.continue_()
                         return

                    self.logger.debug(f"BLOCKED REDIRECT to: {request.url}")
            
            # Also generic block for known bad resource types if needed
            # For now, just allow everything else to ensure site works
            await route.continue_()

        await self.page.route("**/*", route_handler)
        # Actually blocking images might break the chat avatars. Let's just block popups for now.

    async def guest_entry(self):
        """Wrapper for guest entry with retries."""
        max_retries = 3
        for attempt in range(max_retries):
            self.logger.info(f"Guest Entry Attempt {attempt + 1}/{max_retries}")
            
            if await self._attempt_guest_entry():
                self.logger.info("Guest Entry Successful!")
                return True
            
            self.logger.warning("Guest entry failed. Refreshing page and retrying in 5 seconds...")
            from .utils import Dashboard
            Dashboard.status("Entry failed. Refreshing...")
            
            try:
                # RECOVERY: Check if page is dead
                if self.page.is_closed():
                    self.logger.warning("Main page was closed. Recreating...")
                    self.page = await self.context.new_page()
                
                await self.page.reload()
                await self.page.wait_for_timeout(5000)
            except Exception as e:
                self.logger.error(f"Recovery failed: {e}")
                pass
        
        self.logger.error("All guest entry attempts failed.")
        return False

    async def _attempt_guest_entry(self):
        """Fills out the Guest Entry form (Single Attempt)."""
        from .utils import Dashboard  # Import here to avoid circular dependency
        
        entry_url = self.config['selectors']['entry_url']
        try:
            # Polyfill for GPP to prevent JS errors if adblock kills it
            await self.page.add_init_script("""
                window.__gpp = window.__gpp || function() { return ''; };
                window.__tcfapi = window.__tcfapi || function() { return ''; };
                window.uspApm = window.uspApm || { get: function() { return ''; } };
            """)

            # If we are not on the entry page, go there
            if "chatib.us" not in self.page.url:
                 await self.page.goto(entry_url)
                 self.logger.info(f"Navigated to {entry_url}")
            
            # Additional check: are we ALREADY in chat?
            # We check for the message input to confirm we are inside.
            # Using URL "chat" is buggy because "chatib.us" contains "chat".
            chat_indicator = self.config['selectors'].get('message_input', '#msg_content')
            is_in_chat = False
            
            # Check main page
            if await self._check_exists(chat_indicator):
                 is_in_chat = True
            else:
                 # Check frames
                 for frame in self.page.frames:
                     try:
                         if await frame.is_visible(chat_indicator):
                             is_in_chat = True
                             break
                     except: pass
            
            if is_in_chat:
                self.logger.info("Already inside chat. Skipping guest entry.")
                return True

            # Enable console logging for this attempt
            def console_handler(msg):
                self.logger.info(f"BROWSER CONSOLE: {msg.text}")
            self.page.on("console", console_handler)

            Dashboard.status("Filling guest profile...")

            # Wait for form to load
            await self.page.wait_for_timeout(2000)

            # ... [Input filling code omitted for brevity, assuming it works] ...
            # We will patch the Submit section below

            # 1-5 steps same as before...
            # 1. Username
            user_sel = self.config['selectors']['username_input']
            base_username = self.config['guest_profile']['username']
            username = f"{base_username}{random.randint(1000, 9999)}"
            Dashboard.status(f"Generated username: {username}")
            # Use SAFE TYPE (Frame Aware)
            typed = await self.safe_type(user_sel, username, delay=100)
            if typed: await self.page.wait_for_timeout(500)
            else:
                self.logger.error("Username input not found in any frame!")
                Dashboard.status("Error: Username field missing.")
                self.page.remove_listener("console", console_handler)
                return False

            # 2. Gender
            gender = self.config['guest_profile']['gender']
            if gender.lower() == 'female':
                gender_sel = self.config['selectors']['gender_female_radio']
                await self.safe_check(gender_sel)
            else:
                gender_sel = self.config['selectors'].get('gender_male_radio', "input[name='sexe'][value='homme']")
                await self.safe_check(gender_sel)
            await self.page.wait_for_timeout(500)

            # 3. Age
            age_sel = self.config['selectors']['age_dropdown']
            age = self.config['guest_profile']['age']
            await self.safe_select(age_sel, str(age))
            await self.page.wait_for_timeout(800)

            # 4. Country
            country_sel = self.config['selectors']['country_dropdown']
            country_val = self.config['guest_profile']['country']
            Dashboard.status("Selecting Country...")
            await self.safe_select(country_sel, country_val)
            await self.page.wait_for_timeout(2500) 
            
            # 5. State
            state_sel = self.config['selectors']['state_dropdown']
            state_val = self.config['guest_profile']['state']
            Dashboard.status("Selecting State...")
            await self.safe_select(state_sel, state_val)
            await self.page.wait_for_timeout(1000)
            
            # 6. Submit Strategy
            btn_sel = self.config['selectors']['start_chat_btn']
            Dashboard.status("Attempting to Submit...")
            
            # Strategy 1: JS Click on Button
            self.logger.info("Strategy 1: JS Click on #startChatNow")
            try:
                await self.page.evaluate(f"""
                    try {{
                        var btn = document.querySelector('{btn_sel}');
                        if (btn) btn.click();
                        else console.error('Button {btn_sel} not found for JS click');
                    }} catch(e) {{ }}
                """)
            except: pass
            
            await self.page.wait_for_timeout(1000)

            # Strategy 2: LoginGuest Direct Call
            self.logger.info("Strategy 2: Invoke loginGuest()")
            try:
                 await self.page.evaluate("if(typeof loginGuest === 'function') { loginGuest(); } else { console.error('loginGuest not found'); }")
            except Exception as e:
                 self.logger.warning(f"Could not invoke loginGuest: {e}")

            await self.page.wait_for_timeout(1000)

            # Strategy 3: Form Submit
            self.logger.info("Strategy 3: Form Submit")
            try:
                await self.page.evaluate("""
                    var btn = document.querySelector('#startChatNow');
                    if(btn && btn.form) {
                        btn.form.submit();
                    }
                """)
            except: pass
            
            # FINAL VERIFICATION: Did we actually get in?
            await self.page.wait_for_timeout(2000)
            
            # Stop listening before return
            self.page.remove_listener("console", console_handler)
            
            try:
                content = await self.page.content()
                if "Unable to access an error message" in content:
                     self.logger.error("Early detection: Validation error found!")
                     return False
            except Exception as e:
                # If page is navigating/closed, that's actually a GOOD sign (usually)
                self.logger.info(f"Page content check skipped due to navigation (Good sign): {e}")

            Dashboard.status("Form submitted. Waiting for page load...")
            
            # Use 'domcontentloaded' + explicit sleep instead.
            try:
                await self.page.wait_for_load_state('domcontentloaded', timeout=10000)
            except:
                pass # Proceed anyway
            
            await self.page.wait_for_timeout(5000) # Give UI time to settle
            
            # CHECK FOR BROWSER ERROR PAGE ("This page isn't working")
            try:
                content = await self.page.content()
                if "This page isn’t working" in content or "ERR_EMPTY_RESPONSE" in content:
                    self.logger.error("Browser error page detected! Triggering refresh...")
                    return False
                
                # CHECK FOR FORM ERRORS (User reported being stuck with error)
                # Common texts: "unavailable", "taken", "error", "invalid"
                # We check visible text roughly
                page_text = await self.page.inner_text("body")
                if "username is already" in page_text.lower() or "nickname already used" in page_text.lower():
                     self.logger.error("Username taken. Retrying...")
                     return False
                # Relaxed generic check: Only fail if we REALLY don't find the Agree button later.
                     
            except: pass

            # SUCCESS? Only if URL changed or we see chat elements? 
            # If we are strictly still on the exact entry URL and have no chat elements, we probably failed.
            if self.page.url == entry_url and not await self._check_exists(self.config['selectors']['message_input']):
                 # It's possible the URL stays same for SPA, but usually it changes to /chat
                 # But let's look for the Agree button or Chat elements before declaring success.
                 pass

            # SUCCESS CHECK: If "Agree" button is present, we are likely good!
            # We defer the "Generic Error" check until AFTER we try to find the button.
            
            self.logger.info("Guest entry form passed (preliminary). Checking for Agreement...")
            Dashboard.status("Checking for Agreement...")

            # 8. Handle "Agree" button - STATE AWARE CHECK
            # We need to know if we are on the Agreement page, still on Form, or already in Chat.
            
            agree_sel = self.config['selectors'].get('agree_btn', "button.agree")
            
            for i in range(15): # Increased wait time/retries for state transition
                # CHECK STATES
                is_agreement = await self._check_exists(agree_sel) or await self._check_text_exists("Agree") or await self._check_text_exists("Send")
                is_chat = await self._check_exists(self.config['selectors']['message_input']) or await self._check_exists("li.inbox")
                is_form = await self._check_exists(self.config['selectors']['username_input'])
                
                if is_chat:
                    self.logger.info("Detected Chat Interface. Success!")
                    break
                
                if is_form and not is_agreement:
                     # We are likely stuck on the form or it re-rendered
                     # Check for errors
                     page_text = await self.page.inner_text("body")
                     if "taken" in page_text or "error" in page_text.lower():
                         self.logger.error("Stuck on form with errors.")
                         # Don't return False immediately, wait a bit
                     self.logger.info(f"Still seeing form... waiting for transition (Attempt {i+1}).")
                     await self.page.wait_for_timeout(1000)
                     continue

                if is_agreement:
                    self.logger.info("Detected Agreement State. Attempting to click...")
                    
                    # Strategy 1: Find ALL buttons with 'agree' class or text
                    try:
                        buttons = await self.page.query_selector_all("button.agree, button[type='submit'], button.btn-primary")
                        for btn in buttons:
                            if await btn.is_visible():
                                txt = await btn.inner_text()
                                if any(x in txt.lower() for x in ["agree", "enter", "start", "ok", "send"]):
                                    await btn.click()
                                    await self.page.wait_for_timeout(500)
                    except: pass

                    # Strategy 2: Text Click
                    try:
                        if await self.safe_click("text=Agree"): pass
                        elif await self.safe_click("text=AGREE"): pass
                        elif await self.safe_click("text=Enter"): pass
                        elif await self.safe_click("text=Send"): pass
                        elif await self.safe_click("text=Start"): pass
                    except: pass
                    
                    # Verify if we moved past it
                    await self.page.wait_for_timeout(1000)
                    if await self._check_exists(self.config['selectors']['message_input']):
                        break
                
                await self.page.wait_for_timeout(1000)

            # 9. Click Inbox Tab to ensure we are in the right place
            # Click the '1 on 1 Chat' / Inbox tab to ensure we are seeing messages
            inbox_sel = self.config['selectors'].get('inbox_tab', 'li.inbox')
            self.logger.info(f"Clicking Inbox tab ({inbox_sel})...")
            
            # Simple visibility check first
            try:
                # Wait up to 5s for it to appear
                await self.page.wait_for_selector(inbox_sel, timeout=5000, state='visible')
            except: pass

            inbox_clicked = False
            # Strategy 1: Safe Click
            if await self.safe_click(inbox_sel):
                inbox_clicked = True
            
            # Strategy 2: Text Click (Fallback)
            if not inbox_clicked:
                try:
                    if await self.safe_click("text=Inbox"):
                        inbox_clicked = True
                        self.logger.info("Clicked 'Inbox' (Text Selector).")
                except: pass
            
            # Strategy 3: JS Click
            if not inbox_clicked:
                try:
                    await self.page.evaluate(f"document.querySelector('{inbox_sel}').click()")
                    self.logger.info("Clicked 'Inbox' (JS Click).")
                except: pass

            await self.page.wait_for_timeout(1000)
            
            # FINAL VERIFICATION: Did we actually get in?
            # Check for chat input OR inbox list OR inbox tab (header)
            chat_indicator = self.config['selectors'].get('message_input', '#msg_content')
            inbox_tab = self.config['selectors'].get('inbox_tab', '#inboxicon')
            
            # We need to use frame-aware check here too
            entered_chat = False
            
            # Check 1: Chat Input
            if await self._check_exists(chat_indicator):
                 entered_chat = True
            # Check 2: Inbox Tab (Header)
            elif await self._check_exists(inbox_tab):
                 entered_chat = True
            # Check 3: URl Check (Strong signal)
            elif "/chat" in self.page.url:
                 self.logger.info("URL contains '/chat'. Assuming success.")
                 entered_chat = True
            
            if not entered_chat:
                # One last check: "Log out" button?
                if await self.page.is_visible("text=Log out") or await self.page.is_visible("text=Logout"):
                     entered_chat = True

            if not entered_chat:
                self.logger.error("Form submitted but neither Chat Input nor Inbox Tab found. Entry likely failed.")
                return False

            # We do NOT save session for guest mode to avoid "User already exists" next time
            return True

        except Exception as e:
            self.logger.error(f"Error during guest entry: {e}")
            from .utils import Dashboard
            Dashboard.status(f"Entry failed: {e}")
            return False

    async def monitor_loop(self):
        """Main loop to monitor inbox and respond to unread messages."""
        self.running = True
        
        # Ensure we are on the chat page and inbox tab is selected
        inbox_sel = self.config['selectors'].get('inbox_tab', '#pills-chat-tab')
        
        self.logger.info("Attempting to click Inbox tab...")
        await self.safe_click(inbox_sel)

        self.logger.info("Starting inbox monitor loop...")
        from .utils import Dashboard
        Dashboard.status("Monitoring inbox for unread messages...")

        while self.running:
            try:
                # 0. proactively close ads
                await self.close_ads()

                # 1. Check for unread messages (Directly find red badges)
                unread_badge_sel = self.config['selectors']['unread_badge']
                
                # Check if the list container is even visible
                # We need to check frames for this too, but for flow control let's stick to tab clicking
                
                badges = []
                # Search main page
                badges.extend(await self.page.query_selector_all(unread_badge_sel))
                # Search frames
                for frame in self.page.frames:
                    try:
                        badges.extend(await frame.query_selector_all(unread_badge_sel))
                    except: pass

                if not badges:
                     # If no badges, we used to aggressively click the inbox tab.
                     # But if the list selector is wrong, this causes an infinite loop/scroll.
                     # Disabling this for now. We assume we are on the inbox from the start.
                     
                     # Check if we can see ANY list items just for logging?
                     # item_sel = self.config['selectors'].get('inbox_item', '.list-group-item')
                     # if not await self.page.is_visible(item_sel):
                     #    self.logger.debug("No list items visible either.")
                     pass
                     
                     # ORIGINAL LOGIC COMMENTED OUT TO STOP SCROLLING LOOP:
                     """
                     list_sel = self.config['selectors'].get('inbox_list', '.inbox_desc_history')
                     found_list = await self.page.is_visible(list_sel)
                     if not found_list:
                         for frame in self.page.frames:
                             if await frame.is_visible(list_sel):
                                 found_list = True
                                 break
                     
                     if not found_list:
                         self.logger.warning("Inbox list NOT visible. Clicking Inbox tab...")
                         inbox_sel = self.config['selectors'].get('inbox_tab', '#inboxicon')
                         clicked = await self.safe_click(inbox_sel)
                         if not clicked:
                             await self.safe_click("li.inbox")
                         await self.page.wait_for_timeout(2000)
                     """

                if badges:
                    self.logger.info(f"Found {len(badges)} unread badges.")
                    badge = badges[0]
                    
                    # Parent clicking is tricky across frames. 
                    # We need the element handle to belong to the execution context.
                    # So we use evaluate on the handle itself.
                    
                    item_class = self.config['selectors'].get('inbox_item', '.list-group-item').replace('.', '')
                    
                    # Logic: Click the badge's parent
                    # This works regardless of which frame the badge is in, because 'badge' handle has the context.
                    try:
                        username = await badge.evaluate(f"el => el.closest('.{item_class}').getAttribute('data-username')")
                    except:
                        username = "Unknown"

                    Dashboard.status(f"Opening chat with {username}...")
                    await badge.evaluate(f"el => el.closest('.{item_class}').click()")
                    
                    await self.page.wait_for_timeout(2000) 
                    
                    # 3. Send Message
                    test_message = "Hello"
                    await self.send_message(test_message)
                    
                    # 4. Return to Inbox
                    back_btn = self.config['selectors']['back_to_inbox_btn']
                    await self.safe_click(back_btn)
                    await self.page.wait_for_timeout(2000) 

                # SAFETY CHECK
                allowed_domain = self.config['bot'].get('allowed_domain', 'chatib.us')
                if allowed_domain not in self.page.url:
                     # This might be tricky with iframes, main url should be correct though
                    pass
                else:
                    # No unread messages, wait a bit
                    pass

                # SAFETY CHECK: Ensure we are still on target domain
                if allowed_domain not in self.page.url:
                    self.logger.warning(f"Bot drifted to unknown URL: {self.page.url}. Forcing return...")
                    await self.page.goto(self.config['selectors']['chat_url'])

                await asyncio.sleep(3) # Poll interval

            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    async def read_messages(self):
        """Scrapes messages from the DOM."""
        # This is highly dependent on valid selectors
        bubble_sel = self.config['selectors']['incoming_message_bubble']
        
        try:
            # This is a simplification. Real implementation needs robust DOM traversing
            elements = await self.page.query_selector_all(bubble_sel)
            messages = []
            for i, el in enumerate(elements):
                text = await el.inner_text()
                # Dummy ID generation for now. Real implementations should use data-id or similar
                msg_id = f"{len(elements)-i}-{text[:10]}" 
                messages.append({'id': msg_id, 'sender': 'unknown', 'text': text})
            return messages
        except Exception:
            return []

    async def send_message(self, text):
        input_sel = self.config['selectors']['message_input']
        send_sel = self.config['selectors']['send_btn']
        
        try:
            # Check if input is visible. If not, try contenteditable div
            if not await self.page.is_visible(input_sel):
                # Fallback to the contenteditable div seen in HTML
                # <div contenteditable="true" class="contentDiv" id="contenteditablediv" placeholder="Type a message"></div>
                fallback_sel = "#contenteditablediv"
                if await self.page.is_visible(fallback_sel):
                    input_sel = fallback_sel
            
            # Type message carefully
            # 1. Click to focus
            await self.safe_click(input_sel)
            await self.page.wait_for_timeout(500)
            
            # 2. Type characters (React often needs real events)
            await self.page.keyboard.type(text, delay=100)
            await self.page.wait_for_timeout(500)
            
            # 3. Press Enter (Primary send method)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(500)

            # 4. Click Send Button (Backup)
            # Only if text still seems to be in the input? 
            # For now, safe to click it anyway usually.
            await self.safe_click(send_sel)
            
            self.logger.info(f"Bot sent: {text}")
            from .utils import Dashboard
            Dashboard.outgoing(text)
            
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            # Try FORCE click on send just in case
            try:
                await self.page.click(send_sel, force=True)
            except:
                pass

    async def close_ads(self):
        """Attempts to close overlays/ads."""
        try:
            # 1. Try generic "Escape" press
            await self.page.keyboard.press("Escape")
            
            # 2. Frame-aware Dismiss Button Search
            # Google Vignettes are often in iframes.
            dismiss_sel = self.config['selectors'].get('ad_dismiss_btn', '#dismiss-button')
            
            # Check main page
            if await self.safe_click(dismiss_sel):
                self.logger.info("Clicked ad dismiss button (Main Page).")
                return

            # Check all frames (Google Vignettes are usually in 'aswift' or 'google_ads' frames)
            for frame in self.page.frames:
                try:
                    if await frame.is_visible(dismiss_sel):
                        await frame.click(dismiss_sel)
                        self.logger.info(f"Clicked ad dismiss button in frame: {frame.url}")
                        return
                    # Sometimes it's a div with ID dismiss-button inside the frame
                    if await frame.evaluate(f"document.querySelector('{dismiss_sel}') !== null"):
                         await frame.evaluate(f"document.querySelector('{dismiss_sel}').click()")
                         self.logger.info(f"JS Clicked ad dismiss button in frame: {frame.url}")
                         return
                except: pass

            # 3. NUKE ADS FROM ORBIT
            await self.page.evaluate("""
                () => {
                    const selectors = [
                        'iframe[id^="google_ads_iframe"]', 
                        '#google_vignette', 
                        '.adsbygoogle',
                        'ins.adsbygoogle',
                        'div[id^="ad-"]',
                        'div[class*="ad-"]'
                    ];
                    selectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => el.remove());
                    });
                }
            """)
        except Exception:
            pass # Silent fail

    async def _check_exists(self, selector):
        """Helper to check if selector exists in main page or any frame."""
        try:
            if await self.page.is_visible(selector): return True
        except: pass
        for frame in self.page.frames:
            try:
                if await frame.is_visible(selector): return True
            except: continue
        return False

    async def safe_type(self, selector, text, delay=100):
        """Types text into a selector, checking main page AND all iframes."""
        # Helper to verify
        async def verify_fill(ctx, sel, expected):
            try:
                val = await ctx.input_value(sel)
                return expected in val
            except: return False

        # 1. Try Main Page
        try:
             await self.page.click(selector, timeout=2000)
             await self.page.keyboard.type(text, delay=delay)
             if await verify_fill(self.page, selector, text): return True
        except:
             # Fallback: force
             try:
                 await self.page.click(selector, force=True)
                 await self.page.keyboard.type(text, delay=delay)
                 if await verify_fill(self.page, selector, text): return True
             except: pass

        # 2. Try Frames
        for frame in self.page.frames:
            try:
                if await frame.evaluate(f"sel => !!document.querySelector('{{selector}}')", selector):
                     await frame.click(selector, timeout=1000)
                     await frame.type(selector, text, delay=delay)
                     if await verify_fill(frame, selector, text): 
                         self.logger.info(f"Filled {selector} in frame.")
                         return True
            except: continue
        
        return False

    async def safe_select(self, selector, label):
        """Selects an option in a dropdown."""
        # 1. Main
        try:
            await self.page.select_option(selector, label=label, timeout=2000)
            await self.page.dispatch_event(selector, 'change')
            return True # Selection usually reliable if no error
        except: pass
        
        # 2. Frames
        for frame in self.page.frames:
            try:
                await frame.select_option(selector, label=label, timeout=1000)
                await frame.dispatch_event(selector, 'change')
                return True
            except: continue
        return False

    async def safe_check(self, selector):
        """Checks a radio/checkbox, checking main page AND all iframes."""
        try:
            await self.page.check(selector, timeout=2000)
            return True
        except Exception:
            # Force check
            try:
                await self.page.check(selector, force=True, timeout=1000)
                return True
            except: pass
        
        for frame in self.page.frames:
            try:
                await frame.check(selector, timeout=1000)
                return True
            except: continue
        return False

    async def safe_click(self, selector):
        """Attempts to click a selector, checking main page AND all iframes."""
        # 1. Try Main Page
        try:
            await self.page.click(selector, timeout=2000)
            return True
        except: pass
            
        # 2. Try All Frames
        for frame in self.page.frames:
            try:
                 # Check if element exists in frame first to avoid overhead
                if await frame.evaluate(f"sel => !!document.querySelector('{selector}')", selector):
                    await frame.click(selector, timeout=2000)
                    self.logger.info(f"Clicked {selector} in frame: {frame.name or frame.url}")
                    return True
            except:
                continue

        # 3. Try Force Click Main Page (The "Punch Through" Method)
        try:
            self.logger.warning(f"Normal click failed for {selector}. Attempting FORCE click...")
            # Reduced timeout for force click so we don't hang for 30s
            await self.page.click(selector, force=True, timeout=5000)
            return True
        except Exception as e:
            self.logger.warning(f"Force click failed: {e}")
            
        self.logger.warning(f"Could not find element to click: {selector}")
        return False
        """Attempts to click a selector, checking main page AND all iframes."""
        # 1. Try Main Page
        try:
            if await self.page.is_visible(selector):
                await self.page.click(selector, timeout=2000)
                return True
        except: pass
            
        # 2. Try All Frames
        for frame in self.page.frames:
            try:
                 # Check if element exists in frame first to avoid overhead
                if await frame.evaluate(f"sel => !!document.querySelector('{selector}')", selector):
                    await frame.click(selector, timeout=2000)
                    self.logger.info(f"Clicked {selector} in frame: {frame.name or frame.url}")
                    return True
            except:
                continue

        # 3. Try Force Click Main Page (The "Punch Through" Method)
        try:
            self.logger.warning(f"Normal click failed for {selector}. Attempting FORCE click...")
            # Reduced timeout for force click so we don't hang for 30s
            await self.page.click(selector, force=True, timeout=5000)
            return True
        except Exception as e:
            self.logger.warning(f"Force click failed: {e}")
            
        self.logger.warning(f"Could not find element to click: {selector}")
        return False

        if self.playwright:
            await self.playwright.stop()

    async def _check_text_exists(self, text):
        """Helper to check if element with text exists."""
        try:
             # Case insensitive contains check
             if await self.page.is_visible(f"text={text}"): return True
        except: pass
        return False
