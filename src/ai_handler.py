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
        self.logger = logging.getLogger("WebMonitor")
        self.config = config
        self.provider = config.get('llm', {}).get('provider', 'openai')
        
        # Prioritize Environment Variables
        env_key = os.getenv("GEMINI_API_KEY") if self.provider in ['gemini', 'google'] else \
                  os.getenv("ANTHROPIC_API_KEY") if self.provider == 'anthropic' else \
                  os.getenv("OPENAI_API_KEY")
        
        self.api_key = env_key or config.get('llm', {}).get('api_key')
        
        if not self.api_key or "PASTE_YOUR" in self.api_key:
            self.logger.warning(f"No valid API Key found for provider {self.provider}. Please set GEMINI_API_KEY env var or update config.")
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
                 self.logger.error("Gemini API Key missing. AI features will be disabled.")
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
            self.logger.error("AI Client not initialized.")
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
                     self.logger.error(f"Gemini API Call Failed: {api_e}")
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

        # Load recent names to avoid repeats
        recent_names_file = "recent_names.json"
        recent_names = []
        if os.path.exists(recent_names_file):
            try:
                with open(recent_names_file, 'r') as f:
                    recent_names = json.load(f)
            except: pass
            
        recent_names_str = ", ".join(recent_names) if recent_names else "None yet"
        
        # Randomize by picking a random letter and region to force variety
        import random
        import string
        letter = random.choice(string.ascii_uppercase)
        regions = ["North Indian", "South Indian", "Punjabi", "Bengali", "Gujarati", "Modern Indian"]
        region = random.choice(regions)
        
        prompt = (
            f"Generate a single {region} female chat name starting with the letter '{letter}'. "
            "Not actual name but should reflect an Indian female. Don't go for obvious names like Priya or Anjali. "
            f"AVOID these recently used names: {recent_names_str}. "
            "Return only the name, no punctuation, only letters. The name should be common and easy to read."
        )
        
        try:
            generated_name = None
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
                generated_name = parsed.name.strip().lower()
            else:
                # Fallback for other providers if needed
                messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=20
                )
                generated_name = response.choices[0].message.content.strip().lower()

            if generated_name:
                # Ensure only letters and numbers
                import re
                clean_name = re.sub(r'[^a-zA-Z0-9]', '', generated_name)
                if clean_name:
                    # Update history
                    recent_names.append(clean_name)
                    if len(recent_names) > 10:
                        recent_names = recent_names[-10:]
                    try:
                        with open(recent_names_file, 'w') as f:
                            json.dump(recent_names, f)
                    except: pass
                    return f"{clean_name}_32f"
            
            return fallback
        except Exception as e:
            self.logger.error(f"Error generating username: {e}")
            return fallback
