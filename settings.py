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

try:
    from local_settings import *  # noqa: F403,F401
except ImportError:
    pass
