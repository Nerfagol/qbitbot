"""Direct torrent links open fresh guarded views without mutating the library."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import requests

from tests.helpers import Message, context, torrent, update
from tests.test_persistence import async_test
from tests.test_search_ui import button, click, start


@pytest.mark.parametrize("length", [40, 64])
def test_link_fits_telegram_and_binds_identity_owner_chat_and_secret(length):
    from qbitbot.downloads import torrent_link, link_hash

    info = torrent(hash="a" * length, added_on=123)
    data = torrent_link(info, 101, 303, "test-secret")
    assert len(data.encode()) <= 64 and link_hash(data) == info["hash"]
    assert data != torrent_link(info, 202, 303, "test-secret")
    assert data != torrent_link(info, 101, 404, "test-secret")
    assert data != torrent_link(info, 101, 303, "changed-secret")
    assert data != torrent_link(dict(info, added_on=124), 101, 303, "test-secret")


@async_test
@pytest.mark.parametrize(
    "case", ["valid", "missing", "readded", "owner", "chat", "forged", "unauthorized", "outage"]
)
async def test_notification_link_opens_only_matching_download(bot, monkeypatch, case):
    from qbitbot.downloads import torrent_link

    info = torrent(added_on=123)
    data = torrent_link(info, 101, 303, bot.BOT_TOKEN)
    rows = [] if case == "missing" else [dict(info, added_on=124) if case == "readded" else info]
    reads = []

    def read(**kw):
        reads.append(kw)
        if case == "outage":
            raise requests.Timeout("SECRET")
        return rows

    monkeypatch.setattr(bot, "qbit_torrents_info_sync", read)
    mutate = AsyncMock()
    monkeypatch.setattr(bot, "qbit_control_sync", mutate)
    event = update(
        Message(),
        data + "x" if case == "forged" else data,
        user_id=999 if case == "unauthorized" else 202 if case == "owner" else 101,
    )
    if case == "chat":
        event.effective_chat.id = 404
    event.callback_query.answer = AsyncMock()
    ctx = context()
    await bot.on_torrent_link(event, ctx)
    if case == "valid":
        assert "Test download" in event.message.replies[-1].text
        assert "Пауза" in str(event.message.replies[-1].markup)
        assert "downloads" in ctx.user_data
        assert reads == [{"hashes": "a" * 40, "limit": 1}]
    else:
        assert "downloads" not in ctx.user_data
    if case == "unauthorized":
        assert not reads
    assert "SECRET" not in str(event.message.sent)
    assert not mutate.call_count


@pytest.mark.parametrize("duplicate", [False, True])
def test_added_feedback_opens_exact_target_and_retains_all_downloads(bot, monkeypatch, duplicate):
    info = torrent(added_on=123)
    message, ctx, add = start(bot, monkeypatch)
    add.return_value = {
        "ok": not duplicate,
        "already_exists": duplicate,
        "hash": info["hash"],
        "info": info,
    }
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [info])
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "Скачать")
    assert button(message, "Открыть эту загрузку") and button(message, "Все загрузки")
    click(bot, message, ctx, "Открыть эту загрузку")
    detail = message.replies[-1]
    assert "Test download" in detail.text and "Пауза" in str(detail.markup)
    assert add.await_count == 1


@async_test
async def test_stuck_watch_links_to_target(bot, monkeypatch):
    from tests.test_download_health import sample_until
    from qbitbot.downloads import link_hash

    info = torrent(state="metaDL", dlspeed=0, added_on=123)
    sample_until(bot.DOWNLOAD_HEALTH, info)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [info])
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())

    async def stop(*args):
        raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        await bot.watch_torrent_until_done(
            303,
            info["hash"],
            "Test",
            7,
            SimpleNamespace(bot=transport, user_id=101, language_for_user=lambda user: "ru"),
        )
    markup = transport.edit_message_text.call_args.kwargs["reply_markup"]
    assert link_hash(markup.inline_keyboard[0][0].callback_data) == info["hash"]
