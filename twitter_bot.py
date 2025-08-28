import os
import time
import logging
import requests
import json
from datetime import datetime
import telebot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')
TWITTER_TARGET_USER = "AboutNodKrai"
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 900))  # 15 minutes
MAX_TWEETS_PER_CHECK = int(os.getenv('MAX_TWEETS_PER_CHECK', 5))  # Reduced to 5
DATA_FILE = 'data/processed_tweets.txt'
LOG_FILE = 'logs/bot.log'
TEMP_DIR = 'temp/'

# Rate limit tracking
last_api_call = 0
RATE_LIMIT_DELAY = 2  # seconds between API calls (changed variable name)

# Validate required settings
required_vars = [
    ('TELEGRAM_BOT_TOKEN', TELEGRAM_BOT_TOKEN),
    ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID),
    ('TWITTER_BEARER_TOKEN', TWITTER_BEARER_TOKEN),
]

missing_vars = [var for var, value in required_vars if not value]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Setup logging
os.makedirs('logs', exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Telegram bot
telegram_bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

def enforce_rate_limit():
    """Respect Twitter API rate limits"""
    global last_api_call
    current_time = time.time()
    elapsed = current_time - last_api_call
    
    if elapsed < RATE_LIMIT_DELAY:
        sleep_time = RATE_LIMIT_DELAY - elapsed
        time.sleep(sleep_time)
    
    last_api_call = time.time()

def load_processed_tweets():
    """Load processed tweets from file"""
    processed_tweets = set()
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                for line in f:
                    processed_tweets.add(line.strip())
    except Exception as e:
        logger.error(f"Error loading processed tweets: {e}")
    return processed_tweets

def save_processed_tweets(processed_tweets):
    """Save processed tweets to file"""
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, 'w') as f:
            for tweet_id in processed_tweets:
                f.write(f"{tweet_id}\n")
    except Exception as e:
        logger.error(f"Error saving processed tweets: {e}")

def get_user_id(username):
    """Get Twitter user ID from username"""
    url = f"https://api.twitter.com/2/users/by/username/{username}"
    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"
    }
    
    try:
        enforce_rate_limit()  # Changed function name
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check for rate limits
        if response.status_code == 429:
            logger.warning("Rate limit hit when getting user ID. Waiting 15 minutes...")
            time.sleep(900)  # Wait 15 minutes
            return get_user_id(username)  # Retry
        
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data:
            return data['data']['id']
        else:
            logger.error(f"User not found: {username}")
            return None
    except Exception as e:
        logger.error(f"Error fetching user ID: {e}")
        return None

def get_recent_tweets(user_id):
    """Get recent tweets from a user with rate limit handling"""
    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"
    }
    
    params = {
        "max_results": MAX_TWEETS_PER_CHECK,
        "tweet.fields": "created_at,attachments,entities,text,referenced_tweets",
        "expansions": "attachments.media_keys",
        "media.fields": "url,type,preview_image_url,variants"
    }
    
    try:
        enforce_rate_limit()  # Changed function name
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        # Handle rate limits
        if response.status_code == 429:
            logger.warning("Rate limit hit when fetching tweets. Waiting 15 minutes...")
            time.sleep(900)  # Wait 15 minutes
            return get_recent_tweets(user_id)  # Retry
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching tweets: {e}")
        return None

def download_media(media_url, filename):
    """Download media from URL"""
    try:
        response = requests.get(media_url, timeout=15)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        logger.error(f"Failed to download media: {e}")
        return False

def send_media_to_telegram(media_path, caption=None, is_photo=True):
    """Send media to Telegram with caption"""
    try:
        with open(media_path, 'rb') as media:
            if is_photo:
                telegram_bot.send_photo(
                    TELEGRAM_CHAT_ID,
                    media,
                    caption=caption,
                    parse_mode='HTML'
                )
            else:
                telegram_bot.send_video(
                    TELEGRAM_CHAT_ID,
                    media,
                    caption=caption,
                    parse_mode='HTML'
                )
        logger.info("Media sent to Telegram successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send media to Telegram: {e}")
        return False

def clean_tweet_text(text):
    """Clean tweet text by removing URLs and unwanted content"""
    import re
    
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    
    # Remove Twitter's "t.co" shortened links
    text = re.sub(r'pic\.twitter\.com/\S+', '', text)
    
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def is_retweet(tweet):
    """Check if a tweet is a retweet"""
    if 'referenced_tweets' in tweet:
        for ref_tweet in tweet['referenced_tweets']:
            if ref_tweet['type'] == 'retweeted':
                return True
    return False

def process_tweet(tweet, media_data=None):
    """Process a single tweet and extract relevant data - only media tweets, no retweets"""
    
    # Skip retweets
    if is_retweet(tweet):
        logger.info(f"Skipping retweet: {tweet['id']}")
        return None
    
    tweet_id = tweet['id']
    text = clean_tweet_text(tweet['text'])
    created_at = tweet['created_at']
    
    # Check for media attachments - only process if media exists
    media_urls = []
    if 'attachments' in tweet and media_data and 'includes' in media_data and 'media' in media_data['includes']:
        media_keys = tweet['attachments']['media_keys']
        for media_key in media_keys:
            for media in media_data['includes']['media']:
                if media['media_key'] == media_key:
                    if media['type'] == 'photo':
                        media_urls.append({
                            'type': 'photo',
                            'url': media['url']
                        })
                    elif media['type'] == 'video':
                        # For videos, try to get the best quality variant
                        best_bitrate = 0
                        best_url = None
                        
                        if 'variants' in media:
                            for variant in media['variants']:
                                if 'bit_rate' in variant and variant['bit_rate'] > best_bitrate:
                                    best_bitrate = variant['bit_rate']
                                    best_url = variant['url']
                                elif 'url' in variant and not best_url:
                                    best_url = variant['url']
                        
                        if best_url:
                            media_urls.append({
                                'type': 'video',
                                'url': best_url
                            })
    
    # Only return if there's media
    if not media_urls:
        return None
    
    return {
        'id': tweet_id,
        'text': text,
        'created_at': created_at,
        'media_urls': media_urls
    }

def format_caption(tweet_data):
    """Format caption - just the tweet text, no username or time"""
    return tweet_data['text']

def cleanup_temp_files():
    """Clean up temporary files older than 1 hour"""
    try:
        now = time.time()
        for filename in os.listdir(TEMP_DIR):
            file_path = os.path.join(TEMP_DIR, filename)
            if os.path.isfile(file_path) and now - os.path.getctime(file_path) > 3600:
                os.remove(file_path)
                logger.info(f"Cleaned up temp file: {filename}")
    except Exception as e:
        logger.error(f"Error cleaning up temp files: {e}")

def check_and_forward_tweets():
    """Check for new media tweets and forward them to Telegram (no retweets)"""
    logger.info(f"Checking for new media tweets from @{TWITTER_TARGET_USER}...")
    
    processed_tweets = load_processed_tweets()
    
    user_id = get_user_id(TWITTER_TARGET_USER)
    if not user_id:
        logger.error(f"Could not get user ID for @{TWITTER_TARGET_USER}")
        return 0
    
    tweets_data = get_recent_tweets(user_id)
    if not tweets_data or 'data' not in tweets_data:
        logger.info("No tweets data received or no new tweets")
        return 0
    
    new_tweets = []
    
    for tweet in tweets_data['data']:
        if tweet['id'] not in processed_tweets:
            processed_tweet = process_tweet(tweet, tweets_data)
            if processed_tweet:  # Only add if it has media and is not a retweet
                new_tweets.append(processed_tweet)
                processed_tweets.add(tweet['id'])
            else:
                # Mark retweets as processed even if we skip them
                processed_tweets.add(tweet['id'])
    
    for tweet in reversed(new_tweets):
        caption = format_caption(tweet)
        
        # Send each media item
        for i, media in enumerate(tweet['media_urls']):
            media_ext = '.mp4' if media['type'] == 'video' else '.jpg'
            media_filename = os.path.join(TEMP_DIR, f"temp_{tweet['id']}_{i}{media_ext}")
            
            if download_media(media['url'], media_filename):
                is_photo = media['type'] == 'photo'
                
                # Only add caption to the first media item if multiple
                media_caption = caption if i == 0 else None
                
                if send_media_to_telegram(media_filename, caption=media_caption, is_photo=is_photo):
                    logger.info(f"Sent media for tweet: {tweet['id']}")
                
                # Clean up temporary file
                try:
                    os.remove(media_filename)
                except:
                    pass
                
                time.sleep(1)  # Avoid rate limiting
        
        time.sleep(2)  # Avoid rate limiting
    
    # Save processed tweets
    save_processed_tweets(processed_tweets)
    cleanup_temp_files()
    
    logger.info(f"Processed {len(new_tweets)} new media tweets from @{TWITTER_TARGET_USER}")
    return len(new_tweets)

def main():
    """Main function to run the bot"""
    logger.info(f"Starting Twitter Media to Telegram bot for @{TWITTER_TARGET_USER}...")
    
    # Initial check
    check_and_forward_tweets()
    
    try:
        while True:
            check_and_forward_tweets()
            logger.info(f"Next check in {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Bot shutdown complete")

if __name__ == "__main__":
    main()