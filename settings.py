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
    "Nobody expects the Spanish Inquisition! New on {}:",
    "Anybody else feel like a little giggle when I mention my fwiend... Biggus... Dickus? New on {}:",
    "He who is valiant and pure of spirit may find the Holy Grail in the Castle of aaarrrrggh. New on {}:",
    "Now, you listen here! He's not the Messiah. He's a very naughty boy! New on {}:",
    "Look, you stupid Bastard. You've got no arms left. - It’s just a flesh wound. New on {}:",
    "Please, this is supposed to be a happy occasion. Let’s not bicker and argue over who killed who. New on {}:",
    "I'm not the Messiah! Will you please listen? -- He is the Messiah! New on {}:",
    "Spam! Spam! Spam! Spam! Spam! Spam! New on {}:",
    "Apart from the sanitation, the medicine, education, wine, public order, irrigation, roads, the fresh water system, and public health... What have the Romans ever done for us? New on {}:",
    "Always look on the bright side of life. New on {}:",
    "And now for something completely different. New on {}:",
    "We interrupt this program to annoy you and make things generally more irritating. New on {}:",
    "He’s not the Messiah—he’s a very naughty boy! New on {}:",
    "It’s passed on! This parrot is no more! It has ceased to be! New on {}:",
    "It’s... {}:",
    "Are you suggesting that coconuts migrate? New on {}:",
    "We are the Knights who say... NI. New on {}:",
]

UPDATE_EVERY = timedelta(hours=8)

try:
    from local_settings import *  # noqa: F403,F401
except ImportError:
    pass
