import requests
import logging

class ManyChatHandler:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://api.manychat.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        self.logger = logging.getLogger("WebMonitor")

    def get_subscriber_info(self, subscriber_id):
        """Fetch subscriber details."""
        url = f"{self.base_url}/fb/subscriber/getInfo?subscriber_id={subscriber_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get('data', {})
        except Exception as e:
            self.logger.error(f"ManyChat API Error (getInfo): {e}")
            return None

    def send_message(self, subscriber_id, message):
        """Send a simple text message to a subscriber."""
        url = f"{self.base_url}/fb/sending/sendContent"
        payload = {
            "subscriber_id": subscriber_id,
            "data": {
                "version": "v2",
                "content": {
                    "messages": [
                        {
                            "type": "text",
                            "text": message
                        }
                    ]
                }
            }
        }
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"ManyChat API Error (sendContent): {e}")
            return None

    def get_conversation_history(self, subscriber_id, meta_access_token=None):
        """
        Retrieves history. Since ManyChat API has limitations, this might fallback to Meta API 
        or assume history is passed via webhook if available.
        """
        # Placeholder for history retrieval logic.
        # If the user provides a Meta token, we can use Meta Graph API.
        # Otherwise, we might only have access to current message.
        self.logger.warning("get_conversation_history is a placeholder. Implementing fallback/Meta API if token provided.")
        return []
