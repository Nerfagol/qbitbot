"""Completion notices retain useful actions through delivery failures and restarts."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import NetworkError

from tests.helpers import torrent
from tests.test_persistence import async_test, manager


@async_test
async def test_completion_has_exact_details_and_location_without_plex(bot, monkeypatch):
    from qbitbot.downloads import link_hash

    info = torrent(
        state="stalledUP",
        amount_left=0,
        progress=1,
        added_on=123,
        content_path="/downloads/Film/Film.mkv",
        save_path="/downloads",
    )
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [info])
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    await bot.watch_torrent_until_done(
        303,
        info["hash"],
        "Test",
        7,
        SimpleNamespace(bot=transport, user_id=101, language_for_user=lambda user: "ru"),
    )
    call = transport.send_message.call_args
    text = call.args[1]
    assert "Plex" not in text
    assert "/downloads/Film/Film.mkv" in text
    assert "qBittorrent" in text
    buttons = [b for row in call.kwargs["reply_markup"].inline_keyboard for b in row]
    assert not any(b.url for b in buttons)
    assert any(
        b.callback_data
        and b.callback_data.startswith("go:")
        and link_hash(b.callback_data) == info["hash"]
        for b in buttons
    )
    assert len(text.encode("utf-16-le")) // 2 < 4096


@async_test
async def test_completion_buttons_survive_pending_delivery_and_restart_without_qbit(
    bot, tmp_path, monkeypatch
):
    info = torrent(state="stalledUP", amount_left=0, progress=1, added_on=123)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [info])
    m, telegram = manager(bot, tmp_path)
    failed = asyncio.Event()

    async def send(**kw):
        if kw["text"].startswith("Скачивание завершено:"):
            failed.set()
            raise NetworkError("SECRET")
        return SimpleNamespace(message_id=77)

    telegram.send_message.side_effect = send
    await m.subscribe(101, 303, info["hash"], "Film")
    await failed.wait()
    original = telegram.send_message.call_args.kwargs
    await m.close()
    restored, transport = manager(bot, tmp_path)
    monkeypatch.setattr(
        bot, "qbit_torrents_info_sync", lambda **kw: pytest.fail("Use durable notice")
    )
    try:
        await restored.restore()
        await asyncio.gather(*restored.tasks.values())
        saved = transport.send_message.call_args.kwargs
        assert saved["text"] == original["text"]
        assert saved["reply_markup"] == original["reply_markup"]
        assert any(
            b.callback_data and b.callback_data.startswith("go:")
            for row in saved["reply_markup"].inline_keyboard
            for b in row
        )
        assert not restored.store.unfinished()
    finally:
        await restored.close()


def test_optional_notice_metadata_preserves_v1_watch_table_and_legacy_pending(tmp_path):
    from qbitbot.watch_store import WatchStore
    import sqlite3

    path = tmp_path / "legacy.sqlite3"
    store = WatchStore(path)
    store.subscribe(101, 303, "a" * 40, "Film")
    store.pending(303, "a" * 40, "Legacy text")
    assert store.pending_markup(303, "a" * 40) is None
    columns = [row[1] for row in store.db.execute("PRAGMA table_info(watches)")]
    assert columns == [
        "chat_id",
        "torrent_hash",
        "user_id",
        "title",
        "message_id",
        "status",
        "notice",
    ]
    store.close()
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE IF EXISTS notice_markup")
    reopened = WatchStore(path)
    assert reopened.get(303, "a" * 40)["notice"] == "Legacy text"
    assert reopened.pending_markup(303, "a" * 40) is None
    reopened.close()


def test_legacy_writer_cannot_attach_old_buttons_to_a_new_notice(tmp_path):
    from qbitbot.watch_store import WatchStore

    store = WatchStore(tmp_path / "watches.sqlite3")
    try:
        store.subscribe(101, 303, "a" * 40, "Film")
        markup = {"inline_keyboard": [[{"text": "Old", "callback_data": "old"}]]}
        store.pending(303, "a" * 40, "First notice", markup)
        assert store.pending_markup(303, "a" * 40) == markup
        # Simulate an older release writing the unchanged v1 table after rollback.
        with store.db:
            store.db.execute("UPDATE watches SET notice='New legacy notice'")
        assert store.pending_markup(303, "a" * 40) is None
    finally:
        store.close()


@async_test
async def test_legacy_pending_plex_button_and_note_are_removed_on_delivery(bot, tmp_path):
    m, telegram = manager(bot, tmp_path)
    t_hash = "a" * 40
    m.store.subscribe(101, 303, t_hash, "Film")
    text = "Скачивание завершено:\nFilm\n\n📺 Наличие файла в Plex не проверено. Папка загрузки должна быть подключена к медиатеке."
    m.store.pending(
        303,
        t_hash,
        text,
        {
            "inline_keyboard": [
                [{"text": "📺 Открыть Plex", "url": "https://app.plex.tv/desktop"}],
                [{"text": "Все загрузки", "callback_data": "nav:downloads"}],
            ]
        },
    )
    try:
        await m.restore()
        await asyncio.gather(*m.tasks.values())
        call = telegram.send_message.call_args.kwargs
        assert "Plex" not in call["text"]
        buttons = [b for row in call["reply_markup"].inline_keyboard for b in row]
        assert len(buttons) == 1 and buttons[0].callback_data == "nav:downloads"
    finally:
        await m.close()
