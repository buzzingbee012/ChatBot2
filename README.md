# AI ChatBot Monitor

A dual-monitor automated chatbot that interacts on Wireclub and Generic IRC-like sites, powered by Llama AI.

## 1. Setup
1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    playwright install
    ```

2.  **Secrets Configuration**:
    *   This project separates code from secrets.
    *   Copy `config.secrets.example.yaml` to `config.secrets.yaml`.
    *   **Edit `config.secrets.yaml`** and enter your:
        *   Groq API Key (Llama)
        *   Wireclub Credentials
        *   Firebase Credentials path (if using Firebase)

3.  **Firebase (Optional)**:
    *   Place your `serviceAccountKey.json` in the root directory.
    *   **Note**: This file is git-ignored for security.

4.  **GitHub Secrets / Environment Variables (CI/CD)**:
    *   If deploying to a cloud environment (like GitHub Actions, Render, Heroku), you can set these Environment Variables instead of using `config.secrets.yaml`:
        *   `GROQ_API_KEY`
        *   `WIRECLUB_EMAIL`
        *   `WIRECLUB_PASSWORD`
        *   `WIRECLUB_USERNAME`
        *   `SITE_TWO_USERNAME`

## 2. Running
```bash
python main.py
```
*   **Parallel Mode**: By default, it runs both `WireBot` and `SiteTwoBot`.
*   **Single Bot**: Use `python main.py --bot wirebot` to run only one.

## 3. Features
*   **Per-Bot Stats**: View detailed stats in `templates/stats.html`.
*   **Auto-Reply**: Uses Llama AI to reply intelligently.
*   **Context Aware**: Parses chat HTML to distinguish user vs assistant messages.
*   **Robust**: Auto-recovers from login failures and CAPTCHAs.

## 4. Troubleshooting
*   Check `conversation_logs.txt` for detailed logs.
*   If `WireBot` history is blank, the bot now automatically tries 6 different selectors. Check logs for "Scraped History with..."

