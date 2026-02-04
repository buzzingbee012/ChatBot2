import asyncio
import yaml
import logging
from src.ib_bot import IBBot

async def verify():
    # Load Config properly
    from main import load_config
    config = load_config()
    
    # Override headless for visual verification
    config['bot']['headless'] = False 
    
    # Ensure IBBot config exists (fallback if needed)
    if 'ib_bot' not in config:
         config['ib_bot'] = {} 
    
    bot = IBBot(config)
    
    try:
        print("Starting IBBot verification (running for 120 seconds)...")
        await bot.start(duration=120)
        
    except KeyboardInterrupt:
        pass
    finally:
        # Check for screenshots
        import os
        if os.path.exists("ib_entry_error.png"):
            print("Found error screenshot: ib_entry_error.png")

if __name__ == "__main__":
    asyncio.run(verify())
