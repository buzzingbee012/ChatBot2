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
        
        # API Key management
        if self.provider == 'google':
            self.api_key = os.getenv("GOOGLE_API_KEY") or config.get('llm', {}).get('api_key')
        elif self.provider == 'anthropic':
            self.api_key = os.getenv("ANTHROPIC_API_KEY") or config.get('llm', {}).get('api_key')
        elif self.provider == 'llama':
            # Support Groq via OpenAI client if base_url is provided
            self.api_key = os.getenv("GROQ_API_KEY") or config.get('llm', {}).get('api_key')
        else:
            self.api_key = os.getenv("OPENAI_API_KEY") or config.get('llm', {}).get('api_key')
        
        self.base_url = config.get('llm', {}).get('base_url')
        
        if not self.api_key or "PASTE_YOUR" in self.api_key:
            self.logger.warning(f"No valid API Key found for provider {self.provider}. Please set the correct env var or update config.")
            self.api_key = None
        
        self.client = None
        if self.provider == 'anthropic' and self.api_key:
            self.client = Anthropic(api_key=self.api_key)
            self.model = config.get('llm', {}).get('model', 'claude-3-haiku-20240307')
        elif self.provider == 'google' and self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            self.model = config.get('llm', {}).get('model', 'gemini-2.0-flash-lite')
        elif self.api_key:
            # Default to OpenAI-compatible client (OpenAI, Groq/Llama)
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            self.model = config.get('llm', {}).get('model') or config.get('ai', {}).get('model', 'gpt-4o')
        else:
            self.logger.error(f"API Key missing for {self.provider}. AI features will be disabled.")
            
        self.system_prompt = config.get('llm', {}).get('system_prompt') or config.get('ai', {}).get('system_prompt', "You represent a user in a chat room.")
        self.last_token_count = 0
        self.last_error = None

    def generate_response(self, chat_history):
        if not self.client:
            self.logger.error("AI Client not initialized.")
            return None

        try:
            previous_responses = []
            if isinstance(chat_history, list):
                previous_responses = [m.get('content', '') for m in chat_history if m.get('role') == 'assistant' and m.get('content')]
            
            avoid_list_str = "\n".join([f"- {r}" for r in previous_responses[-10:]])
            avoid_prompt = f"\n\nSTRICT REPETITION AVOIDANCE:\nDo NOT repeat any of these previous messages you sent to this user:\n{avoid_list_str}\n\nGenerate a fresh, unique response." if previous_responses else ""

            for attempt in range(3):
                if self.provider == 'anthropic':
                    response = self.client.messages.create(
                        model=self.model,
                        max_tokens=150,
                        system=self.system_prompt + avoid_prompt,
                        messages=chat_history
                    )
                    generated_text = response.content[0].text.strip()

                elif self.provider == 'google':
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
                    parsed = ChatResponse.model_validate_json(response.text)
                    generated_text = parsed.message
                    
                else:
                    # OpenAI / Llama (Groq)
                    messages = [{"role": "system", "content": self.system_prompt + avoid_prompt}]
                    messages.extend(chat_history)
                    
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        max_tokens=150
                    )
                    generated_text = response.choices[0].message.content.strip()

                if generated_text not in previous_responses:
                    return generated_text
                
                self.logger.warning(f"AI repeated a message. Retrying ({attempt+1}/3)...")
            
            return generated_text
                
        except Exception as e:
            self.logger.error(f"AI Generation Error ({self.provider}): {e}")
            return None

    def get_next_message(self, context=None):
        if not self.client:
            return "Hello everyone! How is it going?"
        
        history = [{"role": "user", "content": "Generate a short, friendly greeting for a chat room. Keep it under 50 characters."}]
        return self.generate_response(history) or "Hello everyone!"

    def generate_username(self):
        import random
        import string
        import json
        
        def get_fallback():
             vowels = "aeiou"
             consonants = "bcdfghjklmnpqrstvwxyz"
             name = ""
             for _ in range(random.randint(2,3)):
                 name += random.choice(consonants) + random.choice(vowels)
             return f"{name}{random.randint(10,99)}"

        fallback = get_fallback()
        if not self.client:
            return fallback

        recent_names_file = "recent_names.json"
        recent_names = []
        if os.path.exists(recent_names_file):
            try:
                with open(recent_names_file, 'r') as f:
                    recent_names = json.load(f)
            except: pass
            
        recent_names_str = ", ".join(recent_names) if recent_names else "None yet"
        
        letter = random.choice(string.ascii_uppercase)
        regions = ["North Indian", "South Indian", "Punjabi", "Bengali", "Gujarati", "Modern Indian", "Mumbai", "Delhi", "Haryanvi", "Himachali"]
        region = random.choice(regions)
        
        prompt = (
            f"Generate a single {region} female chat name starting with the letter '{letter}'. "
            "Not actual name but should reflect an Indian female. Don't go for obvious names like Priya or Anjali. "
            f"AVOID these recently used names: {recent_names_str}. "
            "Return only the name, no punctuation, only letters. The name should be short and common."
        )
        
        try:
            generated_name = None
            if self.provider == 'google':
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type='application/json',
                        response_schema=NameResponse
                    )
                )
                parsed = NameResponse.model_validate_json(response.text)
                generated_name = parsed.name.strip().lower()
            else:
                messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=20
                )
                generated_name = response.choices[0].message.content.strip().lower()

            if generated_name:
                import re
                clean_name = re.sub(r'[^a-zA-Z0-9]', '', generated_name)
                if clean_name:
                    recent_names.append(clean_name)
                    if len(recent_names) > 30:
                        recent_names = recent_names[-30:]
                    try:
                        with open(recent_names_file, 'w') as f:
                            json.dump(recent_names, f)
                    except: pass
                    return f"{clean_name}"
            
            return fallback
        except Exception as e:
            self.logger.error(f"Error generating username: {e}")
            return fallback

    async def generate_lobby_message(self):
        if not self.client:
            return "Hey everyone, how's it going?"

        prompt = (
            "Generate an ultra-short (MAX 25 characters) lobby message for an Indian female. "
            "Use Hinglish (e.g., 'Bored hoon, koi h?', 'Hi, baat karega?'). "
            "Sound flirty, cute, and real. Use 1 emoji. "
            "Return only the text, no quotes."
        )

        try:
            if self.provider == 'google':
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type='application/json',
                        response_schema=ChatResponse
                    )
                )
                parsed = ChatResponse.model_validate_json(response.text)
                return parsed.message.strip()
            else:
                messages = [{"role": "system", "content": "You are a flirty Indian female in a chat room."}, {"role": "user", "content": prompt}]
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=25
                )
                return response.choices[0].message.content.strip().replace('"', '')
        except Exception as e:
            self.logger.error(f"Error generating lobby message: {e}")
            return "Hey guys, anyone bored? 😉"
