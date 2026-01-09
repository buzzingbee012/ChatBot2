from src.ai_handler import AIHandler
import yaml
import os

try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    # Mock Config for Gemini Test if not already set
    if config['llm']['provider'] != 'gemini':
        print("Switching provider to Gemini for test...")
        config['llm']['provider'] = 'gemini'
        # Check for env var if not in config
        if not config['llm'].get('api_key') or config['llm']['api_key'] == "YOUR_GEMINI_API_KEY":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                print("WARNING: No GEMINI_API_KEY found in config or env. Test might fail.")
                # We can't really proceed without a key, so let's warn.
            else:
                 config['llm']['api_key'] = api_key
    
    ai = AIHandler(config)
    print(f"Provider: {ai.provider}")
    print(f"Model: {ai.model}")
    
    print("Generating response...")
    # Mock history
    history = [{"role": "user", "content": "Hello, are you google gemini?"}]
    response = ai.generate_response(history)
    print(f"Response: {response}")

except Exception as e:
    print(f"Verification Failed: {e}")
