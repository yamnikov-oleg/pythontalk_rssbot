# -*- coding: utf-8 -*-
import hashlib
import logging
import sys
import time
from datetime import datetime
from typing import Optional, Union

import dateutil.parser
import feedparser
import redis
from schedule import Scheduler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.bot import Bot
from telegram.utils.request import Request

import settings

logging.basicConfig(
    format="%(asctime)s [%(name)s : %(levelname)s] %(message)s",
    level=logging.INFO)


def escape_html(s: str) -> str:
    return s.replace('<', '&lt;').replace('>', '&gt;')


class Storage:
    key_prefix = "rssbot"

    def __init__(self, host: str, port: int, db: int) -> None:
        self.rdb = redis.Redis(
            host=host,
            port=port,
            db=db,
        )

    def _hash_url(self, entry_url: str) -> str:
        sha = hashlib.sha256()
        sha.update(entry_url.encode())
        return sha.hexdigest()

    def set_entry_posted(self, entry_url: str, message_id: Union[int, str]) -> None:
        key = f"{self.key_prefix}:entry_message_id:{self._hash_url(entry_url)}"
        self.rdb.set(key, str(message_id))

    def get_entry_message_id(self, entry_url: str) -> Optional[str]:
        key = f"{self.key_prefix}:entry_message_id:{self._hash_url(entry_url)}"
        value = self.rdb.get(key)
        if value is not None:
            value = value.decode()
        return value

    def was_entry_posted_before(self, entry_url: str) -> bool:
        """
        Returns True if an entry with given url was posted in the group before.
        Used to deduplicate entries.
        """
        return bool(self.get_entry_message_id(entry_url))

    def clear_entry_data(self) -> int:
        """
        Remove all the information about posted entries.
        """
        keys = self.rdb.keys(f"{self.key_prefix}:entry_message_id:*")
        for key in keys:
            self.rdb.delete(key)
        return len(keys)

    def get_last_post_time(self) -> Optional[datetime]:
        """
        Gets datetime when last message was sent.
        """
        key = f"{self.key_prefix}:lastposttime"
        dt_formatted = self.rdb.get(key)
        if not dt_formatted:
            return None

        return dateutil.parser.parse(dt_formatted.decode('utf-8'))

    def set_last_post_time(self) -> None:
        """
        Sets datetime of last message to current time.
        """
        key = f"{self.key_prefix}:lastposttime"
        now = datetime.utcnow()
        dt_formatted = now.isoformat()
        self.rdb.set(key, dt_formatted)

    def clear_last_post_time(self) -> None:
        """
        Sets datetime of last message to current time.
        """
        key = f"{self.key_prefix}:lastposttime"
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

        self.first_update_at_hour = settings.FIRST_UPDATE_AT_HOUR
        self.update_every_hours = settings.UPDATE_EVERY_HOURS

        self.blacklist_words = settings.BLACKLIST_WORDS
        self.blacklist_urls = settings.BLACKLIST_URLS

        self.scheduler = Scheduler()
        self._setup_schedule()

    def _setup_schedule(self):
        logging.info("Setting up RSS bot schedule")

        hour = self.first_update_at_hour
        while hour < 24:
            time_str = f"{hour:02}:00"
            logging.info("Bot will run at %s", time_str)
            self.scheduler.every().day.at(time_str).do(self.update)
            hour += self.update_every_hours

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

        entries_collected = []
        for entry in feed["entries"]:
            title, url = entry["title"], entry["link"]
            if self.storage.was_entry_posted_before(url):
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
        text = (
            f"<b>[{self.feed_title}]</b>\n"
            f"<a href=\"{selected_url}\">{escape_html(selected_title)}</a>"
        )
        message = self.bot.send_message(
            chat_id=self.chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Открыть",
                            url=selected_url,
                        ),
                    ],
                ],
            ),
        )

        # Mark sent entries as posted
        logging.info('Message sent, marking the entry as posted')
        self.storage.set_entry_posted(selected_url, message.message_id)

    def run(self) -> None:
        logging.info("Starting RSS bot")
        while True:
            self.scheduler.run_pending()
            time.sleep(60)

    def clear(self) -> None:
        """
        Removes all info about posted entries from the storage.
        """
        removed = self.storage.clear_entry_data()
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
