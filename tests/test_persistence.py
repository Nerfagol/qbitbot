import asyncio
import importlib
from functools import wraps
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest, Forbidden, NetworkError

from tests.helpers import torrent


def async_test(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return run


def modules():
    return importlib.import_module("watch_store"), importlib.import_module("monitoring")


def manager(bot, tmp_path, telegram=None):
    bot.language_for_user = getattr(bot, "language_for_user", lambda user: "ru")
    storage, monitoring = modules()
    store = storage.WatchStore(tmp_path / "state" / "watches.sqlite3")
    telegram = telegram or SimpleNamespace(
        edit_message_text=AsyncMock(),
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=99)),
    )
    return monitoring.WatchManager(bot, telegram, store), telegram


@async_test
@pytest.mark.parametrize("deleted", [False, True])
async def test_durable_progress_preserves_recovery_navigation(bot, tmp_path, deleted):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    _, monitoring = modules()
    m, telegram = manager(bot, tmp_path)
    m.store.subscribe(101, 303, "a" * 40, "Test")
    m.store.set_message(303, "a" * 40, 77)
    if deleted:
        telegram.edit_message_text.side_effect = BadRequest("Message to edit not found")
    delivery = monitoring.DurableDelivery(m, m.store.get(303, "a" * 40))
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Загрузки", callback_data="nav:downloads")]]
    )
    await delivery.edit_message_text(
        chat_id=303, message_id=77, text="Waiting", reply_markup=markup
    )
    call = telegram.send_message.call_args if deleted else telegram.edit_message_text.call_args
    assert call.kwargs["reply_markup"] == markup
    assert m.store.get(303, "a" * 40)["status"] == "active"
    await m.close()


def test_store_survives_reopen_and_filters_terminal(tmp_path):
    storage, _ = modules()
    path = tmp_path / "state" / "watches.sqlite3"
    store = storage.WatchStore(path)
    store.subscribe(101, 303, "a" * 40, "Example")
    store.set_message(303, "a" * 40, 12)
    store.subscribe(202, 404, "b" * 40, "Other")
    store.set_status(404, "b" * 40, "completed")
    store.close()
    reopened = storage.WatchStore(path)
    assert len(reopened.unfinished()) == 1
    row = reopened.unfinished()[0]
    assert (row["user_id"], row["chat_id"], row["message_id"]) == (101, 303, 12)
    assert path.stat().st_mode & 0o777 == 0o600
    reopened.close()


def test_future_schema_rejected(tmp_path):
    storage, _ = modules()
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(RuntimeError, match="schema"):
        storage.WatchStore(path)


@async_test
async def test_recovery_completion_and_no_repeat(bot, tmp_path, monkeypatch):
    m, telegram = manager(bot, tmp_path)
    m.store.subscribe(101, 303, "a" * 40, "Example")
    m.store.close()
    m, telegram = manager(bot, tmp_path, telegram)
    monkeypatch.setattr(
        bot,
        "qbit_torrents_info_sync",
        lambda **kw: [torrent(state="stalledUP", amount_left=0, progress=1.0)],
    )
    await m.restore()
    await asyncio.gather(*m.tasks.values())
    assert m.store.unfinished() == []
    notices = [
        call
        for call in telegram.send_message.call_args_list
        if str(call.kwargs.get("text", "")).startswith("Скачивание завершено:")
    ]
    assert len(notices) == 1
    await m.close()
    m, _ = manager(bot, tmp_path, telegram)
    await m.restore()
    assert not m.tasks
    assert telegram.send_message.call_count == 2  # progress card plus completion
    await m.close()


@async_test
async def test_pending_notice_retried_without_qbit(bot, tmp_path, monkeypatch):
    m, telegram = manager(bot, tmp_path)
    m.store.subscribe(101, 303, "a" * 40, "Example")
    m.store.pending(303, "a" * 40, "Saved completion")
    telegram.send_message.side_effect = [NetworkError("private URL"), SimpleNamespace(message_id=8)]
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: pytest.fail("No API needed"))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    await m.restore()
    await asyncio.gather(*m.tasks.values())
    assert telegram.send_message.call_count == 2
    assert m.store.unfinished() == []
    await m.close()


@async_test
@pytest.mark.parametrize("revoked", [False, True])
async def test_blocked_or_revoked_owner_stops(bot, tmp_path, monkeypatch, revoked):
    m, telegram = manager(bot, tmp_path)
    m.store.subscribe(999 if revoked else 101, 303, "a" * 40, "Example")
    m.store.pending(303, "a" * 40, "Saved completion")
    telegram.send_message.side_effect = Forbidden("blocked")
    await m.restore()
    await asyncio.gather(*m.tasks.values())
    assert m.store.unfinished() == []
    assert telegram.send_message.call_count == (0 if revoked else 1)
    await m.close()


@async_test
async def test_deleted_progress_card_replaced(bot, tmp_path, monkeypatch):
    m, telegram = manager(bot, tmp_path)
    m.store.subscribe(101, 303, "a" * 40, "Example")
    m.store.set_message(303, "a" * 40, 12)
    telegram.edit_message_text.side_effect = BadRequest("Message to edit not found")
    monkeypatch.setattr(
        bot,
        "qbit_torrents_info_sync",
        lambda **kw: [torrent(state="stalledUP", amount_left=0, progress=1.0)],
    )
    await m.restore()
    await asyncio.gather(*m.tasks.values())
    assert m.store.get(303, "a" * 40)["message_id"] == 99
    assert telegram.send_message.call_count == 2
    await m.close()


@async_test
async def test_subscription_committed_before_send_and_shutdown_retains_it(
    bot, tmp_path, monkeypatch
):
    m, telegram = manager(bot, tmp_path)
    started = asyncio.Event()

    async def hold(**kwargs):
        assert len(m.store.unfinished()) == 1
        started.set()
        await asyncio.Event().wait()

    telegram.send_message.side_effect = hold
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [torrent()])
    await m.subscribe(101, 303, "a" * 40, "Example")
    await started.wait()
    await m.close()
    m, _ = manager(bot, tmp_path)
    assert len(m.store.unfinished()) == 1
    assert m.store.unfinished()[0]["message_id"] is None
    await m.close()


@async_test
async def test_selection_registers_new_and_existing_incomplete(bot, monkeypatch):
    from tests.helpers import Message, context, update

    for duplicate in (False, True):
        ctx = context()
        subscription = AsyncMock()
        ctx.application.bot_data["monitoring"] = SimpleNamespace(subscribe=subscription)
        monkeypatch.setattr(
            bot,
            "jackett_search_sync",
            lambda *args: [{"title": "Example", "url": "magnet:?xt=urn:btih:" + "a" * 40}],
        )
        request = Message("Example")
        await bot.on_text(update(request), ctx)
        message = request.replies[-1]
        await bot.on_pick(update(message, message.markup.inline_keyboard[0][0].callback_data), ctx)
        monkeypatch.setattr(
            bot,
            "qbit_add_and_confirm",
            AsyncMock(
                return_value={
                    "ok": not duplicate,
                    "already_exists": duplicate,
                    "hash": "a" * 40,
                    "info": torrent(),
                }
            ),
        )
        await bot.on_pick(update(message, message.markup.inline_keyboard[0][0].callback_data), ctx)
        subscription.assert_awaited_once_with(101, 303, "a" * 40, "Test download")


@async_test
async def test_lifecycle_restores_then_cancels_and_closes(bot, tmp_path, monkeypatch):
    storage, _ = modules()
    path = tmp_path / "hooks.sqlite3"
    store = storage.WatchStore(path)
    store.subscribe(101, 303, "a" * 40, "Example")
    store.close()
    monkeypatch.setattr(bot, "WATCH_DB_PATH", str(path))
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [torrent()])
    app = SimpleNamespace(
        bot_data={},
        bot=SimpleNamespace(
            send_message=AsyncMock(return_value=SimpleNamespace(message_id=1)),
            edit_message_text=AsyncMock(),
        ),
    )
    await bot.monitoring_start(app)
    m = app.bot_data["monitoring"]
    assert len(m.tasks) == 1
    await bot.monitoring_stop(app)
    assert not m.tasks
    assert len(m.store.unfinished()) == 1
    await bot.monitoring_close(app)
    assert "monitoring" not in app.bot_data
    with pytest.raises(sqlite3.ProgrammingError):
        m.store.unfinished()


@async_test
async def test_repeated_subscription_does_not_replace_task(bot, tmp_path, monkeypatch):
    m, _ = manager(bot, tmp_path)
    await m.subscribe(101, 303, "a" * 40, "Example")
    task = m.tasks[(303, "a" * 40)]
    await m.subscribe(101, 303, "a" * 40, "Example")
    assert list(m.tasks.values()) == [task]
    await m.close()


@async_test
async def test_blocked_progress_stops_polling(bot, tmp_path, monkeypatch):
    m, telegram = manager(bot, tmp_path)
    telegram.send_message.side_effect = Forbidden("blocked")
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [torrent()])
    await m.subscribe(101, 303, "a" * 40, "Example")
    await asyncio.gather(*m.tasks.values())
    assert m.store.get(303, "a" * 40)["status"] == "blocked"
    await m.close()


def test_corrupt_database_is_not_replaced(tmp_path):
    storage, _ = modules()
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"not a sqlite database")
    with pytest.raises(sqlite3.DatabaseError):
        storage.WatchStore(path)
    assert path.read_bytes() == b"not a sqlite database"


@async_test
async def test_rate_limit_preserves_pending_notice_and_waits(bot, tmp_path, monkeypatch):
    from telegram.error import RetryAfter

    m, telegram = manager(bot, tmp_path)
    m.store.subscribe(101, 303, "a" * 40, "Example")
    m.store.pending(303, "a" * 40, "Saved completion")
    telegram.send_message.side_effect = [RetryAfter(42), SimpleNamespace(message_id=8)]
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    await m.restore()
    await asyncio.gather(*m.tasks.values())
    sleep.assert_awaited_once_with(42)
    assert m.store.get(303, "a" * 40)["status"] == "completed"
    await m.close()


@async_test
async def test_removed_torrents_are_not_restored(bot, tmp_path, monkeypatch):
    m, _ = manager(bot, tmp_path)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [])
    monkeypatch.setattr(bot, "WATCH_MISSING_GRACE_SEC", -1)
    await m.subscribe(101, 303, "a" * 40, "Example")
    await asyncio.gather(*m.tasks.values())
    assert m.store.get(303, "a" * 40)["status"] == "missing"
    await m.restore()
    assert not m.tasks
    await m.close()


@async_test
async def test_failed_completion_survives_shutdown(bot, tmp_path, monkeypatch):
    m, telegram = manager(bot, tmp_path)
    ready = asyncio.Event()

    async def interrupted_send(**kwargs):
        if kwargs["text"].startswith("Скачивание завершено:"):
            assert m.store.get(303, "a" * 40)["status"] == "pending"
            ready.set()
            await asyncio.Event().wait()
        return SimpleNamespace(message_id=9)

    telegram.send_message.side_effect = interrupted_send
    monkeypatch.setattr(
        bot,
        "qbit_torrents_info_sync",
        lambda **kw: [torrent(state="stalledUP", amount_left=0, progress=1)],
    )
    await m.subscribe(101, 303, "a" * 40, "Example")
    await ready.wait()
    await m.close()
    m, transport = manager(bot, tmp_path)
    monkeypatch.setattr(
        bot, "qbit_torrents_info_sync", lambda **kw: pytest.fail("Use saved notice")
    )
    await m.restore()
    await asyncio.gather(*m.tasks.values())
    assert transport.send_message.call_count == 1
    assert m.store.unfinished() == []
    await m.close()


def test_unwritable_journal_directory_fails_at_startup(tmp_path):
    storage, _ = modules()
    directory = tmp_path / "locked"
    path = directory / "watches.sqlite3"
    storage.WatchStore(path).close()
    directory.chmod(0o500)
    try:
        with pytest.raises(sqlite3.OperationalError):
            storage.WatchStore(path)
    finally:
        directory.chmod(0o700)


@async_test
async def test_removed_notice_retries_transient_delivery_failure(bot, tmp_path, monkeypatch):
    m, telegram = manager(bot, tmp_path)
    m.store.subscribe(101, 303, "a" * 40, "Example")
    m.store.set_message(303, "a" * 40, 12)
    telegram.edit_message_text.side_effect = [NetworkError("offline"), None]
    monkeypatch.setattr(
        bot,
        "qbit_torrents_info_sync",
        lambda **kw: [],
    )
    monkeypatch.setattr(bot, "WATCH_MISSING_GRACE_SEC", -1)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    await m.restore()
    await asyncio.gather(*m.tasks.values())
    assert telegram.edit_message_text.call_count == 2
    assert m.store.get(303, "a" * 40)["status"] == "missing"
    await m.close()
