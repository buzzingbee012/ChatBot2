import os
import logging
from openai import OpenAI
from anthropic import Anthropic
from google import genai
from pydantic import BaseModel

class ChatResponse(BaseModel):
    """Structured response model for chat completions"""
    message: str

class AIHandler:
    def __init__(self, config):
        self.config = config
        self.provider = config.get('llm', {}).get('provider', 'openai')
        
        # Prioritize Environment Variables
        env_key = os.getenv("GEMINI_API_KEY") if self.provider in ['gemini', 'google'] else \
                  os.getenv("ANTHROPIC_API_KEY") if self.provider == 'anthropic' else \
                  os.getenv("OPENAI_API_KEY")
        
        self.api_key = env_key or config.get('llm', {}).get('api_key')
        
        if not self.api_key:
            logging.warning(f"No API Key found for provider {self.provider}. Please set GEMINI_API_KEY env var.")
        
        self.client = None
        if self.provider == 'anthropic':
            self.client = Anthropic(api_key=self.api_key)
            self.model = config.get('llm', {}).get('model', 'claude-3-haiku-20240307')
        elif self.provider in ['gemini', 'google']:
            self.model = config.get('llm', {}).get('model', 'gemini-2.5-flash-lite')
            print(f"DEBUG: Initialized Gemini with model: {self.model}")
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = OpenAI(api_key=self.api_key)
            self.model = config.get('ai', {}).get('model', 'gpt-4o')
            
        self.system_prompt = config.get('llm', {}).get('system_prompt') or config.get('ai', {}).get('system_prompt', "You represent a user in a chat room.")
        self.last_token_count = 0
        self.last_error = None

    def generate_response(self, chat_history):
        """
        Generates a response based on the chat history.
        chat_history: list of dicts [{'role': 'user', 'content': '...'}, ...]
        """
        if not self.client:
            logging.error("AI Client not initialized.")
            return None

        try:
            if self.provider == 'anthropic':
                # Map specific history format for Anthropic if needed, 
                # but 'role'/'content' matches generally. 
                # System prompt is separate in new API.
                
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=150,
                    system=self.system_prompt,
                    messages=chat_history
                )
                return response.content[0].text.strip()

            elif self.provider in ['gemini', 'google']:
                 # Gemini Format with Pydantic structured output
                 # Build conversation context
                 conversation = f"{self.system_prompt}\n\n"
                 for msg in chat_history:
                     if msg['role'] == 'user':
                         conversation += f"User: {msg['content']}\n"
                     else:
                         conversation += f"Assistant: {msg['content']}\n"
                 conversation += "Assistant:"
                 
                 # Generate with structured JSON output
                 response = self.client.models.generate_content(
                     model=self.model,
                     contents=conversation,
                     config=genai.types.GenerateContentConfig(
                         response_mime_type='application/json',
                         response_schema=ChatResponse
                     )
                 )
                 
                 # Extract token usage
                 tokens_used = 0
                 if hasattr(response, 'usage_metadata') and response.usage_metadata:
                     tokens_used = response.usage_metadata.total_token_count
                 self.last_token_count = tokens_used
                 print(f"DEBUG: Tokens used in this request: {tokens_used}")
                 
                 # Parse JSON response into Pydantic model
                 import json
                 parsed = ChatResponse.model_validate_json(response.text)
                 return parsed.message
                
            else:
                # OpenAI Fallback
                messages = [{"role": "system", "content": self.system_prompt}]
                messages.extend(chat_history)
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=150
                )
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            error_msg = str(e)
            logging.error(f"AI Generation Error ({self.provider}): {e}")
            
            # Track error internally
            self.last_error = error_msg
            self.last_token_count = 0
            
            # Log rate limit specifically if it occurs
            if "429" in error_msg or "quota" in error_msg.lower():
                 logging.warning(f"Rate Limit: {e}")
            
            # Return None - bot will skip sending message entirely
            return None
