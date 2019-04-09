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
    "Take a break, you earned it. New on {}:",
    "You look stunning today. New on {}:",
    "Do you like sweets? Treat yourself with a dessert today. New on {}:",
    "How's the weather today? Good enough for a walk? New on {}:",
    "Pause, take a deep breath. Let your shoulders drop. New on {}:",
    "Have you been drinking enough water? New on {}:",
    "Are sleeping enough? Don't deny yourself a quality rest. New on {}:",
    "It's never a bad time to listen to your favorite music. New on {}:",
    "Put a smile on that pretty face! New on {}:",
    "Don't be too hard on yourself. One small step at a time. New on {}:",
    "A good meal can make one's day. New on {}:",
    "There are no bad days without good days coming after. New on {}:",
]

UPDATE_EVERY = timedelta(hours=8)

try:
    from local_settings import *  # noqa: F403,F401
except ImportError:
    pass
