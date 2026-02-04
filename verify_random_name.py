import yaml
import os
from src.ai_handler import AIHandler

def main():
    # Load config
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)
    
    # Check for secrets
    if os.path.exists("config.secrets.yaml"):
        with open("config.secrets.yaml", 'r') as sf:
            secrets = yaml.safe_load(sf)
            for key in ['llm', 'ai']:
                if secrets and key in secrets:
                    if key not in config: config[key] = {}
                    config[key].update(secrets[key])

    # Initialize AIHandler
    ai = AIHandler(config)
    
    print("Testing generate_username()...")
    for i in range(3):
        name = ai.generate_username()
        print(f"Generated name {i+1}: {name}")
        
    if name and name.endswith("_32f"):
        print("\nSUCCESS: Username generated correctly with suffix.")
    else:
        print("\nFAILURE: Username generation failed or incorrect format.")

if __name__ == "__main__":
    main()
