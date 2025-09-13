from flask import Flask
import threading
import time
import logging
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
            time.sleep(60)

@app.route('/')
def home():
    return "Twitter-to-Telegram Bot is running! Bot thread is active."

@app.route('/health')
def health():
    return "OK"

@app.route('/bot-status')
def bot_status():
    """Check if bot thread is running"""
    return f"Bot thread started: {bot_thread_started}"

# Start the bot thread when the app loads
if __name__ == '__main__':
    bot_thread = threading.Thread(target=bot_worker, daemon=True)
    bot_thread.start()
    app.run(host='0.0.0.0', port=5000)
