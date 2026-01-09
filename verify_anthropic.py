import yaml
from src.ai_handler import AIHandler

# Load Config
try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    print("Config Loaded Successfully.")
    print(f"Username from config: {config['guest_profile']['username']}")
except Exception as e:
    print(f"Failed to load config: {e}")
    exit(1)

# Test AI Handler
try:
    print("\nTesting AI Handler (Anthropic)...")
    handler = AIHandler(config)
    
    # Mock History
    test_history = [
        {"role": "user", "content": "Hello, how are you?"}
    ]
    
    print(f"Using Provider: {handler.provider}")
    print(f"Using Model: {handler.model}")
    print(f"Using API Key: '{handler.api_key}'") # Debug print
    
    response = handler.generate_response(test_history)
    
    if response:
        print("\nSUCCESS! Received Response:")
        print(response)
    else:
        print("\nFAILURE: No response received (Check logs or API Key).")

except Exception as e:
    print(f"\nCRITICAL ERROR: {e}")
