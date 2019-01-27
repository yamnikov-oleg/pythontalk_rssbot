from datetime import timedelta

REDIS_HOST = 'redis'
REDIS_PORT = 6379
REDIS_DB = 0

FEED_TITLE = 'r/python'
FEED_URL = 'https://www.reddit.com/r/python/.rss'
ENTRIES_PER_POST = 5

BOT_TOKEN = ''
BOT_PROXY = ''
CHAT_ID = ''
HEADERS = [
    "So hot right now in {}:",
    "Why so gloomy? Here're some links from {}:",
    "Omg, breaking news from {}:",
    "Cheer up, feed your brain with {}:",
    "Time to procrastinate with {}:",
    "Stop whatever you're doing, look at this ({}):",
]

UPDATE_EVERY = timedelta(hours=8)

try:
    from local_settings import *  # noqa: F403,F401
except ImportError:
    pass
