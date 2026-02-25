import asyncio
import os
import sys
import yaml
import json
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

with patch('src.ai_handler.AIHandler'):
    from src.manychat_bot import ManyChatBot
    from src.base_bot import BaseBot

class MockAI:
    def generate_response(self, history):
        return "Normal chat message"

async def test_base_bot_logic():
    print("Testing BaseBot Link Logic...")
    config = {
        'bot': {
            'link_config': {
                'min_replies_before_link': 2,
                'max_replies_before_link': 5,
                'force_link_probability': 1.0  # Force it always for test
            }
        },
        'instagram_link': "https://test.insta/link"
    }
    
    # Mock BaseBot
    class TestBot(BaseBot):
        def __init__(self, config):
            self.config = config
            self.logger = MagicMock()
            self.ai_handler = MockAI()
        
        async def entry_point(self): return True
        async def handle_ads_and_popups(self): pass
        async def perform_broadcast(self): pass
        async def get_unread_chats(self): return []
        async def open_chat(self, obj): return True
        async def wait_for_chat_load(self, n): return True
        async def get_chat_history(self): return []
        async def send_message(self, t): return True
        async def return_to_lobby(self): pass

    bot = TestBot(config)
    bot.ai_handler = MockAI()
    
    # Test case 1: Below min messages
    res1 = await bot._generate_reply("User1", [], 1)
    print(f"Reply at 1 msg: {res1}")
    assert "instagram" not in res1.lower()
    
    # Test case 2: At min messages (forced by 1.0 prob)
    res2 = await bot._generate_reply("User1", [], 2)
    print(f"Reply at 2 msgs: {res2}")
    assert "instagram" in res2.lower()
    
    # Test case 3: At max messages
    res3 = await bot._generate_reply("User1", [], 5)
    print(f"Reply at 5 msgs: {res3}")
    assert "instagram" in res3.lower()
    
    print("BaseBot logic test passed!")

async def test_manychat_bot_logic():
    print("\nTesting ManyChatBot Persistent Logic...")
    stats_file = "subscriber_stats.json"
    if os.path.exists(stats_file): os.remove(stats_file)
    
    config = {
        'bot': {
            'link_config': {
                'min_replies_before_link': 2,
                'max_replies_before_link': 5,
                'force_link_probability': 1.0
            }
        },
        'manychat': {'api_token': 'test', 'prompt': 'test'},
        'instagram_link': "https://test.insta/link"
    }
    
    bot = ManyChatBot(config)
    bot.ai_handler = MockAI()
    bot.mc_handler = MagicMock()
    bot.mc_handler.send_message.return_value = True
    
    # Initial message (count 0 -> 1)
    await bot.handle_message("SUB123", "hi")
    print(f"Count after 1 msg: {bot.subscriber_counts['SUB123']}")
    assert bot.subscriber_counts['SUB123'] == 1
    
    # Second message (count 1 -> 2)
    # At start of this call, count is 1. min_replies is 2. 
    # So it won't force link yet.
    await bot.handle_message("SUB123", "hi")
    print(f"Count after 2 msgs: {bot.subscriber_counts['SUB123']}")
    assert bot.subscriber_counts['SUB123'] == 2

    # Third message (count 2 -> 3)
    # At start of this call, count is 2. min_replies is 2.
    # Should force link now.
    await bot.handle_message("SUB123", "hi")
    last_call = bot.mc_handler.send_message.call_args[0][1]
    print(f"Reply at 3 msgs: {last_call}")
    assert "instagram" in last_call.lower()
    assert bot.subscriber_counts['SUB123'] == 3
    
    # Verify persistence
    bot2 = ManyChatBot(config)
    print(f"Restored count: {bot2.subscriber_counts['SUB123']}")
    assert bot2.subscriber_counts['SUB123'] == 3
    
    if os.path.exists(stats_file): os.remove(stats_file)
    print("ManyChatBot logic test passed!")

if __name__ == "__main__":
    asyncio.run(test_base_bot_logic())
    asyncio.run(test_manychat_bot_logic())
