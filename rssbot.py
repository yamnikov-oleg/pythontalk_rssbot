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


class RssBot:
    def __init__(self):
        self.storage = Storage(
            settings.REDIS_HOST,
            settings.REDIS_PORT,
            settings.REDIS_DB,
        )

        self.feed_title = settings.FEED_TITLE
        self.feed_url = settings.FEED_URL
        self.entries_per_post = settings.ENTRIES_PER_POST

        if settings.BOT_PROXY:
            req = Request(proxy_url=settings.BOT_PROXY)
            self.bot = Bot(settings.BOT_TOKEN, request=req)
        else:
            self.bot = Bot(settings.BOT_TOKEN)

        self.chat_id = settings.CHAT_ID
        self.headers = settings.HEADERS

        self.update_every = settings.UPDATE_EVERY

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

            entries_collected.append((title, url))
            if len(entries_collected) >= self.entries_per_post:
                break

        logging.info(f'Collected {len(entries_collected)} entries to post')

        # No entries - no message
        if len(entries_collected) == 0:
            return

        # Format and send the message
        header = random.choice(self.headers).format(self.feed_title)
        entries_formatted = []  # List[str]
        for title, url in entries_collected:
            entries_formatted.append(
                f"→ <a href=\"{url}\">{escape_html(title)}</a>")

        message = "\n".join([header, *entries_formatted])
        self.bot.send_message(
            chat_id=self.chat_id,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        # Mark sent entries as posted
        logging.info(f'Message sent, marking entries as posted')
        for _, url in entries_collected:
            self.storage.set_posted(url)

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

            time.sleep((self.update_every / 10).total_seconds())

    def clear(self) -> None:
        """
        Removes all info about posted entries from the storage.
        """
        removed = self.storage.clear_posted()
        logging.info(f"Removed {removed} entries")


if __name__ == "__main__":
    rss_bot = RssBot()
    if len(sys.argv) == 1:
        rss_bot.run()
    elif sys.argv[1] == 'clear':
        rss_bot.clear()
    else:
        raise RuntimeError(sys.argv[1])
