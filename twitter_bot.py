import os
import time
import logging
import requests
import json
import re
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
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 900))
MAX_TWEETS_PER_CHECK = int(os.getenv('MAX_TWEETS_PER_CHECK', 5))

# Use Render's ephemeral storage for temp files
DATA_FILE = '/tmp/processed_tweets.txt'
LOG_FILE = '/tmp/bot.log'

# Rate limit tracking
last_api_call = 0
RATE_LIMIT_DELAY = 2

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
    global last_api_call
    current_time = time.time()
    elapsed = current_time - last_api_call
    
    if elapsed < RATE_LIMIT_DELAY:
        sleep_time = RATE_LIMIT_DELAY - elapsed
        time.sleep(sleep_time)
    
    last_api_call = time.time()

def load_processed_tweets():
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
    try:
        with open(DATA_FILE, 'w') as f:
            for tweet_id in processed_tweets:
                f.write(f"{tweet_id}\n")
    except Exception as e:
        logger.error(f"Error saving processed tweets: {e}")

def get_user_id(username):
    url = f"https://api.twitter.com/2/users/by/username/{username}"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    
    try:
        enforce_rate_limit()
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 429:
            logger.warning("Rate limit hit. Waiting 15 minutes...")
            time.sleep(900)
            return get_user_id(username)
        
        response.raise_for_status()
        data = response.json()
        return data['data']['id'] if 'data' in data else None
    except Exception as e:
        logger.error(f"Error fetching user ID: {e}")
        return None

def get_recent_tweets(user_id):
    url = f"https://api.twitter.com/2/users/{user_id}/tweets"
    headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
    
    params = {
        "max_results": MAX_TWEETS_PER_CHECK,
        "tweet.fields": "created_at,attachments,entities,text,referenced_tweets",
        "expansions": "attachments.media_keys",
        "media.fields": "url,type,preview_image_url,variants"
    }
    
    try:
        enforce_rate_limit()
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 429:
            logger.warning("Rate limit hit. Waiting 15 minutes...")
            time.sleep(900)
            return get_recent_tweets(user_id)
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching tweets: {e}")
        return None

def download_media(media_url, filename):
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
    try:
        with open(media_path, 'rb') as media:
            if is_photo:
                telegram_bot.send_photo(TELEGRAM_CHAT_ID, media, caption=caption, parse_mode='HTML')
            else:
                telegram_bot.send_video(TELEGRAM_CHAT_ID, media, caption=caption, parse_mode='HTML')
        return True
    except Exception as e:
        logger.error(f"Failed to send media: {e}")
        return False

def clean_tweet_text(text):
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'pic\.twitter\.com/\S+', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def is_retweet(tweet):
    if 'referenced_tweets' in tweet:
        for ref_tweet in tweet['referenced_tweets']:
            if ref_tweet['type'] == 'retweeted':
                return True
    return False

def process_tweet(tweet, media_data=None):
    if is_retweet(tweet):
        logger.info(f"Skipping retweet: {tweet['id']}")
        return None
    
    media_urls = []
    if 'attachments' in tweet and media_data and 'includes' in media_data and 'media' in media_data['includes']:
        media_keys = tweet['attachments']['media_keys']
        for media_key in media_keys:
            for media in media_data['includes']['media']:
                if media['media_key'] == media_key and media['type'] == 'photo':
                    media_urls.append({'type': 'photo', 'url': media['url']})
    
    return {
        'id': tweet['id'],
        'text': clean_tweet_text(tweet['text']),
        'media_urls': media_urls
    } if media_urls else None

def check_and_forward_tweets():
    logger.info(f"Checking for new media tweets from @{TWITTER_TARGET_USER}...")
    
    processed_tweets = load_processed_tweets()
    user_id = get_user_id(TWITTER_TARGET_USER)
    
    if not user_id:
        return 0
    
    tweets_data = get_recent_tweets(user_id)
    if not tweets_data or 'data' not in tweets_data:
        return 0
    
    new_tweets = []
    for tweet in tweets_data['data']:
        if tweet['id'] not in processed_tweets:
            processed_tweet = process_tweet(tweet, tweets_data)
            if processed_tweet:
                new_tweets.append(processed_tweet)
            processed_tweets.add(tweet['id'])
    
    for tweet in new_tweets:
        for i, media in enumerate(tweet['media_urls']):
            media_filename = f"/tmp/temp_{tweet['id']}_{i}.jpg"
            if download_media(media['url'], media_filename):
                caption = tweet['text'] if i == 0 else None
                if send_media_to_telegram(media_filename, caption=caption):
                    logger.info(f"Sent media for tweet: {tweet['id']}")
                try:
                    os.remove(media_filename)
                except:
                    pass
                time.sleep(1)
        time.sleep(2)
    
    save_processed_tweets(processed_tweets)
    logger.info(f"Processed {len(new_tweets)} new tweets")
    return len(new_tweets)

def main():
    logger.info(f"Starting bot for @{TWITTER_TARGET_USER}...")
    while True:
        check_and_forward_tweets()
        logger.info(f"Next check in {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
