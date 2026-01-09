import yaml
import os

try:
    print("Loading config.yaml...")
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    print("Config Structure for 'llm':")
    print(config.get('llm', 'Key not found'))
    
    model = config.get('llm', {}).get('model', 'DEFAULT_FALLBACK')
    print(f"Resolved Model: {model}")
    
    provider = config.get('llm', {}).get('provider', 'DEFAULT_FALLBACK')
    print(f"Resolved Provider: {provider}")

except Exception as e:
    print(f"Error: {e}")
