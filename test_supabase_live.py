import os
from dotenv import load_dotenv

# Try to load supabase wrapper
try:
    from src.supabase_handler import SupabaseHandler
    SUPABASE_OK = True
except ImportError as e:
    SUPABASE_OK = False
    print(f"Failed to import SupabaseHandler (missing library?): {e}")

load_dotenv()

def test_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    print(f"Configured URL: {bool(url)}")
    print(f"Configured Key: {bool(key)}")
    
    if not url or not key:
        print("Missing keys!")
        return
        
    if not SUPABASE_OK:
        print("Testing via REST instead of SDK due to missing library..")
        import requests
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        # Test stats
        print("Inserting dummy stats data...")
        payload = {"key": "stats", "value": {"2026-04-13": {"interactions": 42, "tokens": 1337, "errors": []}}}
        res = requests.post(f"{url}/rest/v1/app_data", headers=headers, json=payload)
        # Using upsert via POST with on_conflict
        headers_upsert = headers.copy()
        headers_upsert["Prefer"] = "return=representation,resolution=merge-duplicates"
        res = requests.post(f"{url}/rest/v1/app_data?on_conflict=key", headers=headers_upsert, json=payload)
        
        print("Response:", res.status_code, res.text)
        
        # Test inserting chat limits
        print("Inserting dummy exhausted chat...")
        chat_payload = {
            "bot_name": "TestBot",
            "user_name": "TestUser",
            "history": [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "gtg add me on insta"}]
        }
        res_chat = requests.post(f"{url}/rest/v1/exhausted_chats", headers=headers, json=chat_payload)
        print("Chat Response:", res_chat.status_code, res_chat.text)
        
    else:
        print("Supabase library is available! Testing via SDK.")
        config = {'supabase': {'enabled': True}}
        handler = SupabaseHandler(config)
        handler.update_stats({"2026-04-13": {"interactions": 99, "tokens": 5555, "errors": []}})
        handler.save_chat_history("SDK_User", "SDK_Bot", [{"role": "user", "content": "Yo!"}])
        print("Done via SDK.")

if __name__ == "__main__":
    test_supabase()
