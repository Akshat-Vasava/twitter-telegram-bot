import keep_alive  # Add this at the very top
from flask import Flask
import threading
import time
import logging
import os
from twitter_bot import check_and_forward_tweets, CHECK_INTERVAL

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable to track if bot thread is running
bot_thread_started = False
bot_thread = None

def bot_worker():
    """Background thread that runs the bot"""
    global bot_thread_started
    bot_thread_started = True
    logger.info("✅ Bot worker thread started successfully!")
    
    # Add a small delay to ensure Flask app is fully ready
    time.sleep(2)
    
    # Initial check immediately
    logger.info("🔄 Performing initial tweet check...")
    initial_count = check_and_forward_tweets()
    logger.info(f"✅ Initial check completed. Processed {initial_count} tweets.")
    
    # Then continue with regular intervals
    while True:
        try:
            logger.info(f"💤 Sleeping for {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
            logger.info("🔄 Checking for new tweets...")
            tweet_count = check_and_forward_tweets()
            if tweet_count > 0:
                logger.info(f"✅ Processed {tweet_count} new tweets")
            else:
                logger.info("✅ No new tweets found")
        except Exception as e:
            logger.error(f"❌ Error in bot worker: {e}")
            time.sleep(60)  # Wait before retrying

def start_bot_thread():
    """Start the bot thread"""
    global bot_thread, bot_thread_started
    if not bot_thread_started and (bot_thread is None or not bot_thread.is_alive()):
        logger.info("🚀 Starting bot thread...")
        bot_thread = threading.Thread(target=bot_worker, daemon=True)
        bot_thread.start()
        return True
    return False

# Start the bot thread when the app imports this module
start_bot_thread()

@app.route('/')
def home():
    return "Twitter-to-Telegram Bot is running! Bot thread should be active."

@app.route('/health')
def health():
    return "OK"

@app.route('/bot-status')
def bot_status():
    """Check if bot thread is running"""
    global bot_thread_started, bot_thread
    status = f"Bot thread started: {bot_thread_started}"
    if bot_thread:
        status += f", Alive: {bot_thread.is_alive()}"
    return status

@app.route('/trigger-check')
def manual_start():
    """Manually start the bot thread"""
    if start_bot_thread():
        return "Bot thread started manually!"
    return "Bot thread already running or starting..."

@app.route('/trigger-check')
def trigger_check():
    """Manually trigger a tweet check"""
    try:
        result = check_and_forward_tweets()
        return f"Manual check completed. Processed {result} tweets."
    except Exception as e:
        return f"Error during manual check: {e}"

# For Koyeb deployment
if __name__ == '__main__':
    start_bot_thread()
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
