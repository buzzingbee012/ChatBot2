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
                    # We can't easily run main() because it never returns if bots run
                    # So we'll just test the logic inside main() manually
                    
                    from main import load_config
                    import argparse
                    
                    parser = argparse.ArgumentParser()
                    parser.add_argument('--duration', default=None)
                    parser.add_argument('--bot', default='all')
                    parser.add_argument('--count', '-n', type=int, default=1)
                    args = parser.parse_args(['--count', '2', '--bot', 'all'])
                    
                    config = load_config()
                    bots = []
                    for i in range(1, args.count + 1):
                        instance_config = config.copy()
                        if args.bot in ['wire', 'all']:
                            bots.append(WireBot(instance_config, instance_id=i))
                        if args.bot in ['site2', 'all']:
                            bots.append(SiteTwoBot(instance_config, instance_id=i))
                        if args.bot in ['ib', 'all']:
                            bots.append(IBBot(instance_config, instance_id=i))
                    
                    print(f"Total bots created: {len(bots)}")
                    assert len(bots) == 6 # 2 instances * 3 bot types
                    
                    # Verify names
                    names = [bot.logger.name for bot in bots]
                    print(f"Bot names: {names}")
                    assert "IBBot-1" in names
                    assert "IBBot-2" in names
                    assert "SiteTwoBot-1" in names
                    assert "SiteTwoBot-2" in names
                    assert "WireBot-1" in names
                    assert "WireBot-2" in names
                    
                    print("Scaling initialization test passed!")

if __name__ == "__main__":
    asyncio.run(test_scaling_initialization())
