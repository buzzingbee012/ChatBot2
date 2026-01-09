from google import genai
from pydantic import BaseModel
import os

class ChatResponse(BaseModel):
    message: str

api_key = "AIzaSyBiiYxFVJyCYojRo7lhRACChv8j2ml5fGg"
client = genai.Client(api_key=api_key)

conversation = "You are a helpful assistant.\n\nUser: Hello\nAssistant:"

try:
    response = client.models.generate_content(
        model="gemini-2.0-flash-lite",
        contents=conversation,
        config=genai.types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema=ChatResponse
        )
    )
    
    print("Response object type:", type(response))
    print("\nResponse attributes:", dir(response))
    print("\nResponse text:", response.text)
    
    # Try different ways to access token usage
    print("\n--- Checking for token metadata ---")
    if hasattr(response, 'usage_metadata'):
        print("Has usage_metadata:", response.usage_metadata)
    if hasattr(response, 'metadata'):
        print("Has metadata:", response.metadata)
    if hasattr(response, 'usage'):
        print("Has usage:", response.usage)
    
    # Print full response structure
    print("\n--- Full response ---")
    print(response)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
