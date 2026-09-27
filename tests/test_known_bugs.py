"""Regression coverage for the six defects captured from the deployment baseline."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import requests

from tests.helpers import Message, context, torrent, update

pytestmark = pytest.mark.known_bug


def test_old_result_button_does_not_add_new_search_result(bot, monkeypatch):
    ctx = context()
    searches = {
        "first": [{"title": "First result", "url": "magnet:?xt=urn:btih:" + "a" * 40}],
        "second": [{"title": "Second result", "url": "magnet:?xt=urn:btih:" + "b" * 40}],
    }
    monkeypatch.setattr(bot, "jackett_search_sync", lambda query, limit: searches[query])
    first = Message("first", 10)
    second = Message("second", 20)
    asyncio.run(bot.on_text(update(first), ctx))
    first = first.replies[-1]
    callback = first.markup.inline_keyboard[0][0].callback_data
    asyncio.run(bot.on_pick(update(first, callback), ctx))
    callback = first.markup.inline_keyboard[0][0].callback_data
    asyncio.run(bot.on_text(update(second), ctx))
    selected = []

    async def add(url, **kwargs):
        selected.append(url)
        return {"ok": False, "already_exists": True, "info": torrent()}

    monkeypatch.setattr(bot, "qbit_add_and_confirm", add)
    asyncio.run(bot.on_pick(update(first, callback), ctx))
    # Rejecting stale buttons OR selecting their original item is safe.
    assert selected in ([], [searches["first"][0]["url"]])


def test_metadata_fetch_is_not_complete(bot):
    assert not bot.is_completed(torrent(state="metaDL", progress=0, amount_left=0, total_size=0))


def test_bytes_remaining_are_not_complete(bot):
    assert not bot.is_completed(torrent(progress=0.999, amount_left=1024))


def test_unknown_eta_is_not_a_duration(bot):
    assert bot.human_eta(8640000) in ("", "unknown", "—")


def test_watcher_recovers_from_transient_api_failure(bot, monkeypatch):
    calls = 0

    def info(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise requests.ConnectionError("Synthetic temporary outage")
        return [torrent(state="uploading", progress=1.0, amount_left=0)]

    monkeypatch.setattr(bot, "qbit_torrents_info_sync", info)
    monkeypatch.setattr(bot, "WATCH_INTERVAL_SEC", 0)
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())

    async def watch():
        await asyncio.wait_for(
            bot.watch_torrent_until_done(
                303, "a" * 40, "Test download", 10, SimpleNamespace(bot=transport)
            ),
            timeout=2,
        )

    asyncio.run(watch())
    assert transport.send_message.call_count == 1


@pytest.mark.parametrize("redact_enabled", [True, False])
def test_failed_add_does_not_disclose_url_credentials(bot, monkeypatch, redact_enabled):
    ctx = context()
    monkeypatch.setattr(
        bot,
        "jackett_search_sync",
        lambda *args: [{"title": "Example", "url": "https://example.invalid/file"}],
    )
    secret = "SYNTHETIC_TRACKER_SECRET"
    monkeypatch.setattr(bot, "DIAG_REDACT", redact_enabled)
    add = AsyncMock(
        return_value={
            "ok": False,
            "add_reply": secret,
            "url_add_error": secret,
            "file_add_error": secret,
        }
    )
    monkeypatch.setattr(bot, "qbit_add_and_confirm", add)
    monkeypatch.setattr(
        bot,
        "probe_url",
        AsyncMock(
            return_value={
                "ok": True,
                "method": "HEAD",
                "status": 200,
                "content_type": "application/x-bittorrent",
                "final_url": f"https://example.invalid/file?passkey={secret}",
            }
        ),
    )
    message = Message("query")
    asyncio.run(bot.on_text(update(message), ctx))
    message = message.replies[-1]
    callback = message.markup.inline_keyboard[0][0].callback_data
    asyncio.run(bot.on_pick(update(message, callback), ctx))
    assert add.await_count == 0
    callback = message.markup.inline_keyboard[0][0].callback_data
    asyncio.run(bot.on_pick(update(message, callback), ctx))
    assert add.await_count == 1
    assert "не подтверждено" in message.text
    assert secret not in message.text
    assert secret not in "\n".join(item["text"] for item in message.sent)
