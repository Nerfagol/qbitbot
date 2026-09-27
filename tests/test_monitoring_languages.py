"""Owned background messages and durable language boundaries."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from qbitbot.preferences import LanguageService, PreferenceStore
from tests.helpers import Message, torrent, update
from tests.test_health import setup_health, callback, action
from tests.test_persistence import manager


def test_shared_health_snapshot_renders_owner_language_and_refresh(bot, tmp_path):
    async def scenario():
        health, calls, telegram = setup_health(bot, tmp_path)
        service = LanguageService(PreferenceStore(tmp_path / "preferences.sqlite3"))
        service.set_for_user(101, "ru")
        service.set_for_user(202, "en")
        health.api.language_for_user = service.for_user
        try:
            ru, en = Message(), Message()
            await health.open(update(ru, user_id=101))
            await health.open(update(en, user_id=202))
            assert "Состояние системы" in ru.replies[-1].text
            assert "System health" in en.replies[-1].text
            assert len(calls) == 2
            service.set_for_user(101, "en")
            card = ru.replies[-1]
            await health.callback(callback(card, action(card, "refresh")))
            assert "System health" in telegram.edit_message_text.call_args.kwargs["text"]
            await health.close()
            restored, _, transport = setup_health(bot, tmp_path)
            restored.api.language_for_user = service.for_user
            await restored.cycle()
            assert all(
                "System health" in c.kwargs["text"]
                for c in transport.edit_message_text.call_args_list
            )
            await restored.close()
        finally:
            await health.close()
            service.store.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "language,expected", [("en", "Download complete:"), ("ru", "Скачивание завершено:")]
)
def test_completion_uses_owner_language(bot, monkeypatch, language, expected):
    monkeypatch.setattr(
        bot,
        "qbit_torrents_info_sync",
        lambda **kw: [torrent(state="uploading", progress=1, amount_left=0)],
    )
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    ctx = SimpleNamespace(bot=transport, user_id=101, language_for_user=lambda user: language)
    asyncio.run(bot.watch_torrent_until_done(303, "a" * 40, "Test", 1, ctx))
    assert transport.send_message.call_args.args[1].startswith(expected)


def test_pending_russian_payload_survives_preference_change_and_reopen(bot, tmp_path, monkeypatch):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    async def scenario():
        original, transport = manager(bot, tmp_path)
        original.store.subscribe(101, 303, "a" * 40, "Test")
        text = "Скачивание завершено:\nТест {unchanged}"
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Подробнее", callback_data="nav:downloads")]]
        )
        original.store.pending(303, "a" * 40, text, markup.to_dict())
        await original.close()
        monkeypatch.setattr(bot, "language_for_user", lambda user: "en", raising=False)
        monkeypatch.setattr(
            bot,
            "qbit_torrents_info_sync",
            lambda **kw: pytest.fail("Pending payload needs no service query"),
        )
        restored, transport = manager(bot, tmp_path)
        await restored.restore()
        await asyncio.gather(*restored.tasks.values())
        call = transport.send_message.call_args.kwargs
        assert call["text"] == text
        assert call["reply_markup"].to_dict() == markup.to_dict()
        await restored.close()

    asyncio.run(scenario())


def test_setup_diagnostics_language_and_secret_safety(monkeypatch, capsys):
    from qbitbot.cli import setup_check

    monkeypatch.setattr(setup_check, "load_env", lambda: None)
    monkeypatch.setattr(setup_check, "read_settings", lambda env: object())
    monkeypatch.setattr(
        setup_check,
        "run_checks",
        lambda settings: [setup_check.CheckResult("Jackett", False, "setup.auth")],
    )
    assert setup_check.main(["--language", "ru"]) == 1
    assert "Проверь" in capsys.readouterr().out


def test_shutdown_stops_all_language_readers_before_store_close(bot):
    order = []

    async def stopped(name):
        order.append(name)

    app = SimpleNamespace(
        bot_data={
            "search_jobs": SimpleNamespace(stop=lambda: stopped("search")),
            "health": SimpleNamespace(close=lambda: stopped("health")),
            "monitoring": SimpleNamespace(close=lambda: stopped("watches")),
            "languages": SimpleNamespace(
                store=SimpleNamespace(close=lambda: order.append("preferences"))
            ),
        }
    )
    asyncio.run(bot.monitoring_close(app))
    assert order == ["search", "health", "watches", "preferences"]


def test_restored_watch_uses_reopened_detected_preference(bot, tmp_path, monkeypatch):
    async def scenario():
        path = tmp_path / "preferences.sqlite3"
        service = LanguageService(PreferenceStore(path))
        service.for_user(101, "ru-RU")
        service.store.close()
        restored = LanguageService(PreferenceStore(path))
        monkeypatch.setattr(bot, "language_for_user", restored.for_user, raising=False)
        monkeypatch.setattr(
            bot,
            "qbit_torrents_info_sync",
            lambda **kw: [torrent(state="uploading", progress=1, amount_left=0)],
        )
        watcher, transport = manager(bot, tmp_path)
        watcher.store.subscribe(101, 303, "a" * 40, "Test")
        await watcher.close()
        watcher, transport = manager(bot, tmp_path)
        await watcher.restore()
        await asyncio.gather(*watcher.tasks.values())
        assert transport.send_message.call_args.kwargs["text"].startswith("Скачивание завершено:")
        await watcher.close()
        restored.store.close()

    asyncio.run(scenario())


def test_completion_rechecks_language_after_progress_delivery(bot, monkeypatch):
    language = ["ru"]
    monkeypatch.setattr(
        bot,
        "qbit_torrents_info_sync",
        lambda **kw: [torrent(state="uploading", progress=1, amount_left=0)],
    )

    async def edit(**kwargs):
        language[0] = "en"

    transport = SimpleNamespace(edit_message_text=edit, send_message=AsyncMock())
    context = SimpleNamespace(
        bot=transport, user_id=101, language_for_user=lambda user: language[0]
    )
    asyncio.run(bot.watch_torrent_until_done(303, "a" * 40, "Fixture", 1, context))
    assert transport.send_message.call_args.args[1].startswith("Download complete:")
