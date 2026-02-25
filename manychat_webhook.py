from flask import Flask, request, jsonify
import yaml
import asyncio
import logging
from src.manychat_bot import ManyChatBot

app = Flask(__name__)

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebMonitor")

def load_config(path="config.yaml"):
    try:
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Try to load secrets file for local dev override
        secrets_path = "config.secrets.yaml"
        import os
        if os.path.exists(secrets_path):
            with open(secrets_path, 'r') as sf:
                secrets = yaml.safe_load(sf)
                for key in ['llm', 'manychat', 'ai']:
                    if secrets and key in secrets:
                        if key not in config: config[key] = {}
                        config[key].update(secrets[key])
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

config = load_config()
bot = ManyChatBot(config)

@app.route('/manychat/webhook', methods=['POST'])
async def manychat_webhook():
    """
    Webhook endpoint for ManyChat External Requests.
    Expected JSON payload:
    {
        "subscriber_id": "12345678",
        "message": "Hello",
        "history": [{"role": "user", "content": "Hi"}, ...] (optional)
    }
    """
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No JSON payload provided"}), 400
        
    subscriber_id = data.get('subscriber_id')
    message = data.get('message')
    history = data.get('history')

    if not subscriber_id:
        return jsonify({"status": "error", "message": "subscriber_id is required"}), 400

    # Run the bot logic
    success = await bot.handle_message(subscriber_id, current_message=message, history=history)
    
    if success:
        return jsonify({"status": "success", "message": "Reply sent"})
    else:
        return jsonify({"status": "error", "message": "Failed to process message"}), 500

if __name__ == '__main__':
    # Use hypercorn or similar for production, Flask dev server for testing
    app.run(debug=True, port=8000)
