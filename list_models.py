import google.generativeai as genai
import yaml
import os

try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    api_key = config.get('llm', {}).get('api_key') or os.getenv("GEMINI_API_KEY")
    
    if not api_key or "YOUR_" in api_key:
        print("Please set a valid API Key in config.yaml or env var.")
        exit(1)
        
    genai.configure(api_key=api_key)
    
    print("Listing available models...")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)

except Exception as e:
    print(f"Error: {e}")
