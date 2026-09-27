"""Hourly service snapshots and durable, opt-in Telegram health cards."""

import asyncio
import re
import secrets
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, Forbidden, TelegramError

INTERVAL = 3600
CACHE_SECONDS = 30


def check_jackett(url, key):
    # Capabilities authenticate the configured API without searching any indexer.
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in {"t", "q", "apikey"}]
    response = requests.get(
        urlunsplit(parts._replace(query=urlencode(query), fragment="")),
        params={"apikey": key, "t": "caps"},
        timeout=(5, 10),
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    if root.tag != "caps" or root.find("searching") is None:
        raise ValueError("Invalid capabilities response")


def check_qbit(session, url):
    response = session().get(f"{url}/api/v2/app/version", timeout=(5, 10))
    response.raise_for_status()
    if not re.fullmatch(r"v?\d+\.\d+(?:\.[\w.-]+)?", response.text.strip()):
        raise ValueError("Invalid version response")


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class HealthManager:
    def __init__(self, api, telegram, path):
        self.api, self.telegram = api, telegram
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(path)
        path.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS cards (
            user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL, token TEXT NOT NULL,
            PRIMARY KEY(user_id, chat_id))""")
        self.db.commit()
        self.lock = asyncio.Lock()
        self.task = None
        self.closed = False
        self.snapshot = None
        self.checked_at = None
        self.cache_until = 0

    def start(self):
        if self.task is None and not self.closed:
            self.task = asyncio.create_task(self.run())

    async def run(self):
        while True:
            try:
                await self.cycle()
            except Exception as error:
                print("HEALTH ERROR:", type(error).__name__)
            await asyncio.sleep(INTERVAL)

    async def stop(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None

    async def close(self):
        await self.stop()
        if not self.closed:
            self.closed = True
            self.db.close()

    def row(self, user, chat):
        return self.db.execute(
            "SELECT * FROM cards WHERE user_id=? AND chat_id=?", (user, chat)
        ).fetchone()

    def forget(self, row):
        with self.db:
            self.db.execute(
                "DELETE FROM cards WHERE user_id=? AND chat_id=?", (row["user_id"], row["chat_id"])
            )

    async def sample(self, *, force=False):
        if not force and self.snapshot is not None and time.monotonic() < self.cache_until:
            return

        async def probe(function):
            try:
                await asyncio.to_thread(function)
                return "🟢", "доступен"
            except requests.Timeout:
                return "🟡", "не ответил вовремя"
            except Exception:
                return "🔴", "недоступен"

        self.snapshot = await asyncio.gather(
            probe(self.api.check_qbit), probe(self.api.check_jackett)
        )
        self.checked_at = time.time()
        self.cache_until = time.monotonic() + CACHE_SECONDS

    def text(self):
        lines = ["🩺 Состояние системы", "", "🟢 Бот — работает"]
        for label, (icon, status) in zip(("qBittorrent", "Jackett"), self.snapshot):
            lines.append(f"{icon} {label} — {status}")
        lines.extend(["", f"🕒 Проверено: {timestamp(self.checked_at)}", "Обновляется каждый час."])
        search = self.api.last_search()
        if search:
            if search.get("failed"):
                result = "не завершился — попробуй повторить поиск"
            elif search.get("total"):
                result = f"ответили {search['responded']} из {search['total']} источников"
            else:
                result = "состояние источников неизвестно"
            lines.extend(["", f"🔎 Последний поиск ({timestamp(search['time'])}): {result}."])
        else:
            lines.extend(["", "⚪ Источники поиска ещё не проверялись после запуска бота."])
        lines.extend(
            [
                "Источники не проверяются ежечасно — их статус берётся из последнего поиска.",
                "",
                "Если время проверки не меняется больше часа, данные могли устареть.",
                "Доступность сервисов не гарантирует скорость или наличие раздачи.",
            ]
        )
        return "\n".join(lines)

    def markup(self, token):
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔄 Проверить", callback_data=f"health:{token}:refresh"),
                    InlineKeyboardButton("📌 Закрепить", callback_data=f"health:{token}:pin"),
                ],
                [InlineKeyboardButton("📥 Загрузки", callback_data="nav:downloads")],
            ]
        )

    async def edit(self, row):
        try:
            await self.telegram.edit_message_text(
                chat_id=row["chat_id"],
                message_id=row["message_id"],
                text=self.text(),
                reply_markup=self.markup(row["token"]),
                parse_mode=None,
            )
            return True
        except Forbidden:
            self.forget(row)
            return False
        except BadRequest as error:
            reason = str(error).lower()
            if "message is not modified" in reason:
                return True
            if any(
                term in reason for term in ("message to edit not found", "message can't be edited")
            ):
                self.forget(row)
                return False
            raise

    async def open(self, update):
        if not self.api.allowed(update):
            return
        async with self.lock:
            user, chat = update.effective_user.id, update.effective_chat.id
            await self.sample()
            row = self.row(user, chat)
            if row and await self.edit(row):
                return
            token = secrets.token_hex(8)
            message = await update.message.reply_text(
                self.text(),
                reply_markup=self.markup(token),
                parse_mode=None,
            )
            with self.db:
                self.db.execute(
                    "INSERT OR REPLACE INTO cards VALUES (?, ?, ?, ?)",
                    (user, chat, message.message_id, token),
                )

    def callback_row(self, update):
        query = update.callback_query
        row = self.row(update.effective_user.id, update.effective_chat.id)
        if (
            row
            and self.api.allowed(update)
            and row["message_id"] == getattr(query.message, "message_id", None)
            and query.data in {f"health:{row['token']}:refresh", f"health:{row['token']}:pin"}
        ):
            return row
        return None

    async def callback(self, update):
        query = update.callback_query
        if not self.api.allowed(update):
            await query.answer("Нет доступа.", show_alert=True)
            return
        if self.callback_row(update) is None:
            await query.answer(
                "Карточка устарела или принадлежит другому пользователю. Открой /health.",
                show_alert=True,
            )
            return
        # A slow hourly probe must not delay Telegram's short acknowledgement window.
        await query.answer()
        async with self.lock:
            row = self.callback_row(update)
            if row is None:
                await query.message.reply_text("Карточка недоступна. Открой /health заново.")
                return
            try:
                if query.data.endswith(":pin"):
                    await self.telegram.pin_chat_message(
                        chat_id=row["chat_id"],
                        message_id=row["message_id"],
                        disable_notification=True,
                    )
                else:
                    await self.sample()
                    if not await self.edit(row):
                        await query.message.reply_text(
                            "Карточка недоступна. Открой /health заново."
                        )
            except TelegramError:
                await query.message.reply_text(
                    "Не удалось закрепить карточку. Проверь права бота или закрепи её вручную."
                    if query.data.endswith(":pin")
                    else "Не удалось обновить карточку. Попробуй /health позже."
                )

    async def cycle(self):
        async with self.lock:
            rows = list(self.db.execute("SELECT * FROM cards"))
            active = []
            for row in rows:
                if row["user_id"] not in self.api.ALLOWED_USERS:
                    self.forget(row)
                else:
                    active.append(row)
            if not active:
                return
            await self.sample(force=True)
            for row in active:
                try:
                    await self.edit(row)
                except TelegramError as error:
                    # Keep the card for the next hourly attempt; never log raw responses.
                    print("HEALTH DELIVERY ERROR:", type(error).__name__)
