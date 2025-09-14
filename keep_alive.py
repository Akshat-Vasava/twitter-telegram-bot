import requests
import time
import threading
import os

def keep_alive():
    """Ping the bot's health endpoint to keep it awake"""
    bot_url = os.getenv('KOYEB_APP_URL', 'https://your-app-name-.koyeb.app')
    
    while True:
        try:
            response = requests.get(f"{bot_url}/health", timeout=10)
            print(f"Ping successful: {response.status_code}")
        except Exception as e:
            print(f"Ping failed: {e}")
        
        # Ping every 45 minutes (less than 1 hour)
        time.sleep(2700)  # 45 minutes

# Start in a separate thread
threading.Thread(target=keep_alive, daemon=True).start()
