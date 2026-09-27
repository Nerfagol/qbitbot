"""Health cards: safe probes, hourly edits, durable ownership and optional pinning."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import requests
from telegram.error import BadRequest, Forbidden, NetworkError

from tests.helpers import Message, update
from tests.test_persistence import async_test


def setup_health(bot, tmp_path):
    from health import HealthManager

    calls = []
    api = SimpleNamespace(
        allowed=bot.allowed,
        ALLOWED_USERS=bot.ALLOWED_USERS,
        check_qbit=lambda: calls.append("qbit"),
        check_jackett=lambda: calls.append("jackett"),
        last_search=lambda: None,
        language_for_user=lambda user: "ru",
    )
    telegram = SimpleNamespace(
        edit_message_text=AsyncMock(),
        pin_chat_message=AsyncMock(),
    )
    manager = HealthManager(api, telegram, tmp_path / "health.sqlite3")
    return manager, calls, telegram


def action(message, suffix):
    return next(
        b.callback_data
        for row in message.markup.inline_keyboard
        for b in row
        if b.callback_data.endswith(":" + suffix)
    )


def callback(message, data, user=101, chat=303):
    event = update(message, data, user_id=user)
    event.effective_chat.id = chat
    event.callback_query.answer = AsyncMock()
    return event


@async_test
async def test_open_refresh_and_hourly_cycle_edit_one_card(bot, tmp_path):
    manager, calls, telegram = setup_health(bot, tmp_path)
    try:
        request = Message()
        await manager.open(update(request))
        card = request.replies[-1]
        assert "каждый час" in card.text and "UTC" in card.text
        assert "qBittorrent — доступен" in card.text and "Jackett — доступен" in card.text
        assert "не проверялись" in card.text
        assert calls == ["qbit", "jackett"]
        await manager.open(update(request))
        assert len(request.replies) == 1
        await manager.callback(callback(card, action(card, "refresh")))
        assert len(calls) == 2  # Fast refreshes share a short cache.
        await manager.cycle()
        assert calls == ["qbit", "jackett"] * 2
        assert telegram.edit_message_text.call_args.kwargs["message_id"] == card.message_id
        assert not telegram.pin_chat_message.await_count
    finally:
        await manager.close()


@async_test
async def test_restart_restores_same_card_and_pin_is_explicit(bot, tmp_path):
    manager, _, telegram = setup_health(bot, tmp_path)
    request = Message()
    await manager.open(update(request))
    card = request.replies[-1]
    pin = action(card, "pin")
    await manager.close()
    restored, calls, transport = setup_health(bot, tmp_path)
    try:
        await restored.cycle()
        assert len(calls) == 2
        assert transport.edit_message_text.call_args.kwargs["message_id"] == card.message_id
        await restored.callback(callback(card, pin))
        assert transport.pin_chat_message.call_args.kwargs == {
            "chat_id": 303,
            "message_id": card.message_id,
            "disable_notification": True,
        }
        assert not telegram.pin_chat_message.await_count
    finally:
        await restored.close()


@async_test
@pytest.mark.parametrize("bad", ["owner", "unauthorized", "chat", "message", "token"])
async def test_card_callbacks_recheck_context_before_probes_or_pin(bot, tmp_path, bad):
    manager, calls, telegram = setup_health(bot, tmp_path)
    try:
        request = Message()
        await manager.open(update(request))
        card = request.replies[-1]
        event = callback(card, action(card, "pin"))
        if bad == "owner":
            event.effective_user.id = 202
        elif bad == "unauthorized":
            event.effective_user.id = 999
        elif bad == "chat":
            event.effective_chat.id = 404
        elif bad == "message":
            card.message_id += 1
        else:
            event.callback_query.data += "forged"
        await manager.callback(event)
        assert len(calls) == 2 and not telegram.pin_chat_message.await_count
    finally:
        await manager.close()


@async_test
@pytest.mark.parametrize("failure", [requests.Timeout("SECRET"), ValueError("SECRET")])
async def test_dependency_failure_isolated_and_no_raw_errors(bot, tmp_path, failure):
    manager, _, _ = setup_health(bot, tmp_path)
    manager.api.check_qbit = lambda: (_ for _ in ()).throw(failure)
    try:
        request = Message()
        await manager.open(update(request))
        text = request.replies[-1].text
        assert "qBittorrent —" in text and "Jackett — доступен" in text
        assert "SECRET" not in text
        assert (
            "не ответил вовремя" in text
            if isinstance(failure, requests.Timeout)
            else "недоступен" in text
        )
    finally:
        await manager.close()


@async_test
async def test_historical_indexer_status_is_labelled_and_timestamped(bot, tmp_path):
    manager, _, _ = setup_health(bot, tmp_path)
    manager.api.last_search = lambda: {
        "time": 1700000000,
        "responded": 3,
        "total": 4,
        "failed": False,
    }
    try:
        request = Message()
        await manager.open(update(request))
        text = request.replies[-1].text
        assert "3 из 4" in text and "Последний поиск" in text and "2023-11-14" in text
        assert "не проверяются" in text
    finally:
        await manager.close()


@async_test
@pytest.mark.parametrize("error", [Forbidden("SECRET"), BadRequest("Message to edit not found")])
async def test_missing_or_blocked_card_stops_updates_until_reopened(bot, tmp_path, error):
    manager, calls, telegram = setup_health(bot, tmp_path)
    try:
        request = Message()
        await manager.open(update(request))
        telegram.edit_message_text.side_effect = error
        await manager.cycle()
        await manager.cycle()
        assert len(calls) == 4 and telegram.edit_message_text.await_count == 1
    finally:
        await manager.close()


@async_test
async def test_transient_edit_failure_retries_next_cycle_and_revoked_user_is_removed(bot, tmp_path):
    manager, _, telegram = setup_health(bot, tmp_path)
    try:
        request = Message()
        await manager.open(update(request))
        telegram.edit_message_text.side_effect = [NetworkError("SECRET"), None]
        await manager.cycle()
        await manager.cycle()
        assert telegram.edit_message_text.await_count == 2
        manager.api.ALLOWED_USERS = set()
        await manager.cycle()
        assert telegram.edit_message_text.await_count == 2
    finally:
        await manager.close()


@async_test
async def test_hourly_loop_interval_and_shutdown(bot, tmp_path, monkeypatch):
    import health

    manager, _, _ = setup_health(bot, tmp_path)
    delays = []
    sleeping = asyncio.Event()

    async def sleep(delay):
        delays.append(delay)
        sleeping.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(health.asyncio, "sleep", sleep)
    manager.start()
    await sleeping.wait()
    task = manager.task
    await manager.close()
    assert delays == [3600] and task.cancelled()


@pytest.mark.parametrize("body", ['<error code="100" description="SECRET"/>', "<html/>", "<rss/>"])
def test_jackett_probe_rejects_false_success_without_search(monkeypatch, body):
    from health import check_jackett

    calls = []
    monkeypatch.setattr(
        requests,
        "get",
        lambda url, **kw: calls.append((url, kw))
        or SimpleNamespace(raise_for_status=lambda: None, text=body),
    )
    with pytest.raises(ValueError):
        check_jackett("http://fixture/api?t=search&q=film&apikey=old", "test-key")
    assert calls[0][1]["params"] == {"apikey": "test-key", "t": "caps"}
    assert "q=" not in calls[0][0] and "apikey=" not in calls[0][0]


def test_jackett_capabilities_probe_accepts_valid_response(monkeypatch):
    from health import check_jackett

    monkeypatch.setattr(
        requests,
        "get",
        lambda *a, **kw: SimpleNamespace(
            raise_for_status=lambda: None, text="<caps><searching/></caps>"
        ),
    )
    check_jackett("http://fixture/api", "test-key")


@async_test
async def test_command_navigation_and_lifecycle_restore_health_manager(bot, tmp_path, monkeypatch):
    monkeypatch.setattr(bot, "WATCH_DB_PATH", str(tmp_path / "watches.sqlite3"))
    telegram = SimpleNamespace(
        set_my_commands=AsyncMock(),
        set_chat_menu_button=AsyncMock(),
        edit_message_text=AsyncMock(),
        pin_chat_message=AsyncMock(),
    )
    app = SimpleNamespace(bot=telegram, bot_data={})
    try:
        await bot.application_start(app)
        manager = app.bot_data["health"]
        manager.api.check_qbit = lambda: None
        manager.api.check_jackett = lambda: None
        event = update(Message())
        ctx = SimpleNamespace(application=app)
        await bot.cmd_health(event, ctx)
        assert "Состояние системы" in event.message.replies[-1].text
        task = manager.task
        await bot.monitoring_stop(app)
        assert task.cancelled()
    finally:
        await bot.monitoring_close(app)
    assert manager.closed


def test_search_records_only_safe_coverage_and_failure(bot, monkeypatch):
    from search_ui import SearchResults

    monkeypatch.setattr(bot, "_jackett_search_sync", lambda *a: SearchResults(statuses=[2, 1]))
    bot.jackett_search_sync("private title")
    assert bot.LAST_SEARCH_HEALTH["responded"] == 1
    assert bot.LAST_SEARCH_HEALTH["total"] == 2
    assert "private" not in str(bot.LAST_SEARCH_HEALTH)
    monkeypatch.setattr(
        bot, "_jackett_search_sync", lambda *a: (_ for _ in ()).throw(requests.Timeout("SECRET"))
    )
    with pytest.raises(requests.Timeout):
        bot.jackett_search_sync("private title")
    assert bot.LAST_SEARCH_HEALTH["failed"]
    assert "SECRET" not in str(bot.LAST_SEARCH_HEALTH)


@async_test
@pytest.mark.parametrize("removed", [False, True])
async def test_callback_acknowledges_while_hourly_check_runs_and_revalidates(
    bot, tmp_path, removed
):
    manager, _, telegram = setup_health(bot, tmp_path)
    request = Message()
    await manager.open(update(request))
    card = request.replies[-1]
    event = callback(card, action(card, "pin"))
    blocked = asyncio.Event()
    release = asyncio.Event()
    original_sample = manager.sample

    async def delayed_sample(**kwargs):
        blocked.set()
        await release.wait()
        await original_sample(**kwargs)

    manager.sample = delayed_sample
    if removed:
        telegram.edit_message_text.side_effect = BadRequest("Message to edit not found")
    cycle = asyncio.create_task(manager.cycle())
    await blocked.wait()
    press = asyncio.create_task(manager.callback(event))
    try:
        await asyncio.sleep(0)
        assert event.callback_query.answer.await_count == 1
        assert not telegram.pin_chat_message.await_count
        release.set()
        await cycle
        await press
        assert telegram.pin_chat_message.await_count == (0 if removed else 1)
    finally:
        release.set()
        await asyncio.gather(cycle, press, return_exceptions=True)
        await manager.close()
