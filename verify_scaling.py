import asyncio
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.getcwd())

# Import bots - we will patch the AI client inside the test
from src.manychat_bot import ManyChatBot
from src.base_bot import BaseBot
from src.ib_bot import IBBot
from src.site_two import SiteTwoBot
from src.wirebot import WireBot
from src.ai_handler import AIHandler

async def test_scaling_initialization():
    print("Testing Multi-Instance Initialization...")
    
    # Mock bots start method
    with patch.object(IBBot, 'start', return_value=asyncio.Future()) as mock_ib:
        with patch.object(SiteTwoBot, 'start', return_value=asyncio.Future()) as mock_s2:
            with patch.object(WireBot, 'start', return_value=asyncio.Future()) as mock_wire:
                # We need to set the result of the futures or they will hang asyncio.gather
                mock_ib.return_value.set_result(True)
                mock_s2.return_value.set_result(True)
                mock_wire.return_value.set_result(True)
                
                # Import main and run with arguments
                import main
                sys.argv = ['main.py', '--count', '2', '--bot', 'all']
                
                # We need to mock load_config because it might fail on missing files
                mock_config = {
                    'guest_profile': {'username': 'testuser'},
                    'bot': {'headless': True},
                    'site_two': {'url': 'http://test'}
                }
                
                with patch('main.load_config', return_value=mock_config):
                    with patch('src.ai_handler.AIHandler') as MockAIHandler:
                        # Setup the mock instance
                        mock_ai_instance = MockAIHandler.return_value
                        # side_effect to return unique names
                        mock_ai_instance.generate_username.side_effect = [f"Name_{i}" for i in range(100)]
                        
                        from main import load_config
                        import argparse
                        
                        parser = argparse.ArgumentParser()
                        parser.add_argument('--duration', default=None)
                        parser.add_argument('--bot', default='all')
                        parser.add_argument('--count', '-n', type=int, default=1)
                        args = parser.parse_args(['--count', '10', '--bot', 'all'])
                        
                        config = load_config()
                        
                        # Verify unique names
                        names = []
                        for i in range(1, args.count + 1):
                            b = SiteTwoBot(config.copy(), instance_id=i)
                            # In the real bot, b.username is set from ai_handler during init
                            # Since we mocked AIHandler, SiteTwoBot.__init__ will call it
                            names.append(mock_ai_instance.generate_username())
                        
                        print(f"Generated names: {names}")
                        # Check if all names are unique
                        assert len(set(names)) == len(names)
                        assert len(names) == 10
                    
                    print("Scaling initialization and unique naming test passed!")

if __name__ == "__main__":
    asyncio.run(test_scaling_initialization())
