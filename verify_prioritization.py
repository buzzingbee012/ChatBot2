import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

class MockBot:
    def __init__(self):
        self.user_reply_counts = {
            "NewUser": 0,
            "ActiveUser1": 5,
            "ActiveUser2": 10,
            "AlmostDoneUser": 14
        }
    
    async def get_unread_chats(self):
        # Unordered unreads
        return [
            {'name': 'NewUser'},
            {'name': 'ActiveUser1'},
            {'name': 'ActiveUser2'},
            {'name': 'AlmostDoneUser'}
        ]

    async def verify_sort(self):
        unreads = await self.get_unread_chats()
        print("Before sort:", [u['name'] for u in unreads])
        
        # Logic from base_bot.py
        unreads.sort(key=lambda x: self.user_reply_counts.get(x['name'], 0), reverse=True)
        
        print("After sort (Prioritized):", [u['name'] for u in unreads])
        
        expected = ["AlmostDoneUser", "ActiveUser2", "ActiveUser1", "NewUser"]
        actual = [u['name'] for u in unreads]
        
        if actual == expected:
            print("SUCCESS: Prioritization logic is correct.")
        else:
            print(f"FAILURE: Expected {expected}, got {actual}")

if __name__ == "__main__":
    bot = MockBot()
    asyncio.run(bot.verify_sort())
