# -*- coding: utf-8 -*-
import logging
import random
import sys
import time
from datetime import datetime
from typing import Optional

import dateutil.parser
import feedparser
import redis
from telegram.bot import Bot
from telegram.utils.request import Request

import settings

logging.basicConfig(
    format="%(asctime)s [%(name)s : %(levelname)s] %(message)s",
    level=logging.INFO)


def escape_html(s: str) -> str:
    return s.replace('<', '&lt;').replace('>', '&gt;')


class Storage:
    def __init__(self, host: str, port: int, db: int) -> None:
        self.rdb = redis.Redis(
            host=host,
            port=port,
            db=db,
        )

    def was_posted_before(self, entry_url: str) -> bool:
        """
        Returns True if an entry with given url was posted in the group before.
        Used to deduplicate entries.
        """
        key = f"pythontalk_rssbot_entry[{entry_url}]"
        value = self.rdb.get(key)
        return bool(value)

    def set_posted(self, entry_url: str) -> None:
        """
        Marks entry with the given url as posted.
        """
        key = f"pythontalk_rssbot_entry[{entry_url}]"
        self.rdb.set(key, b'1')

    def clear_posted(self) -> int:
        """
        Remove all the information about posted entries.
        """
        keys = self.rdb.keys("pythontalk_rssbot_entry*")
        for key in keys:
            self.rdb.delete(key)
        return len(keys)

    def get_last_post_time(self) -> Optional[datetime]:
        """
        Gets datetime when last message was sent.
        """
        key = "pythontalk_rssbot_lastposttime"
        dt_formatted = self.rdb.get(key)
        if not dt_formatted:
            return None

        return dateutil.parser.parse(dt_formatted.decode('utf-8'))

    def set_last_post_time(self) -> None:
        """
        Sets datetime of last message to current time.
        """
        key = "pythontalk_rssbot_lastposttime"
        now = datetime.utcnow()
        dt_formatted = now.isoformat()
        self.rdb.set(key, dt_formatted)

    def clear_last_post_time(self) -> None:
        """
        Sets datetime of last message to current time.
        """
        key = "pythontalk_rssbot_lastposttime"
        self.rdb.delete(key)


class RssBot:
    def __init__(self):
        self.storage = Storage(
            settings.REDIS_HOST,
            settings.REDIS_PORT,
            settings.REDIS_DB,
        )

        self.feed_title = settings.FEED_TITLE
        self.feed_url = settings.FEED_URL

        if settings.BOT_PROXY:
            req = Request(proxy_url=settings.BOT_PROXY)
            self.bot = Bot(settings.BOT_TOKEN, request=req)
        else:
            self.bot = Bot(settings.BOT_TOKEN)

        self.chat_id = settings.CHAT_ID

        self.update_every = settings.UPDATE_EVERY

        self.blacklist_words = settings.BLACKLIST_WORDS
        self.blacklist_urls = settings.BLACKLIST_URLS

    def contains_blacklisted_words(self, title):
        title_lower = title.lower()
        for word in self.blacklist_words:
            if word.lower() in title_lower:
                return True

        return False

    def is_blacklisted_url(self, url):
        for blacklisted_url in self.blacklist_urls:
            if url.startswith(blacklisted_url):
                return True

        return False

    def update(self):
        """
        Parses the feed and posts new links in the group.
        """

        logging.info("Started feed update")

        # Collect the entries to post
        feed = feedparser.parse(self.feed_url)
        logging.info(
            f'Received {len(feed["entries"])} entries from {self.feed_url}')

        entries_collected = []  # type: List[Tuple[str, str]]
        for entry in feed["entries"]:
            title, url = entry["title"], entry["link"]
            if self.storage.was_posted_before(url):
                continue

            if self.contains_blacklisted_words(title):
                logging.info("Title \"%s\" contains blacklisted words, skipping", title)
                continue

            if self.is_blacklisted_url(url):
                logging.info("URL \"%s\" is blacklisted, skipping", url)
                continue

            entries_collected.append((title, url))

        logging.info(f'Collected {len(entries_collected)} entries to post')

        # No entries - no message
        if len(entries_collected) == 0:
            return

        selected_title, selected_url = entries_collected[0]
        logging.info(f'Posting entry: {selected_url}')

        # Format and send the message
        message = f"<a href=\"{selected_url}\">{escape_html(selected_title)}</a>"
        self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode="HTML",
        )

        # Mark sent entries as posted
        logging.info(f'Message sent, marking the entry as posted')
        self.storage.set_posted(selected_url)

    def run(self) -> None:
        logging.info("Starting RSS bot")
        while True:
            last_time = self.storage.get_last_post_time()
            if last_time:
                now = datetime.utcnow()
                delta = now - last_time
                logging.info(f"Time since last post: {delta}")
            else:
                delta = None
                logging.info(f"Post was never made yet")

            if not delta or delta >= self.update_every:
                self.update()
                self.storage.set_last_post_time()

            time.sleep((self.update_every / 50).total_seconds())

    def clear(self) -> None:
        """
        Removes all info about posted entries from the storage.
        """
        removed = self.storage.clear_posted()
        self.storage.clear_last_post_time()
        logging.info(f"Removed {removed} entries")


if __name__ == "__main__":
    rss_bot = RssBot()
    if len(sys.argv) == 1:
        rss_bot.run()
    elif sys.argv[1] == 'clear':
        rss_bot.clear()
    else:
        raise RuntimeError(sys.argv[1])
