from flask import Flask
import threading
import time
import logging
import os
from twitter_bot import check_and_forward_tweets, CHECK_INTERVAL, logger as bot_logger

app = Flask(__name__)

# Setup logging - Match the format from twitter_bot.py for consistency
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variable to track if bot thread is running
bot_thread_started = False
bot_thread = None

def bot_worker():
    """Background thread that runs the bot"""
    global bot_thread_started
    bot_thread_started = True
    logger.info("✅ Bot worker thread started successfully!")
    bot_logger.info("✅ Bot worker thread started successfully!")
    
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
            bot_logger.error(f"❌ Error in bot worker: {e}")
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
    return """
    <h1>Twitter-to-Telegram Bot is Running! 🚀</h1>
    <p>Endpoints:</p>
    <ul>
        <li><a href="/health">/health</a> - Health check</li>
        <li><a href="/bot-status">/bot-status</a> - Bot thread status</li>
        <li><a href="/trigger-check">/trigger-check</a> - Manual tweet check</li>
    </ul>
    """

@app.route('/health')
def health():
    """Health check endpoint for Koyeb"""
    global bot_thread_started, bot_thread
    if bot_thread and bot_thread.is_alive():
        return "OK", 200
    else:
        return "Bot thread not running", 500

@app.route('/bot-status')
def bot_status():
    """Check if bot thread is running"""
    global bot_thread_started, bot_thread
    status = {
        "bot_thread_started": bot_thread_started,
        "bot_thread_alive": bot_thread.is_alive() if bot_thread else False,
        "check_interval_seconds": CHECK_INTERVAL,
        "data_directory": os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'),
        "log_directory": os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    }
    return status

@app.route('/trigger-check')
def trigger_check():
    """Manually trigger a tweet check"""
    try:
        result = check_and_forward_tweets()
        return {
            "status": "success",
            "message": f"Manual check completed",
            "tweets_processed": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error during manual check: {e}"
        }, 500

# For Koyeb deployment
if __name__ == '__main__':
    # Ensure data and logs directories exist before starting
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)
    
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Log directory: {log_dir}")
    
    start_bot_thread()
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
