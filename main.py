import asyncio
import sys
import yaml
import logging
# from src.bot_core import ChatBot
from src.site_two import SiteTwoBot as ChatBot

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
                # Simple merge: update llm.api_key if present
                if secrets and 'llm' in secrets:
                    if 'llm' not in config: config['llm'] = {}
                    config['llm'].update(secrets['llm'])
                    print("Loaded secrets from config.secrets.yaml")
        
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)

import argparse

async def main():
    parser = argparse.ArgumentParser(description='Run the Chat Bot.')
    parser.add_argument('--duration', type=int, help='Duration in seconds to run the bot', default=None)
    args = parser.parse_args()

    config = load_config()
    bot = ChatBot(config)
    
    try:
        # SiteTwoBot.start() handles the full loop internally
        await bot.start(duration=args.duration)
            
    except KeyboardInterrupt:
        print("Stopping bot...")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
