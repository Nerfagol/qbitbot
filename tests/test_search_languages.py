import asyncio
from unittest.mock import AsyncMock

import pytest

from search_ui import SearchResults, release_details
from tests.helpers import Message, context, update
from tests.test_search_ui import button


def start_in(bot, monkeypatch, language, items=None):
    items = (
        items
        if items is not None
        else SearchResults(
            [
                {
                    "title": "Example.2024.1080p [Audio: RUS / ENG]",
                    "url": "magnet:?xt=urn:btih:" + "a" * 40,
                    "seeders": 30,
                    "size": 1024,
                }
            ],
            statuses=[2, 1],
        )
    )
    monkeypatch.setattr(bot, "jackett_search_sync", lambda *a: items)
    ctx = context()
    msg = Message("Скачать Example {title}")
    event = update(msg)
    event.effective_user.language_code = language
    asyncio.run(bot.on_text(event, ctx))
    return msg.replies[-1], ctx


@pytest.mark.parametrize(
    "language,partial,download,filters",
    [
        ("en", "Search incomplete", "Download", "Filters"),
        ("ru", "Поиск неполный", "Скачать", "Фильтры"),
    ],
)
def test_search_preview_filters_and_titles_in_both_languages(
    bot, monkeypatch, language, partial, download, filters
):
    card, ctx = start_in(bot, monkeypatch, language)
    assert partial in card.text
    assert "Скачать Example {title}" in card.text
    assert any(filters in b.text for row in card.markup.inline_keyboard for b in row)
    event = update(card, button(card, "1"))
    event.effective_user.language_code = language
    asyncio.run(bot.on_pick(event, ctx))
    assert "Full HD" in card.text
    assert any(download in b.text for row in card.markup.inline_keyboard for b in row)
    assert ("Russian, English" if language == "en" else "Русский, английский") in card.text


def test_switch_language_preserves_target_and_single_use_download(bot, monkeypatch):
    card, ctx = start_in(bot, monkeypatch, "ru")
    service = bot.language_service(ctx)
    service.set_for_user(101, "en")
    asyncio.run(bot.on_pick(update(card, button(card, "1")), ctx))
    assert "Add this torrent" in card.text
    add = AsyncMock(return_value={"ok": False, "already_exists": True, "info": {}})
    monkeypatch.setattr(bot, "qbit_add_and_confirm", add)
    data = button(card, "Download")
    asyncio.run(bot.on_pick(update(card, data), ctx))
    asyncio.run(bot.on_pick(update(card, data), ctx))
    assert add.await_count == 1
    assert add.await_args.args[0] == "magnet:?xt=urn:btih:" + "a" * 40
    assert "Already in downloads" in card.text


def test_coverage_rerenders_after_language_change(bot, monkeypatch):
    card, ctx = start_in(bot, monkeypatch, "ru")
    bot.language_service(ctx).set_for_user(101, "en")
    asyncio.run(bot.on_pick(update(card, button(card, "Сортировка")), ctx))
    assert "Search incomplete" in card.text and "Поиск неполный" not in card.text


@pytest.mark.parametrize(
    "language,want", [("en", "Season 2 · Episode 3"), ("ru", "Сезон 2 · Серия 3")]
)
def test_release_episode_is_translated_without_changing_name(language, want):
    details = release_details("Example.Name.S02E03.1080p", language=language)
    assert details["heading"] == "Example Name" and details["episode"] == want


@pytest.mark.parametrize("language,expected", [("en", "Please wait"), ("ru", "Дождись")])
def test_busy_search_feedback_uses_owner_language(bot, monkeypatch, language, expected):
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def pending(event, ctx):
            started.set()
            await release.wait()

        monkeypatch.setattr(bot, "on_text", pending)
        ctx = context()
        event = update(Message("Example"))
        event.effective_user.language_code = language
        await bot.dispatch_search(event, ctx)
        await started.wait()
        msg = Message("Again")
        event = update(msg)
        event.effective_user.language_code = language
        await bot.dispatch_search(event, ctx)
        assert expected in msg.sent[-1]["text"]
        release.set()
        await bot.monitoring_close(ctx.application)

    asyncio.run(scenario())


@pytest.mark.parametrize("language", ["en", "ru"])
@pytest.mark.parametrize(
    "statuses,english,russian",
    [
        ([2], "Nothing found", "Ничего не нашёл"),
        ([2, 1], "Search incomplete", "Поиск неполный"),
        ([1], "temporarily unavailable", "временно недоступен"),
        (None, "status is unknown", "неизвестно"),
    ],
)
def test_empty_and_unavailable_search_feedback(
    bot, monkeypatch, language, statuses, english, russian
):
    card, ctx = start_in(bot, monkeypatch, language, SearchResults([], statuses=statuses))
    assert (english if language == "en" else russian) in card.text
    assert len(card.markup.inline_keyboard[0]) == 2
