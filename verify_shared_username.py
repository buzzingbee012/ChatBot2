import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.getcwd())

with patch('src.ai_handler.AIHandler'):
    from src.manychat_bot import ManyChatBot
    from src.base_bot import BaseBot
    from src.ib_bot import IBBot
    from src.site_two import SiteTwoBot
    from src.wirebot import WireBot

async def test_shared_username_scaling():
    print("Testing Shared Username Scaling...")
    
    # We need to mock load_config because it might fail on missing files
    mock_config = {
        'guest_profile': {'username': 'testuser'},
        'bot': {'headless': True},
        'site_two': {'url': 'http://test'}
    }
    
    with patch('main.load_config', return_value=mock_config):
        import argparse
        import main
        
        # Mock AIHandler to return a fixed name for testing
        with patch('src.ai_handler.AIHandler') as mock_ai_class:
            mock_ai_instance = mock_ai_class.return_value
            mock_ai_instance.generate_username.return_value = "Jasmin"
            
            # SiteTwo=2, IBBot=2
            args = argparse.Namespace(
                duration=None,
                bot='all',
                count=None,
                ib_count=2,
                site2_count=2,
                wire_count=0
            )
            
            config = main.load_config()
            
            # This simulates the logic in main()
            from src.ai_handler import AIHandler
            ai = AIHandler(config)
            shared_guest_username = ai.generate_username()
            print(f"Shared Username: {shared_guest_username}")
            assert shared_guest_username == "Jasmin"
            
            bots = []
            for i in range(1, args.ib_count + 1):
                bots.append(IBBot(config.copy(), instance_id=i, shared_username=shared_guest_username))
            for i in range(1, args.site2_count + 1):
                bots.append(SiteTwoBot(config.copy(), instance_id=i, shared_username=shared_guest_username))
            
            print(f"Total bots created: {len(bots)}")
            assert len(bots) == 4
            
            # Check IBBots
            for bot in [b for b in bots if isinstance(b, IBBot)]:
                print(f"IBBot {bot.logger.name} shared_username: {bot.shared_username}")
                assert bot.shared_username == "Jasmin"
            
            # Check SiteTwoBots
            for bot in [b for b in bots if isinstance(b, SiteTwoBot)]:
                print(f"SiteTwoBot {bot.logger.name} username: {bot.username}")
                # SiteTwoBot appends _f
                assert bot.username == "Jasmin_f"
            
            print("Shared username scaling test passed!")

if __name__ == "__main__":
    asyncio.run(test_shared_username_scaling())
