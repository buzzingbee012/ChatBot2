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

async def test_granular_scaling():
    print("Testing Granular Bot Scaling (6, 3, 1)...")
    
    # We need to mock load_config because it might fail on missing files
    mock_config = {
        'guest_profile': {'username': 'testuser'},
        'bot': {'headless': True},
        'site_two': {'url': 'http://test'}
    }
    
    with patch('main.load_config', return_value=mock_config):
        import argparse
        import main
        
        parser = argparse.ArgumentParser()
        parser.add_argument('--duration', default=None)
        parser.add_argument('--bot', default='all')
        parser.add_argument('--count', '-n', type=int, default=None)
        parser.add_argument('--ib-count', type=int, default=None)
        parser.add_argument('--site2-count', type=int, default=None)
        parser.add_argument('--wire-count', type=int, default=None)
        
        # SiteTwo=6, IBBot=3, WireBot=1
        args = parser.parse_args(['--site2-count', '6', '--ib-count', '3', '--wire-count', '1'])
        
        config = main.load_config()
        bots = []
        
        ib_count = args.ib_count if args.ib_count is not None else (args.count if args.count is not None else (1 if args.bot in ['ib', 'all'] else 0))
        s2_count = args.site2_count if args.site2_count is not None else (args.count if args.count is not None else (1 if args.bot in ['site2', 'all'] else 0))
        wire_count = args.wire_count if args.wire_count is not None else (args.count if args.count is not None else (1 if args.bot in ['wire', 'all'] else 0))
        
        for i in range(1, ib_count + 1):
            bots.append(IBBot(config.copy(), instance_id=i))
        for i in range(1, s2_count + 1):
            bots.append(SiteTwoBot(config.copy(), instance_id=i))
        for i in range(1, wire_count + 1):
            bots.append(WireBot(config.copy(), instance_id=i))
        
        print(f"Total bots created: {len(bots)}")
        assert len(bots) == 10
        
        ib_bots = [b for b in bots if isinstance(b, IBBot)]
        s2_bots = [b for b in bots if isinstance(b, SiteTwoBot)]
        wire_bots = [b for b in bots if isinstance(b, WireBot)]
        
        print(f"IBBots: {len(ib_bots)}")
        print(f"SiteTwoBots: {len(s2_bots)}")
        print(f"WireBots: {len(wire_bots)}")
        
        assert len(ib_bots) == 3
        assert len(s2_bots) == 6
        assert len(wire_bots) == 1
        
        # Verify naming sequence
        ib_names = [b.logger.name for b in ib_bots]
        print(f"IBBot names: {ib_names}")
        assert "IBBot-1" in ib_names
        assert "IBBot-3" in ib_names
        
        print("Granular scaling test passed!")

if __name__ == "__main__":
    asyncio.run(test_granular_scaling())
