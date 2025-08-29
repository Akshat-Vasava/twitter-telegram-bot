from flask import Flask
import threading
import time
from twitter_bot import check_and_forward_tweets, CHECK_INTERVAL
import logging

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def bot_worker():
    """Background thread that runs the bot"""
    logger.info("Starting bot worker thread...")
    while True:
        try:
            check_and_forward_tweets()
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"Error in bot worker: {e}")
            time.sleep(60)  # Wait before retrying

@app.route('/')
def home():
    return "Twitter-to-Telegram Bot is running!"

@app.route('/health')
def health():
    return "OK"

if __name__ == '__main__':
    # Start the bot in a background thread
    bot_thread = threading.Thread(target=bot_worker, daemon=True)
    bot_thread.start()
    
    # Start the web server
    app.run(host='0.0.0.0', port=5000)
