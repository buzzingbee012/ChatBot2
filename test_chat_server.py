from flask import Flask, render_template, request, jsonify
import yaml
from src.ai_handler import AIHandler
from src.stats_tracker import StatsTracker
import os

app = Flask(__name__)

# Load Config
CONFIG_PATH = "config.yaml"
try:
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    print("Config loaded.")
except Exception as e:
    print(f"Error loading config: {e}")
    exit(1)

# Initialize AI
ai_handler = AIHandler(config)
stats_tracker = StatsTracker()

@app.route('/')
def home():
    return render_template('chat.html', model_name=ai_handler.model)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message')
    history = data.get('history', [])
    
    # Append new user message to history
    history.append({"role": "user", "content": user_message})
    
    # Generate Response
    response = ai_handler.generate_response(history)
    
    # Track stats (tokens and errors)
    tokens = getattr(ai_handler, 'last_token_count', 0)
    error = getattr(ai_handler, 'last_error', None)
    stats_tracker.increment_today(tokens=tokens, error=error)
    
    return jsonify({
        "reply": response or "Error generating response."
    })

@app.route('/stats')
def stats():
    stats_data = stats_tracker.get_stats()
    total = stats_tracker.get_total()
    total_tokens = stats_tracker.get_total_tokens()
    return render_template('stats.html', stats=stats_data, total=total, total_tokens=total_tokens)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
