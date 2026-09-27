"""Recommendations and feedback for users who do not know torrent terminology."""

import asyncio
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import requests

from tests.helpers import torrent, update
from tests.test_search_ui import button, click, results, start

GIB = 1024**3


def test_recommended_balances_sources_resolution_and_size(bot, monkeypatch):
    items = results(4)
    for item, title, seeds, size in zip(
        items,
        ["Film.2160p.Huge", "Film.1080p.Balanced", "Film.1080p.Empty", "Film.1080p.Unknown"],
        [1, 40, 0, None],
        [70 * GIB, 3 * GIB, 2 * GIB, None],
    ):
        item.update(title=title, seeders=seeds, size=size)
    message, ctx, add = start(bot, monkeypatch, items)
    assert "⭐ Рекомендуемые" in message.text
    assert "1. Film.1080p.Balanced" in message.text
    click(bot, message, ctx, "1")
    assert add.await_count == 0
    click(bot, message, ctx, "Скачать")
    assert add.await_args.args[0] == items[1]["url"]


def test_recommended_fallback_balances_size_below_source_threshold(bot, monkeypatch):
    items = results(3)
    for item, title, seeds, size in zip(
        items, ["Film.2160p", "Film.1080p", "Film.720p"], [20, 20, 20], [70 * GIB, 3 * GIB, GIB]
    ):
        item.update(title=title, seeders=seeds, size=size)
    message, ctx, _ = start(bot, monkeypatch, items)
    assert "1. Film.1080p" in message.text
    click(bot, message, ctx, "Качество")
    assert "1. Film.2160p" in message.text


@pytest.mark.parametrize(
    "seeds,label",
    [
        (20, "🟢 Много источников"),
        (5, "🟢 Есть источники"),
        (1, "🟡 Мало источников"),
        (0, "🔴 Нет источников"),
        (None, "⚪ Источники неизвестны"),
        (-1, "⚪ Источники неизвестны"),
    ],
)
def test_plain_labels_and_exact_counts_only_in_preview(bot, monkeypatch, seeds, label):
    items = results(1)
    items[0].update(title="Film.1080p", seeders=seeds, size=3 * GIB)
    message, ctx, _ = start(bot, monkeypatch, items)
    assert "🎬 Full HD" in message.text and label in message.text
    assert "Сиды:" not in message.text
    click(bot, message, ctx, "1")
    assert "по названию" in message.text
    assert (
        f"Полных источников: {seeds if seeds is not None and seeds >= 0 else 'неизвестно'}"
        in message.text
    )
    assert "скорост" not in message.text.lower()


@pytest.mark.parametrize(
    "outcome,expected",
    [
        ({"ok": True, "hash": "a" * 40, "info": torrent()}, "✅ Добавлено в загрузки"),
        (
            {"ok": False, "already_exists": True, "hash": "a" * 40, "info": torrent()},
            "ℹ️ Уже есть в загрузках",
        ),
        ({"ok": False, "add_reply": "SECRET"}, "⚠️ Добавление пока не подтверждено"),
        ({"ok": True, "hash": None}, "⚠️ Добавление пока не подтверждено"),
        (requests.Timeout("SECRET"), "⚠️ Добавление пока не подтверждено"),
    ],
)
def test_download_feedback_is_accurate_and_preserves_navigation(
    bot, monkeypatch, outcome, expected
):
    message, ctx, add = start(bot, monkeypatch)
    ctx.application.bot_data["monitoring"] = SimpleNamespace(subscribe=AsyncMock())
    if isinstance(outcome, Exception):
        add.side_effect = outcome
    else:
        add.return_value = outcome
    click(bot, message, ctx, "1")
    token = button(message, "Скачать")
    asyncio.run(bot.on_pick(update(message, token), ctx))
    assert expected in message.text
    assert "SECRET" not in message.text
    assert "state:" not in message.text and "progress:" not in message.text
    button(message, "Все загрузки")
    button(message, "К результатам")
    assert not any("Скачать" in b.text for row in message.markup.inline_keyboard for b in row)
    asyncio.run(bot.on_pick(update(message, token), ctx))
    assert add.await_count == 1
    click(bot, message, ctx, "К результатам")
    assert "1/3" in message.text


def test_notification_failure_does_not_hide_success_or_promise_notice(bot, monkeypatch):
    message, ctx, add = start(bot, monkeypatch)
    add.return_value = {"ok": True, "hash": "a" * 40, "info": torrent()}
    ctx.application.bot_data["monitoring"] = SimpleNamespace(
        subscribe=AsyncMock(side_effect=OSError("SECRET"))
    )
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "Скачать")
    assert "✅ Добавлено в загрузки" in message.text
    assert "Не удалось подтвердить уведомления" in message.text
    assert "Сообщу" not in message.text
    assert "SECRET" not in message.text


def test_open_downloads_from_feedback_preserves_search_back_action(bot, monkeypatch):
    message, ctx, _ = start(bot, monkeypatch)
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "Скачать")
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [])
    click(bot, message, ctx, "Все загрузки")
    assert "Торрентов пока нет" in message.sent[-1]["text"]
    click(bot, message, ctx, "К результатам")
    assert "1/3" in message.text


def test_recommended_demotes_camera_recordings_even_with_many_sources(bot, monkeypatch):
    items = results(2)
    items[0].update(title="Film.1080p.HDCAM", seeders=9000, size=2 * GIB)
    items[1].update(title="Film.1080p.WEB-DL", seeders=3, size=3 * GIB)
    message, _, _ = start(bot, monkeypatch, items)
    assert "1. Film.1080p.WEB-DL" in message.text


def test_healthy_recommendations_prioritize_quality_and_size_over_extra_sources(bot, monkeypatch):
    items = results(3)
    for item, name, seeds, size in zip(
        items,
        ["Film.1080p", "Film.2160p.Large", "Film.2160p.Small"],
        [9000, 500, 25],
        [3 * GIB, 60 * GIB, 20 * GIB],
    ):
        item.update(title=name, seeders=seeds, size=size)
    message, ctx, add = start(bot, monkeypatch, items)
    assert "1. Film.2160p.Small" in message.text
    assert message.text.index("Film.2160p.Large") < message.text.index("Film.1080p")
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "Скачать")
    assert add.await_args.args[0] == items[2]["url"]


def test_first_recommended_page_reserves_full_hd_and_4k_choices(bot, monkeypatch):
    items = results(10)
    for i, item in enumerate(items):
        item.update(
            title=f"Film.{'2160p' if i < 7 else '1080p'}.{i}", seeders=25, size=(i + 1) * GIB
        )
    message, ctx, _ = start(bot, monkeypatch, items)
    assert len(re.findall(r"\d+\. Film\.1080p", message.text)) == 2
    assert len(re.findall(r"\d+\. Film\.2160p", message.text)) >= 2
    visible = re.findall(r"\d+\. (Film\.[^\n]+)", message.text)
    click(bot, message, ctx, "Далее")
    visible += re.findall(r"\d+\. (Film\.[^\n]+)", message.text)
    assert len(visible) == len(set(visible)) == 10


def test_low_source_4k_is_not_promoted_to_fill_a_quality_slot(bot, monkeypatch):
    items = results(6)
    for i, item in enumerate(items):
        item.update(title=f"Film.1080p.{i}", seeders=25)
    items[-1].update(title="Film.2160p.Few", seeders=24)
    message, _, _ = start(bot, monkeypatch, items)
    assert "Film.2160p.Few" not in message.text
