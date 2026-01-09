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
        print("Starting Bot verification...")
        await bot.start()
        # The start method calls guest_entry internally
        # If it returns, it means entry was successful and it started monitoring (or failed)
        # But wait, start() runs monitor_loop forever if successful.
        # So we should modify how we call it or just run guest_entry directly if possible, 
        # but guest_entry needs setup (browser launch).
        # SiteTwoBot.start() launches browser.
        
        # Let's run it for a bit then stop
        await asyncio.sleep(60) 
        
    except KeyboardInterrupt:
        pass
    finally:
        await bot.stop()
        print("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(verify())
