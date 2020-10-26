from datetime import timedelta

REDIS_HOST = 'redis'
REDIS_PORT = 6379
REDIS_DB = 0

FEED_TITLE = 'r/python'
FEED_URL = 'https://www.reddit.com/r/python/.rss'

BOT_TOKEN = ''
BOT_PROXY = ''
CHAT_ID = ''

UPDATE_EVERY = timedelta(hours=8)

# Titles with at least one of these words will be skipped.
# Each word is searched as a substring case-insensitively.
BLACKLIST_WORDS = []

try:
    from local_settings import *  # noqa: F403,F401
except ImportError:
    pass
