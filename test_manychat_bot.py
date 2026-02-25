import asyncio
import yaml
import unittest
from unittest.mock import MagicMock, patch
from src.manychat_bot import ManyChatBot

class TestManyChatBot(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = {
            'manychat': {
                'api_token': 'test_token',
                'prompt': 'You are Jasmin.'
            },
            'llm': {
                'provider': 'openai', # Use a provider that's easier to mock
                'api_key': 'test_key'
            }
        }
        # Path AIHandler to avoid actual API calls
        with patch('src.ai_handler.AIHandler.__init__', return_value=None):
            with patch('src.manychat_handler.ManyChatHandler.__init__', return_value=None):
                self.bot = ManyChatBot(self.config)
                self.bot.ai_handler = MagicMock()
                self.bot.mc_handler = MagicMock()

    async def test_handle_message_success(self):
        # Setup
        subscriber_id = "123"
        message = "Hello"
        history = [{"role": "user", "content": "Hello"}]
        self.bot.ai_handler.generate_response.return_value = "Hi there!"
        self.bot.mc_handler.send_message.return_value = {"status": "success"}

        # Execute
        result = await self.bot.handle_message(subscriber_id, current_message=message, history=history)

        # Verify
        self.assertTrue(result)
        self.bot.ai_handler.generate_response.assert_called_with(history)
        self.bot.mc_handler.send_message.assert_called_with(subscriber_id, "Hi there!")

    async def test_handle_message_duplicate(self):
        # Setup
        subscriber_id = "123"
        message = "Hello"
        history = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]
        # In actual AIHandler, this would return something else or None if it repeats.
        # Here we mock it returning a duplicate, and we see if our bot handles it (though AIHandler should prevent it).
        self.bot.ai_handler.generate_response.return_value = "Hi there!" 
        # Note: ManyChatBot doesn't have an extra duplicate check because it relies on AIHandler.
        # But let's verify it calls the handler.
        
        self.bot.mc_handler.send_message.return_value = {"status": "success"}

        # Execute
        result = await self.bot.handle_message(subscriber_id, current_message=message, history=history)

        # Verify
        self.assertTrue(result)
        self.bot.mc_handler.send_message.assert_called_with(subscriber_id, "Hi there!")

    async def test_handle_message_error_response(self):
        # Setup
        subscriber_id = "123"
        self.bot.ai_handler.generate_response.return_value = "Error: something went wrong"

        # Execute
        result = await self.bot.handle_message(subscriber_id, current_message="Hi")

        # Verify
        self.assertFalse(result)
        self.bot.mc_handler.send_message.assert_not_called()

if __name__ == '__main__':
    unittest.main()
