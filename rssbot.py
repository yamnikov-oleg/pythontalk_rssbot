# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import sys
from datetime import datetime
from typing import Optional, Tuple, Union, cast

import dateutil.parser
import feedparser
import redis
from schedule import Scheduler
from telegram import (CallbackQuery, InlineKeyboardButton,
                      InlineKeyboardMarkup, Update)
from telegram.bot import Bot
from telegram.ext import CallbackQueryHandler, Updater
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

    def _hash_url(self, url: str) -> str:
        sha = hashlib.sha256()
        sha.update(url.encode())
        return sha.hexdigest()

    def set_entry_posted(self, url: str, message_id: Union[int, str], message_text: str) -> None:
        entry_data = {
            "url": url,
            "message_id": message_id,
            "message_text": message_text,
        }
        entry_data_json = json.dumps(entry_data)

        entry_url_key = f"{self.key_prefix}:entry_by_url:{self._hash_url(url)}"
        self.rdb.set(entry_url_key, entry_data_json)

        message_id_key = f"{self.key_prefix}:entry_by_message_id:{message_id}"
        self.rdb.set(message_id_key, entry_data_json)

    def get_entry_data_by_url(self, url: str) -> Optional[dict]:
        key = f"{self.key_prefix}:entry_by_url:{self._hash_url(url)}"
        value = self.rdb.get(key)
        if value is not None:
            value = json.loads(value)
        return value

    def get_entry_data_by_message_id(self, message_id: Union[int, str]) -> None:
        key = f"{self.key_prefix}:entry_by_message_id:{message_id}"
        value = self.rdb.get(key)
        if value is not None:
            value = json.loads(value)
        return value

    def was_entry_posted_before(self, url: str) -> bool:
        """
        Returns True if an entry with given url was posted in the group before.
        Used to deduplicate entries.
        """
        return bool(self.get_entry_data_by_url(url))

    def get_entry_likes_dislikes(self, url: str) -> Tuple[int, int]:
        likes_key = f"{self.key_prefix}:entry_user_likes:{self._hash_url(url)}"
        likes = self.rdb.scard(likes_key)

        dislikes_key = f"{self.key_prefix}:entry_user_dislikes:{self._hash_url(url)}"
        dislikes = self.rdb.scard(dislikes_key)

        return likes, dislikes

    def toggle_entry_liked(self, url: str, user_id: Union[str, int]) -> None:
        likes_key = f"{self.key_prefix}:entry_user_likes:{self._hash_url(url)}"
        dislikes_key = f"{self.key_prefix}:entry_user_dislikes:{self._hash_url(url)}"

        # It's important that operations in both cases are atomic.
        if self.rdb.sismember(likes_key, user_id):
            self.rdb.srem(likes_key, user_id)
        else:
            with self.rdb.pipeline() as p:
                p.srem(dislikes_key, user_id)
                p.sadd(likes_key, user_id)
                p.execute()

    def toggle_entry_disliked(self, url: str, user_id: Union[str, int]) -> None:
        likes_key = f"{self.key_prefix}:entry_user_likes:{self._hash_url(url)}"
        dislikes_key = f"{self.key_prefix}:entry_user_dislikes:{self._hash_url(url)}"

        # It's important that operations in both cases are atomic.
        if self.rdb.sismember(dislikes_key, user_id):
            self.rdb.srem(dislikes_key, user_id)
        else:
            with self.rdb.pipeline() as p:
                p.srem(likes_key, user_id)
                p.sadd(dislikes_key, user_id)
                p.execute()

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
        self.updater = Updater(bot=self.bot)

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
                    [
                        InlineKeyboardButton(
                            "👍 0",
                            callback_data="like",
                        ),
                        InlineKeyboardButton(
                            "👎 0",
                            callback_data="dislike",
                        ),
                    ],
                ],
            ),
        )

        # Mark sent entries as posted
        logging.info('Message sent, marking the entry as posted')
        self.storage.set_entry_posted(
            url=selected_url,
            message_id=message.message_id,
            message_text=text,
        )

    def update_entry_message(self, entry_data: dict) -> None:
        likes, dislikes = self.storage.get_entry_likes_dislikes(entry_data["url"])
        self.bot.edit_message_reply_markup(
            chat_id=self.chat_id,
            message_id=entry_data["message_id"],
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Открыть",
                            url=entry_data["url"],
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            f"👍 {likes}",
                            callback_data="like",
                        ),
                        InlineKeyboardButton(
                            f"👎 {dislikes}",
                            callback_data="dislike",
                        ),
                    ],
                ],
            ),
        )

    def handle_like(self, bot: Bot, update: Update) -> None:
        update.callback_query.answer()

        query = cast(CallbackQuery, update.callback_query)
        entry_data = self.storage.get_entry_data_by_message_id(query.message.message_id)
        if not entry_data:
            logging.info(
                'Like query from user \"%s %s\" (id %s) for unknown post (message id %s)',
                query.from_user.first_name,
                query.from_user.last_name,
                query.from_user.id,
                query.message.message_id,
            )
            return

        logging.info(
            'Like query from user \"%s %s\" (id %s) for post \"%s\" (message id %s)',
            query.from_user.first_name,
            query.from_user.last_name,
            query.from_user.id,
            entry_data["url"],
            query.message.message_id,
        )

        self.storage.toggle_entry_liked(entry_data["url"], query.from_user.id)
        self.update_entry_message(entry_data)

    def handle_dislike(self, bot: Bot, update: Update) -> None:
        update.callback_query.answer()

        query = cast(CallbackQuery, update.callback_query)
        entry_data = self.storage.get_entry_data_by_message_id(query.message.message_id)
        if not entry_data:
            logging.info(
                'Dislike query from user \"%s %s\" (id %s) for unknown post (message id %s)',
                query.from_user.first_name,
                query.from_user.last_name,
                query.from_user.id,
                query.message.message_id,
            )
            return

        logging.info(
            'Dislike query from user \"%s %s\" (id %s) for post \"%s\" (message id %s)',
            query.from_user.first_name,
            query.from_user.last_name,
            query.from_user.id,
            entry_data["url"],
            query.message.message_id,
        )

        self.storage.toggle_entry_disliked(entry_data["url"], query.from_user.id)
        self.update_entry_message(entry_data)

    def run(self) -> None:
        logging.info("Starting RSS bot")

        self.updater.dispatcher.add_handler(CallbackQueryHandler(self.handle_like, pattern="like"))
        self.updater.dispatcher.add_handler(CallbackQueryHandler(self.handle_dislike, pattern="dislike"))
        self.updater.job_queue.run_repeating(lambda bot, job: self.scheduler.run_pending(), interval=60)
        self.updater.start_polling()
        self.updater.idle()

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
