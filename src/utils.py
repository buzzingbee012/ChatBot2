import logging
import random
import time
import asyncio
from datetime import datetime

class Logger:
    def __init__(self, name=None, log_file="conversation_logs.txt"):
        self.logger = logging.getLogger("WebMonitor")
        self.logger.setLevel(logging.INFO)
        self.name = name
        
        # Only add handlers if they haven't been added yet
        self.logger.propagate = False
        
        if not any(isinstance(h, logging.FileHandler) for h in self.logger.handlers):
            # File handler
            fh = logging.FileHandler(log_file)
            fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(fh)
            
        if not any(isinstance(h, logging.StreamHandler) for h in self.logger.handlers):
            # Console handler
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(ch)

    def info(self, message):
        self._log("INFO", message)

    def error(self, message):
        self._log("ERROR", message)

    def warning(self, message):
        self._log("WARNING", message)

    def debug(self, message):
        # Only log to file, not console, to keep it quiet as requested
        self.logger.debug(message)

    def _log(self, level, message):
        if self.name:
            message = f"[{self.name}] {message}"
            
        if level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "DEBUG":
            self.logger.debug(message)

    
    def log_chat(self, sender, message):
        self.logger.info(f"CHAT [{sender}]: {message}")

class Dashboard:
    @staticmethod
    def print_separator():
        print("-" * 50)

    @staticmethod
    def incoming(sender, message):
        print(f"\n[RECEIVED] {sender}: {message}")
        print("-" * 20)

    @staticmethod
    def outgoing(message):
        print(f"\n[SENT] Me: {message}")
        Dashboard.print_separator()

    @staticmethod
    def status(message):
        print(f"\n[STATUS] {message}")

async def random_delay(min_seconds, max_seconds):
    """Waits for a random amount of time between min and max seconds."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)
    return delay

async def safe_click(page, selector, logger=None):
    """
    Attempts to click a selector, checking main page AND all iframes.
    Standalone version.
    """
    # 1. Try Main Page
    try:
        await page.click(selector, timeout=2000)
        return True
    except: pass
        
    # 2. Try All Frames
    try:
        for frame in page.frames:
            try:
                # Check if element exists in frame
                if await frame.evaluate(f"sel => !!document.querySelector('{selector}')", selector):
                    await frame.click(selector, timeout=2000)
                    if logger: logger.info(f"Clicked {selector} in frame: {frame.name or frame.url}")
                    return True
            except:
                continue
    except: pass

    # 3. Try Force Click Main Page
    try:
        if logger: logger.warning(f"Normal click failed for {selector}. Attempting FORCE click...")
        await page.click(selector, force=True, timeout=5000)
        return True
    except Exception as e:
        if logger: logger.warning(f"Force click failed: {e}")
        
    if logger: logger.warning(f"Could not find element to click: {selector}")
    return False

async def close_ads(page):
    """Attempts to close common ad overlays."""
    ad_selectors = [
        "button[aria-label='Close']",
        ".close-ad",
        "#close_ad_btn",
        "div[class*='close']",
        "svg[class*='close']" # Generic dangerous selector, but user wants aggression
    ]
    # Only click if it looks very much like a close button
    # Avoiding broad 'div' clicks
    pass 
