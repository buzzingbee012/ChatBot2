import os
import yaml
from dotenv import load_dotenv
from src.ai_handler import AIHandler

def test_llama_config():
    # Load .env
    load_dotenv()
    
    # Load config
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    print(f"Provider: {config.get('llm', {}).get('provider')}")
    print(f"Model: {config.get('llm', {}).get('model')}")
    print(f"Base URL: {config.get('llm', {}).get('base_url')}")
    
    # Initialize Handler
    handler = AIHandler(config)
    
    # Check if API Key was picked up
    if handler.api_key:
        masked = handler.api_key[:5] + "..." + handler.api_key[-5:]
        print(f"API Key found and loaded: {masked}")
    else:
        print("ERROR: API Key NOT found!")

    # Check model name
    print(f"Handler Model: {handler.model}")
    
    if handler.api_key and handler.provider == 'openai' and 'llama' in handler.model.lower():
        print("\nSUCCESS: Llama/Groq configuration verified!")
    else:
        print("\nFAILURE: Configuration mismatch.")

if __name__ == "__main__":
    test_llama_config()
