import asyncio
import yaml
from src.site_two import SiteTwoBot

async def verify():
    # Load Config
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    # Override headless for visual verification if needed
    config['bot']['headless'] = False 
    
    bot = SiteTwoBot(config)
    try:
    try:
        print("Starting Bot verification (running for 60 seconds)...")
        # Run the bot for 60 seconds then it will exit efficiently
        await bot.start(duration=60)
        
    except KeyboardInterrupt:
        pass 
        
    except KeyboardInterrupt:
        pass
    finally:
        await bot.stop()
        print("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(verify())
