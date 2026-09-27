import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import requests

from tests.helpers import Message, context, torrent, update


def search(bot, monkeypatch):
    ctx = context()
    message = Message("query")
    monkeypatch.setattr(
        bot,
        "jackett_search_sync",
        lambda *args: [{"title": "Result", "url": "magnet:?xt=urn:btih:" + "a" * 40}],
    )
    asyncio.run(bot.on_text(update(message), ctx))
    message = message.replies[-1]
    callback = message.markup.inline_keyboard[0][0].callback_data
    asyncio.run(bot.on_pick(update(message, callback), ctx))
    callback = message.markup.inline_keyboard[0][0].callback_data
    add = AsyncMock(return_value={"ok": False, "already_exists": True, "info": torrent()})
    monkeypatch.setattr(bot, "qbit_add_and_confirm", add)
    return ctx, message, callback, add


def test_current_search_still_adds_selected_result(bot, monkeypatch):
    ctx, message, callback, add = search(bot, monkeypatch)
    asyncio.run(bot.on_pick(update(message, callback), ctx))
    assert add.await_args.args[0] == "magnet:?xt=urn:btih:" + "a" * 40


def test_search_from_another_chat_is_rejected(bot, monkeypatch):
    ctx, message, callback, add = search(bot, monkeypatch)
    event = update(message, callback)
    event.effective_chat.id = 404
    asyncio.run(bot.on_pick(event, ctx))
    assert add.await_count == 0


def test_search_expires_after_fifteen_minutes(bot, monkeypatch):
    now = bot.time.monotonic()
    monkeypatch.setattr(bot.time, "monotonic", lambda: now)
    ctx, message, callback, add = search(bot, monkeypatch)
    monkeypatch.setattr(bot.time, "monotonic", lambda: now + 901)
    asyncio.run(bot.on_pick(update(message, callback), ctx))
    assert add.await_count == 0


def test_empty_new_search_preserves_previous_confirmation(bot, monkeypatch):
    ctx, message, callback, add = search(bot, monkeypatch)
    monkeypatch.setattr(bot, "jackett_search_sync", lambda *args: [])
    asyncio.run(bot.on_text(update(Message("no results")), ctx))
    asyncio.run(bot.on_pick(update(message, callback), ctx))
    assert add.await_count == 1


@pytest.mark.parametrize(
    "state",
    [
        "metaDL",
        "forcedMetaDL",
        "checkingDL",
        "checkingUP",
        "checkingResumeData",
        "moving",
        "missingFiles",
        "error",
        "unknown",
    ],
)
def test_unverified_or_broken_states_are_never_complete(bot, state):
    assert not bot.is_completed(torrent(state=state, progress=1, amount_left=0))


@pytest.mark.parametrize(
    "state", ["uploading", "stalledUP", "queuedUP", "stoppedUP", "forcedUP", "pausedUP"]
)
def test_complete_upload_states_are_recognized(bot, state):
    assert bot.is_completed(torrent(state=state, progress=1, amount_left=0))


def test_zero_unknown_size_is_not_complete(bot):
    assert not bot.is_completed(torrent(state="uploading", progress=1, amount_left=0, total_size=0))


def test_status_does_not_render_unknown_eta_as_duration(bot):
    text = bot.format_torrent_line(torrent(eta=8640000), language="ru")
    assert "100d" not in text and "ETA" not in text


def test_watcher_backoff_is_capped_and_recovers(bot, monkeypatch):
    attempts, delays = [], []

    def read(**kwargs):
        attempts.append(1)
        if len(attempts) <= 8:
            raise requests.Timeout("DO_NOT_EXPOSE_TOKEN")
        return [torrent(state="uploading", progress=1, amount_left=0)]

    async def sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(bot, "qbit_torrents_info_sync", read)
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    monkeypatch.setattr(bot, "WATCH_INTERVAL_SEC", 30)
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    asyncio.run(
        bot.watch_torrent_until_done(
            303,
            "a" * 40,
            "Test",
            10,
            SimpleNamespace(bot=transport, language_for_user=lambda user: "ru"),
        )
    )
    assert delays == [30, 60, 120, 240, 300, 300, 300, 300]
    assert transport.send_message.call_count == 1
    edits = [call.kwargs["text"] for call in transport.edit_message_text.call_args_list]
    assert "qBittorrent" in edits[0] and "100%" in edits[-1]
    assert "DO_NOT_EXPOSE_TOKEN" not in "".join(edits)


def test_watcher_remains_cancellable_during_outage(bot, monkeypatch):
    def read(**kwargs):
        raise requests.ConnectionError("temporary outage")

    async def cancel(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(bot, "qbit_torrents_info_sync", read)
    monkeypatch.setattr(bot.asyncio, "sleep", cancel)
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            bot.watch_torrent_until_done(
                303,
                "a" * 40,
                "Test",
                10,
                SimpleNamespace(bot=transport, language_for_user=lambda user: "ru"),
            )
        )


@pytest.mark.parametrize(
    "handler,dependency",
    [("on_text", "jackett_search_sync"), ("cmd_status", "qbit_torrents_info_sync")],
)
def test_api_exception_details_are_not_sent_to_chat(bot, monkeypatch, handler, dependency):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("https://example.invalid/file?passkey=HIDDEN_SECRET")

    monkeypatch.setattr(bot, dependency, fail)
    message = Message("query")
    asyncio.run(getattr(bot, handler)(update(message), context()))
    assert "HIDDEN_SECRET" not in "".join(item["text"] for item in message.sent)


def test_error_logger_omits_exception_secrets(bot, capsys):
    asyncio.run(bot.on_error(None, SimpleNamespace(error=RuntimeError("HIDDEN_SECRET"))))
    assert "HIDDEN_SECRET" not in capsys.readouterr().out
