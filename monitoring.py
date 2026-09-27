"""Own watcher tasks and persist their Telegram delivery state across restarts."""

import asyncio
from types import SimpleNamespace

from telegram import InlineKeyboardMarkup
from telegram.error import BadRequest, Forbidden, RetryAfter


class WatchStopped(Exception):
    """Delivery is permanently forbidden; the polling loop must stop."""


def retry_delay(error, interval, failures):
    if isinstance(error, RetryAfter):
        seconds = error.retry_after
        return seconds.total_seconds() if hasattr(seconds, "total_seconds") else seconds
    return min(max(1, interval) * 2 ** min(failures - 1, 9), 300)


class DurableDelivery:
    """Telegram interface used only by one existing torrent polling loop."""

    def __init__(self, manager, row):
        self.manager = manager
        self.key = (row["chat_id"], row["torrent_hash"])
        self.message_id = row["message_id"]

    async def edit_message_text(self, *, chat_id, message_id, text, reply_markup=None):
        m = self.manager
        try:
            if self.message_id is not None:
                try:
                    await m.telegram.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.message_id,
                        text=text,
                        reply_markup=reply_markup,
                    )
                    return
                except BadRequest as error:
                    reason = str(error).lower()
                    if "message is not modified" in reason:
                        return
                    if not any(
                        term in reason
                        for term in ("message to edit not found", "message can't be edited")
                    ):
                        raise
            message = await m.telegram.send_message(
                chat_id=chat_id, text=text, reply_markup=reply_markup
            )
            m.store.set_message(*self.key, message.message_id)
            self.message_id = message.message_id
        except Forbidden:
            m.store.set_status(*self.key, "blocked")
            raise WatchStopped() from None
        except RetryAfter as error:
            # The polling loop retries edits. Respect Telegram's requested delay first.
            await asyncio.sleep(retry_delay(error, m.api.WATCH_INTERVAL_SEC, 1))
            raise

    async def send_message(self, chat_id, text, reply_markup=None):
        # Older pending notices may still contain the retired Plex launcher.
        text = text.removesuffix(
            "\n\n📺 Наличие файла в Plex не проверено. Папка загрузки должна быть подключена к медиатеке."
        )
        if reply_markup:
            rows = [
                [button for button in row if button.url != "https://app.plex.tv/desktop"]
                for row in reply_markup.inline_keyboard
            ]
            rows = [row for row in rows if row]
            reply_markup = InlineKeyboardMarkup(rows) if rows else None
        m = self.manager
        m.store.pending(*self.key, text, reply_markup.to_dict() if reply_markup else None)
        try:
            await m.telegram.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        except Forbidden:
            m.store.set_status(*self.key, "blocked")
            raise WatchStopped() from None
        m.store.set_status(*self.key, "completed")


class WatchManager:
    def __init__(self, api, telegram, store):
        self.api, self.telegram, self.store = api, telegram, store
        self.tasks = {}
        self.closed = False

    def start(self, row):
        key = (row["chat_id"], row["torrent_hash"])
        task = asyncio.create_task(self.run(key))
        self.tasks[key] = task

        def finished(done):
            if self.tasks.get(key) is done:
                self.tasks.pop(key, None)
            if not done.cancelled() and done.exception():
                print("WATCH ERROR:", type(done.exception()).__name__)

        task.add_done_callback(finished)

    async def restore(self):
        for row in self.store.unfinished():
            key = (row["chat_id"], row["torrent_hash"])
            if row["user_id"] not in self.api.ALLOWED_USERS:
                self.store.set_status(*key, "revoked")
            elif key not in self.tasks:
                if row["status"] == "error":
                    self.store.set_status(*key, "active")
                self.start(row)

    async def subscribe(self, user_id, chat_id, torrent_hash, title):
        if self.closed:
            raise RuntimeError("Monitoring is shutting down")
        if user_id not in self.api.ALLOWED_USERS:
            raise PermissionError("Subscription owner is not allowed")
        key = (chat_id, torrent_hash)
        # Repeated selection must not reset a pending notification or spawn a second task.
        row = self.store.get(*key)
        if row and row["status"] in ("active", "pending"):
            if key not in self.tasks:
                self.start(row)
            return
        self.store.subscribe(user_id, chat_id, torrent_hash, title)
        self.start(self.store.get(*key))

    async def run(self, key):
        failures = 0
        while True:
            row = self.store.get(*key)
            if row["user_id"] not in self.api.ALLOWED_USERS:
                self.store.set_status(*key, "revoked")
                return
            delivery = DurableDelivery(self, row)
            try:
                if row["status"] == "pending":
                    markup = self.store.pending_markup(*key)
                    await delivery.send_message(
                        key[0],
                        row["notice"],
                        reply_markup=InlineKeyboardMarkup.de_json(markup, self.telegram)
                        if markup
                        else None,
                    )
                else:
                    status = await self.api.watch_torrent_until_done(
                        key[0],
                        key[1],
                        row["title"],
                        row["message_id"],
                        SimpleNamespace(bot=delivery, user_id=row["user_id"]),
                    )
                    if status in ("missing", "error"):
                        self.store.set_status(*key, status)
                return
            except WatchStopped:
                return
            except Exception as error:
                # Cancellation propagates. Logs never include URLs or credentials.
                print("WATCH RETRY:", type(error).__name__)
                failures += 1
                await asyncio.sleep(retry_delay(error, self.api.WATCH_INTERVAL_SEC, failures))

    async def removed(self, torrent_hash):
        """Retire watches after confirmed removal, including undelivered notices."""
        for row in self.store.unfinished():
            if row["torrent_hash"] != torrent_hash:
                continue
            key = (row["chat_id"], torrent_hash)
            task = self.tasks.pop(key, None)
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            self.store.set_status(*key, "missing")

    async def stop(self):
        self.closed = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()

    async def close(self):
        await self.stop()
        self.store.close()


class SearchJobs:
    """Bound slow work per user without blocking the sequential control handlers."""

    def __init__(self):
        self.tasks = {}
        self.closed = False

    def busy(self, user_id):
        task = self.tasks.get(user_id)
        return self.closed or (task is not None and not task.done())

    async def unavailable(self, update):
        query = update.callback_query
        if query:
            await query.answer()
        message = query.message if query else update.message
        await message.reply_text(
            "⏳ Дождись завершения текущего поиска или добавления. "
            "Загрузки и их управление доступны через /downloads."
            if not self.closed
            else "Бот перезапускается. Попробуй ещё раз через минуту."
        )

    async def start(self, update, context, callback):
        user = update.effective_user.id
        if self.busy(user):
            await self.unavailable(update)
            return

        async def run():
            try:
                await callback(update, context)
            except Exception as error:
                print("SEARCH JOB ERROR:", type(error).__name__)
                message = update.callback_query.message if update.callback_query else update.message
                try:
                    await message.reply_text(
                        "Не удалось завершить запрос. Если добавлял торрент, сначала проверь /downloads."
                    )
                except Exception as delivery_error:
                    print("SEARCH JOB NOTICE ERROR:", type(delivery_error).__name__)
            finally:
                if self.tasks.get(user) is asyncio.current_task():
                    self.tasks.pop(user, None)

        self.tasks[user] = asyncio.create_task(run())

    async def stop(self):
        self.closed = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
