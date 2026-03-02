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
    bots = []
    
    # Determine counts
    ib_count = args.ib_count if args.ib_count is not None else (args.count if args.count is not None else (1 if args.bot in ['ib', 'all'] else 0))
    s2_count = args.site2_count if args.site2_count is not None else (args.count if args.count is not None else (1 if args.bot in ['site2', 'all'] else 0))
    wire_count = args.wire_count if args.wire_count is not None else (args.count if args.count is not None else (1 if args.bot in ['wire', 'all'] else 0))

    if args.bot != 'all':
        if args.bot != 'ib': ib_count = 0
        if args.bot != 'site2': s2_count = 0
        if args.bot != 'wire': wire_count = 0

    # Initialize IBBots
    for i in range(1, ib_count + 1):
        bots.append(IBBot(config.copy(), instance_id=i))
        
    # Initialize SiteTwoBots
    for i in range(1, s2_count + 1):
        bots.append(SiteTwoBot(config.copy(), instance_id=i))
        
    # Initialize WireBots
    for i in range(1, wire_count + 1):
        bots.append(WireBot(config.copy(), instance_id=i))
    
    if not bots:
        print("No bots selected to run.")
        return

    try:
        # Run all selected bots in parallel, but stagger their start to avoid name collisions
        # and simultaneous login attempts which can be flagged
        async def start_staggered(bot, delay):
            await asyncio.sleep(delay)
            return await bot.start(duration=args.duration)

        tasks = []
        for idx, bot in enumerate(bots):
            # 5 second staggered start
            tasks.append(start_staggered(bot, idx * 5))
            
        await asyncio.gather(*tasks)
            
    except KeyboardInterrupt:
        print("Stopping bots...")
    finally:
        for bot in bots:
            await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
