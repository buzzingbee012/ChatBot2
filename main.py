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
            'GEMINI_API_KEY': ('ai', 'api_key'),
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
    parser.add_argument('--count', '-n', type=int, help='Number of instances per bot type', default=1)
    args = parser.parse_args()

    config = load_config()
    bots = []
    
    for i in range(1, args.count + 1):
        # Create a specific config for this instance (to allow name overrides if needed)
        instance_config = config.copy()
        
        if args.bot in ['wire', 'all']:
            bots.append(WireBot(instance_config, instance_id=i))
        
        if args.bot in ['site2', 'all']:
            bots.append(SiteTwoBot(instance_config, instance_id=i))
        
        if args.bot in ['ib', 'all']:
            bots.append(IBBot(instance_config, instance_id=i))
    
    if not bots:
        print("No bots selected to run.")
        return

    try:
        # Run all selected bots in parallel
        await asyncio.gather(*(bot.start(duration=args.duration) for bot in bots))
            
    except KeyboardInterrupt:
        print("Stopping bots...")
    finally:
        for bot in bots:
            await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
