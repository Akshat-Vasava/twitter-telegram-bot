from flask import Flask
import threading
import time
import logging
import os
from twitter_bot import check_and_forward_tweets, CHECK_INTERVAL, logger as bot_logger

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to track if bot thread is running
bot_thread_started = False

def bot_worker():
    """Background thread that runs the bot"""
    global bot_thread_started
    bot_thread_started = True
    logger.info("✅ Bot worker thread started successfully!")
    bot_logger.info("✅ Bot worker thread started successfully!")
    
    while True:
        try:
            logger.info("🔄 Checking for new tweets...")
            bot_logger.info("🔄 Checking for new tweets...")
            check_and_forward_tweets()
            logger.info(f"💤 Sleeping for {CHECK_INTERVAL} seconds...")
            bot_logger.info(f"💤 Sleeping for {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"❌ Error in bot worker: {e}")
            bot_logger.error(f"❌ Error in bot worker: {e}")
            time.sleep(60)  # Wait before retrying

@app.before_first_request
def start_bot_thread():
    """Start the bot thread when the first request comes in"""
    global bot_thread_started
    if not bot_thread_started:
        logger.info("🚀 Starting bot thread...")
        bot_thread = threading.Thread(target=bot_worker, daemon=True)
        bot_thread.start()

@app.route('/')
def home():
    return "Twitter-to-Telegram Bot is running! Bot thread should start automatically."

@app.route('/health')
def health():
    return "OK"

@app.route('/start-bot')
def start_bot():
    """Manual endpoint to start the bot"""
    start_bot_thread()
    return "Bot thread started manually!"

@app.route('/bot-status')
def bot_status():
    """Check if bot thread is running"""
    return f"Bot thread started: {bot_thread_started}"

# Start the bot thread when the app loads (for development)
if __name__ == '__main__':
    start_bot_thread()
    app.run(host='0.0.0.0', port=5000)
