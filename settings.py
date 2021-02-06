from datetime import timedelta

REDIS_HOST = 'redis'
REDIS_PORT = 6379
REDIS_DB = 0

FEED_TITLE = 'Planet Python'
FEED_URL = 'https://planetpython.org/rss20.xml'

BOT_TOKEN = ''
BOT_PROXY = ''
CHAT_ID = ''

UPDATE_EVERY = timedelta(hours=8)

# Titles with at least one of these words will be skipped.
# Each word is searched as a substring case-insensitively.
BLACKLIST_WORDS = []

# URLs starting with any of these URLs will be skipped.
BLACKLIST_URLS = []

try:
    from local_settings import *  # noqa: F403,F401
except ImportError:
    pass
