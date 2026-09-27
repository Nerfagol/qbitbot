"""Filters narrow fetched results without changing torrent identity or adding."""

import asyncio

import pytest

from tests.helpers import Message, update
from tests.test_search_ui import button, click, results, start

GIB = 1024**3


def choices():
    items = results(8)
    for item, name, size in zip(
        items,
        [
            "Film.720p",
            "Film.1080p.A",
            "Film.2160p",
            "Film.1080p.B",
            "Film.4K",
            "Film.Unknown",
            "Film.HDCAM.1080p",
            "Film.1080i",
        ],
        [2 * GIB, 5 * GIB, 10 * GIB, 10 * GIB + 1, 20 * GIB, None, GIB, GIB],
    ):
        item.update(title=name, size=size, seeders=30)
    return items


def test_combined_filters_preview_download_identity_and_reset(bot, monkeypatch):
    items = choices()
    message, ctx, add = start(bot, monkeypatch, items)
    expires = ctx.user_data["search"]["expires"]
    click(bot, message, ctx, "Фильтры")
    click(bot, message, ctx, "1080p")
    click(bot, message, ctx, "До 10 ГБ")
    assert "1 из 8" in message.text and "1080p" in message.text and "10 ГБ" in message.text
    assert "1. Film.1080p.A\n" in message.text
    assert "Film.1080p.B" not in message.text and "Film.HDCAM" not in message.text
    assert ctx.user_data["search"]["expires"] == expires
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "К результатам")
    assert "1 из 8" in message.text
    assert add.await_count == 0
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "Скачать")
    assert add.await_args.args[0] == items[1]["url"]
    click(bot, message, ctx, "К результатам")
    click(bot, message, ctx, "Сбросить фильтры")
    assert "8 результатов" in message.text


@pytest.mark.parametrize("value,label", [(5, "До 5 ГБ"), (10, "До 10 ГБ"), (20, "До 20 ГБ")])
def test_size_limit_is_inclusive_and_unknown_sizes_do_not_match(bot, monkeypatch, value, label):
    items = results(6)
    for item, size in zip(items, [value * GIB, value * GIB + 1, None, 0, -1, GIB]):
        item["size"] = size
    message, ctx, add = start(bot, monkeypatch, items)
    click(bot, message, ctx, "Фильтры")
    click(bot, message, ctx, label)
    assert "2 из 6" in message.text
    assert "Release 0" in message.text and "Release 5" in message.text
    assert all(f"Release {i}" not in message.text for i in range(1, 5))
    assert not add.await_count


def test_4k_filter_empty_combination_and_reset_recover_without_new_search(bot, monkeypatch):
    message, ctx, add = start(bot, monkeypatch, choices())
    monkeypatch.setattr(
        bot, "jackett_search_sync", lambda *args: pytest.fail("Filters must not query Jackett")
    )
    click(bot, message, ctx, "Фильтры")
    click(bot, message, ctx, "4K")
    assert "2 из 8" in message.text
    click(bot, message, ctx, "До 5 ГБ")
    assert "0 из 8" in message.text and "ничего" in message.text
    assert "1/0" not in message.text and "Нажми номер" not in message.text
    assert all(row for row in message.markup.inline_keyboard)
    assert not any(b.text.isdigit() for row in message.markup.inline_keyboard for b in row)
    click(bot, message, ctx, "Скрыть фильтры")
    assert "4K" in message.text and "5 ГБ" in message.text
    click(bot, message, ctx, "Сбросить фильтры")
    assert "8 результатов" in message.text and not add.await_count


def test_filter_resets_page_preserves_sort_and_filtered_numbering(bot, monkeypatch):
    items = results(14)
    for i, item in enumerate(items):
        item.update(title=f"Film.{'1080p' if i % 2 else '2160p'}.{i}", size=(i + 1) * GIB)
    message, ctx, add = start(bot, monkeypatch, items)
    click(bot, message, ctx, "Размер ↓")
    click(bot, message, ctx, "Далее")
    click(bot, message, ctx, "Фильтры")
    click(bot, message, ctx, "1080p")
    assert "Страница 1/2" in message.text and "Размер ↓" in message.text
    click(bot, message, ctx, "Далее")
    assert "6. Film.1080p.3" in message.text and "7. Film.1080p.1" in message.text
    click(bot, message, ctx, "6")
    click(bot, message, ctx, "К результатам")
    assert "Страница 2/2" in message.text
    click(bot, message, ctx, "6")
    click(bot, message, ctx, "Скачать")
    assert add.await_args.args[0] == items[3]["url"]


@pytest.mark.parametrize("mode", ["original", "recommended", "quality", "seeds", "small", "large"])
def test_every_sort_and_recommended_reservations_respect_filters(bot, monkeypatch, mode):
    from search_ui import quality

    _, ctx, _ = start(bot, monkeypatch, choices())
    session = ctx.user_data["search"]
    session.update(sort=mode, quality_filter="1080p", size_filter=10)
    indices = bot.search_browser().ordered(session)
    assert indices == [1]
    assert all(quality(session["results"][i]["title"])[1] == "1080p" for i in indices)


@pytest.mark.parametrize("bad", ["user", "chat", "message", "expired", "restart", "forged"])
def test_filter_actions_keep_existing_owner_and_expiry_guards(bot, monkeypatch, bad):
    message, ctx, add = start(bot, monkeypatch, choices())
    click(bot, message, ctx, "Фильтры")
    session = ctx.user_data["search"]
    event = update(message, button(message, "1080p"))
    if bad == "user":
        event.effective_user.id = 202
    elif bad == "chat":
        event.effective_chat.id = 404
    elif bad == "message":
        event.callback_query.message = Message(message_id=999)
    elif bad == "expired":
        session["expires"] = 0
    elif bad == "restart":
        ctx.user_data.clear()
    else:
        event.callback_query.data += "bad"
    asyncio.run(bot.on_pick(event, ctx))
    assert session.get("quality_filter", "any") == "any" and not add.await_count


def test_filter_invalidates_old_buttons_and_new_search_starts_unfiltered(bot, monkeypatch):
    message, ctx, add = start(bot, monkeypatch, choices())
    old = button(message, "1")
    click(bot, message, ctx, "Фильтры")
    click(bot, message, ctx, "1080p")
    asyncio.run(bot.on_pick(update(message, old), ctx))
    assert "устарел" in message.sent[-1]["text"] and not add.await_count
    new = Message("another title")
    asyncio.run(bot.on_text(update(new), ctx))
    assert "8 результатов" in new.replies[-1].text
    assert ctx.user_data["search"].get("quality_filter", "any") == "any"
