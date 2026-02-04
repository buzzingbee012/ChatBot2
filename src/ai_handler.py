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
            # Extract previous assistant messages to avoid repetitions
            previous_responses = []
            if isinstance(chat_history, list):
                previous_responses = [m.get('content', '') for m in chat_history if m.get('role') == 'assistant' and m.get('content')]
            
            avoid_list_str = "\n".join([f"- {r}" for r in previous_responses[-10:]])
            avoid_prompt = f"\n\nSTRICT REPETITION AVOIDANCE:\nDo NOT repeat any of these previous messages you sent to this user:\n{avoid_list_str}\n\nGenerate a fresh, unique response." if previous_responses else ""

            for attempt in range(3): # Try up to 3 times to get a unique response
                if self.provider == 'anthropic':
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=150,
                        system=self.system_prompt + avoid_prompt,
                        messages=chat_history
                    )
                    generated_text = response.content[0].text.strip()

                elif self.provider in ['gemini', 'google']:
                    conversation = f"{self.system_prompt}{avoid_prompt}\n\n"
                    if isinstance(chat_history, list):
                        for msg in chat_history:
                            role = msg.get('role', 'user')
                            content = msg.get('content', '')
                            conversation += f"{'User' if role == 'user' else 'Assistant'}: {content}\n"
                    conversation += "Assistant:"
                    
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=conversation,
                        config=genai.types.GenerateContentConfig(
                            response_mime_type='application/json',
                            response_schema=ChatResponse
                        )
                    )
                    
                    tokens_used = getattr(response.usage_metadata, 'total_token_count', 0) if hasattr(response, 'usage_metadata') else 0
                    self.last_token_count = tokens_used
                    
                    import json
                    parsed = ChatResponse.model_validate_json(response.text)
                    generated_text = parsed.message
                    
                else:
                    # OpenAI Fallback
                    messages = [{"role": "system", "content": self.system_prompt + avoid_prompt}]
                    messages.extend(chat_history)
                    
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=150
                    )
                    generated_text = response.choices[0].message.content.strip()

                # Check for exact duplication
                if generated_text not in previous_responses:
                    return generated_text
                
                self.logger.warning(f"AI repeated a message. Retrying ({attempt+1}/3)...")
            
            # If all retries fail, return the last one anyway or None
            return generated_text
                
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
        fallback = "jasmin32f"
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
                    return f"{clean_name}32f"
            
            return fallback
        except Exception as e:
            self.logger.error(f"Error generating username: {e}")
            return fallback
