
import os
import sys
import logging
from src.ai_handler import AIHandler

# Set dummy API keys for testing
os.environ["GOOGLE_API_KEY"] = "test_google_key"
os.environ["OPENAI_API_KEY"] = "test_openai_key"

logging.basicConfig(level=logging.INFO)

def test_initialization():
    print("Testing Gemini initialization...")
    config_google = {
        'llm': {
            'provider': 'google',
            'model': 'gemini-1.5-flash'
        }
    }
    handler = AIHandler(config_google)
    print(f"Provider: {handler.provider}")
    print(f"Model: {handler.model}")
    print(f"Client Type: {type(handler.client)}")
    
    if handler.provider == 'google' and "genai.client.Client" in str(type(handler.client)):
        print("SUCCESS: Gemini client initialized correctly.")
    else:
        print("FAIL: Gemini client initialization failed.")

    print("\nTesting OpenAI initialization...")
    config_openai = {
        'llm': {
            'provider': 'openai',
            'model': 'gpt-4o'
        }
    }
    handler_oa = AIHandler(config_openai)
    print(f"Provider: {handler_oa.provider}")
    print(f"Model: {handler_oa.model}")
    print(f"Client Type: {type(handler_oa.client)}")
    
    if handler_oa.provider == 'openai' and "openai.OpenAI" in str(type(handler_oa.client)):
        print("SUCCESS: OpenAI client initialized correctly.")
    else:
        print("FAIL: OpenAI client initialization failed.")

if __name__ == "__main__":
    test_initialization()
