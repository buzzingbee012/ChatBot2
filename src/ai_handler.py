import os
import logging
from openai import OpenAI
from anthropic import Anthropic
from google import genai
from pydantic import BaseModel

class ChatResponse(BaseModel):
    """Structured response model for chat completions"""
    message: str

class NameResponse(BaseModel):
    """Structured response model for name generation"""
    name: str

class AIHandler:
    def __init__(self, config):
        self.config = config
        self.provider = config.get('llm', {}).get('provider', 'openai')
        
        # Prioritize Environment Variables
        env_key = os.getenv("GEMINI_API_KEY") if self.provider in ['gemini', 'google'] else \
                  os.getenv("ANTHROPIC_API_KEY") if self.provider == 'anthropic' else \
                  os.getenv("OPENAI_API_KEY")
        
        self.api_key = env_key or config.get('llm', {}).get('api_key')
        
        if not self.api_key or "PASTE_YOUR" in self.api_key:
            logging.warning(f"No valid API Key found for provider {self.provider}. Please set GEMINI_API_KEY env var or update config.")
            self.api_key = None # Treat as missing
        
        self.client = None
        if self.provider == 'anthropic':
            self.client = Anthropic(api_key=self.api_key)
            self.model = config.get('llm', {}).get('model', 'claude-3-haiku-20240307')
        elif self.provider in ['gemini', 'google']:
            self.model = config.get('llm', {}).get('model', 'gemini-2.5-flash-lite')
            self.model = config.get('llm', {}).get('model', 'gemini-2.5-flash-lite')
            if self.api_key:
                masked_key = self.api_key[:5] + "..." + self.api_key[-5:] if len(self.api_key) > 10 else "***"
                masked_key = self.api_key[:5] + "..." + self.api_key[-5:] if len(self.api_key) > 10 else "***"
                self.client = genai.Client(api_key=self.api_key)
            else:
                 logging.error("Gemini API Key missing. AI features will be disabled.")
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
                 
                 # Robust handling of history (dict vs string vs list)
                 if isinstance(chat_history, str):
                     # If still a string for some reason, treat as user message
                     conversation += f"User: {chat_history}\n"
                 elif isinstance(chat_history, list):
                     for msg in chat_history:
                         if isinstance(msg, dict):
                            role = msg.get('role', 'user')
                            content = msg.get('content', '')
                            if role == 'user':
                                conversation += f"User: {content}\n"
                            else:
                                conversation += f"Assistant: {content}\n"
                         else:
                             # Handle odd cases where msg might be just string in list
                             conversation += f"User: {str(msg)}\n"
                             
                 conversation += "Assistant:"
                 # print(f"DEBUG: Input Prompt to Gemini:\n{conversation}") # REMOVED as requested
                 
                 # Generate with structured JSON output
                 try:
                     response = self.client.models.generate_content(
                         model=self.model,
                         contents=conversation,
                         config=genai.types.GenerateContentConfig(
                             response_mime_type='application/json',
                             response_schema=ChatResponse
                         )
                     )
                 except Exception as api_e: # Log error concisely
                     logging.error(f"Gemini API Call Failed: {api_e}")
                     raise api_e
                 
                 # Extract token usage
                 tokens_used = 0
                 if hasattr(response, 'usage_metadata') and response.usage_metadata:
                     tokens_used = response.usage_metadata.total_token_count
                 self.last_token_count = tokens_used
                 
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

    def get_next_message(self, context=None):
        """Generates a generic broadcast message."""
        if not self.client:
            return "Hello everyone! How is it going?"
        
        # Simple prompt for broadcast
        history = [{"role": "user", "content": "Generate a short, friendly greeting for a chat room. Keep it under 50 characters."}]
        return self.generate_response(history) or "Hello everyone!"

    def generate_username(self):
        """Generates a random desi female name and appends _32f."""
        fallback = "jasmin_32f"
        if not self.client:
            return fallback

        prompt = "Generate a single Indian/Desi female chat name. Not actual name but should reflect an Indian female. Don't go for obvious names. Return only the name, no punctuation, only letters. The name should be common and easy to read."
        
        try:
            if self.provider in ['gemini', 'google']:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type='application/json',
                        response_schema=NameResponse
                    )
                )
                import json
                parsed = NameResponse.model_validate_json(response.text)
                name = parsed.name.strip().lower()
                # Ensure only letters and numbers
                import re
                name = re.sub(r'[^a-zA-Z0-9]', '', name)
                if not name:
                    return fallback
                return f"{name}_32f"
            else:
                # Fallback for other providers if needed
                messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=20
                )
                name = response.choices[0].message.content.strip().lower()
                import re
                name = re.sub(r'[^a-zA-Z0-9]', '', name)
                if not name:
                    return fallback
                return f"{name}_32f"
        except Exception as e:
            logging.error(f"Error generating username: {e}")
            return fallback
