import asyncio
import sys
import yaml
import logging
# from src.bot_core import ChatBot
from src.site_two import SiteTwoBot
from src.wirebot import WireBot
from src.ib_bot import IBBot
from src.ai_handler import AIHandler
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def load_config(path="config.yaml"):
    try:
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Try to load secrets file for local dev override
        secrets_path = "config.secrets.yaml"
        import os
        if os.path.exists(secrets_path):
            with open(secrets_path, 'r') as sf:
                secrets = yaml.safe_load(sf)
                # Simple merge: update llm and wireclub if present
                for key in ['llm', 'wireclub', 'site_two', 'ai', 'firebase']:
                    if secrets and key in secrets:
                        if key not in config: config[key] = {}
                        config[key].update(secrets[key])

        # Environment Variable Override (for GitHub Secrets / CI)
        # Prioritized over files
        env_map = {
            'GROQ_API_KEY': ('ai', 'api_key'),
            'WIRECLUB_EMAIL': ('wireclub', 'email'),
            'WIRECLUB_PASSWORD': ('wireclub', 'password'),
            'WIRECLUB_USERNAME': ('wireclub', 'username'),
            'SITE_TWO_USERNAME': ('site_two', 'username'),
            'FIREBASE_CREDENTIALS': ('firebase', 'cred_path') # Could be path or raw json, but usually path
        }
        
        for env_var, (section, key) in env_map.items():
            val = os.getenv(env_var)
            if val:
                if section not in config: config[section] = {}
                config[section][key] = val
                print(f"Config: Loaded {env_var} from environment.")
        
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

import argparse

class BotManager:
    def __init__(self, config):
        self.config = config
        self.bots = []
        self._stop_event = asyncio.Event()
        self.running_task = None

    async def initialize_bots(self, bot_type='all', count=None, ib_count=None, s2_count=None, wire_count=None):
        self.bots = []
        
        # Determine counts
        final_ib_count = ib_count if ib_count is not None else (count if count is not None else (1 if bot_type in ['ib', 'all'] else 0))
        final_s2_count = s2_count if s2_count is not None else (count if count is not None else (1 if bot_type in ['site2', 'all'] else 0))
        final_wire_count = wire_count if wire_count is not None else (count if count is not None else (1 if bot_type in ['wire', 'all'] else 0))

        if bot_type != 'all':
            if bot_type != 'ib': final_ib_count = 0
            if bot_type != 'site2': final_s2_count = 0
            if bot_type != 'wire': final_wire_count = 0

        # Initialize IBBots
        for i in range(1, final_ib_count + 1):
            self.bots.append(IBBot(self.config.copy(), instance_id=i))
            
        # Initialize SiteTwoBots
        for i in range(1, final_s2_count + 1):
            self.bots.append(SiteTwoBot(self.config.copy(), instance_id=i))
            
        # Initialize WireBots
        for i in range(1, final_wire_count + 1):
            self.bots.append(WireBot(self.config.copy(), instance_id=i))
            
        return len(self.bots)

    async def start(self, duration=None):
        if not self.bots:
            print("No bots initialized.")
            return

        self._stop_event.clear()
        
        async def start_staggered(bot, delay):
            try:
                await asyncio.sleep(delay)
                if self._stop_event.is_set():
                    return
                await bot.start(duration=duration)
            except Exception as e:
                print(f"Error in bot {bot}: {e}")

        tasks = []
        for idx, bot in enumerate(self.bots):
            tasks.append(asyncio.create_task(start_staggered(bot, idx * 5)))
            
        self.running_task = asyncio.gather(*tasks)
        try:
            await self.running_task
        except asyncio.CancelledError:
            print("Bot manager task cancelled.")
        finally:
            await self.stop()

    async def stop(self):
        self._stop_event.set()
        if self.running_task and not self.running_task.done():
            self.running_task.cancel()
        
        stop_tasks = []
        for bot in self.bots:
            stop_tasks.append(bot.stop())
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        self.bots = []

async def main():
    parser = argparse.ArgumentParser(description='Run the Chat Bot.')
    parser.add_argument('--duration', type=int, help='Duration in seconds to run the bot', default=None)
    parser.add_argument('--bot', type=str, help='Run specific bot: wire, site2, ib, or all', default='all')
    parser.add_argument('--count', '-n', type=int, help='Global Number of instances per bot type (default 1)', default=None)
    parser.add_argument('--ib-count', type=int, help='Specific count for IBBot', default=None)
    parser.add_argument('--site2-count', type=int, help='Specific count for SiteTwoBot', default=None)
    parser.add_argument('--wire-count', type=int, help='Specific count for WireBot', default=None)
    args = parser.parse_args()

    config = load_config()
    manager = BotManager(config)
    
    bot_count = await manager.initialize_bots(
        bot_type=args.bot,
        count=args.count,
        ib_count=args.ib_count,
        s2_count=args.site2_count,
        wire_count=args.wire_count
    )

    if bot_count == 0:
        print("No bots selected to run.")
        return

    try:
        await manager.start(duration=args.duration)
    except KeyboardInterrupt:
        print("Stopping bots...")
        await manager.stop()

if __name__ == "__main__":
    asyncio.run(main())

