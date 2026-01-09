# Web Monitor Setup Instructions

## 1. Installation
1.  Open your terminal in `C:\Users\sgurp\.gemini\antigravity\scratch\web_monitor`.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    playwright install
    ```

## 2. Configuration (`config.yaml`)
Open `config.yaml` and update the following:
*   **credentials**: Add your `username` and `password`.
*   **ai**: Add your `api_key`.
*   **selectors**:
    *   **CRITICAL**: You must manually inspect the chat page to find the correct CSS selectors for:
        *   `chat_history_container`: The main div holding messages.
        *   `incoming_message_bubble`: The specific class for messages from others.
        *   `message_input`: The text input field.
        *   `send_btn`: The send button.

## 3. Running
Run the bot with:
```bash
python main.py
```

## 4. First Run
*   The first time, the bot will attempt to log in.
*   If `headless: false` is set in config (recommended for first run), you can watch it working.
*   Once logged in, it saves `session.json` so next time it skips login.

## 5. Troubleshooting
*   Check `conversation_logs.txt` for errors.
*   If elements aren't found, update the selectors in `config.yaml`.
