"""Search navigation must never mutate torrents before explicit confirmation."""

import asyncio
import re
from unittest.mock import AsyncMock

import pytest
import requests

from tests.helpers import Message, context, update


def results(count=12):
    return [
        {
            "title": f"Release {i}",
            "url": f"magnet:?xt=urn:btih:{i:040x}",
            "size": (count - i) * 1024,
            "seeders": count - i,
        }
        for i in range(count)
    ]


def button(message, label):
    # Resolve a release by its visible numbered text, just as a user would.
    for line in message.text.splitlines():
        match = re.fullmatch(r"(\d+)\. " + re.escape(label), line)
        if match:
            label = match[1]
            break
    return next(
        b.callback_data
        for row in message.markup.inline_keyboard
        for b in row
        if (b.text == label if label.isdigit() else label in b.text)
    )


def start(bot, monkeypatch, items=None):
    monkeypatch.setattr(bot, "jackett_search_sync", lambda *args: items or results())
    add = AsyncMock(return_value={"ok": False, "already_exists": True, "info": {}})
    monkeypatch.setattr(bot, "qbit_add_and_confirm", add)
    message, ctx = Message("example"), context()
    asyncio.run(bot.on_text(update(message), ctx))
    return message.replies[-1], ctx, add


def click(bot, message, ctx, label):
    if label in (
        "Источники",
        "Размер ↑",
        "Размер ↓",
        "Порядок поиска",
        "Качество",
        "Рекомендуемые",
    ):
        if not any(label in b.text for row in message.markup.inline_keyboard for b in row):
            click(bot, message, ctx, "Сортировка")
    asyncio.run(bot.on_pick(update(message, button(message, label)), ctx))


def test_page_preview_back_and_explicit_download(bot, monkeypatch):
    message, ctx, add = start(bot, monkeypatch)
    assert "1/3" in message.text
    assert "Release 4" in message.text and "Release 5" not in message.text
    click(bot, message, ctx, "Далее")
    assert "2/3" in message.text
    click(bot, message, ctx, "Release 7")
    assert "Release 7" in message.text
    assert add.await_count == 0
    click(bot, message, ctx, "К результатам")
    assert "2/3" in message.text
    click(bot, message, ctx, "Release 7")
    confirm = button(message, "Скачать")
    asyncio.run(bot.on_pick(update(message, confirm), ctx))
    asyncio.run(bot.on_pick(update(message, confirm), ctx))
    add.assert_awaited_once_with(results()[7]["url"], title_hint="Release 7")


@pytest.mark.parametrize("sort,expected", [("Источники", 0), ("Размер ↑", 11), ("Размер ↓", 0)])
def test_sort_keeps_original_torrent_identity(bot, monkeypatch, sort, expected):
    message, ctx, add = start(bot, monkeypatch)
    click(bot, message, ctx, sort)
    first = message.markup.inline_keyboard[0][0]
    assert first.text == "1"
    assert f"1. Release {expected}\n" in message.text
    asyncio.run(bot.on_pick(update(message, first.callback_data), ctx))
    assert add.await_count == 0
    click(bot, message, ctx, "Скачать")
    assert add.await_args.args[0] == results()[expected]["url"]


@pytest.mark.parametrize("mismatch", ["user", "chat", "message", "expired", "restart"])
def test_preview_confirmation_checks_owner_chat_message_and_age(bot, monkeypatch, mismatch):
    message, ctx, add = start(bot, monkeypatch)
    click(bot, message, ctx, "Release 0")
    event = update(message, button(message, "Скачать"))
    if mismatch == "user":
        bot.ALLOWED_USERS.add(202)
        event.effective_user.id = 202
    elif mismatch == "chat":
        event.effective_chat.id = 404
    elif mismatch == "message":
        event.callback_query.message = Message(message_id=999)
    elif mismatch == "expired":
        monkeypatch.setattr(bot.time, "monotonic", lambda: ctx.user_data["search"]["expires"] + 1)
    else:
        ctx.user_data.clear()
    asyncio.run(bot.on_pick(event, ctx))
    assert add.await_count == 0


def test_sort_invalidates_previous_selection_buttons(bot, monkeypatch):
    message, ctx, add = start(bot, monkeypatch)
    old = button(message, "Release 0")
    click(bot, message, ctx, "Источники")
    asyncio.run(bot.on_pick(update(message, old), ctx))
    assert add.await_count == 0
    assert "устарел" in message.sent[-1]["text"]


@pytest.mark.parametrize("empty", [False, True])
def test_failed_or_empty_search_preserves_previous_results(bot, monkeypatch, empty):
    message, ctx, add = start(bot, monkeypatch)

    def search(*args):
        if empty:
            return []
        raise requests.Timeout("https://private.invalid/?apikey=SECRET")

    monkeypatch.setattr(bot, "jackett_search_sync", search)
    new = Message("different")
    asyncio.run(bot.on_text(update(new), ctx))
    assert "SECRET" not in new.replies[-1].text
    assert "Изменить запрос" in str(new.replies[-1].markup)
    assert "Повторить" in str(new.replies[-1].markup)
    click(bot, message, ctx, "Release 0")
    click(bot, message, ctx, "Скачать")
    assert add.await_count == 1


def test_pending_message_is_replaced_and_retry_uses_failed_query(bot, monkeypatch):
    monkeypatch.setattr(bot, "jackett_search_sync", lambda *args: [])
    message, ctx = Message("specific query"), context()
    asyncio.run(bot.on_text(update(message), ctx))
    assert len(message.replies) == 1
    failure = message.replies[0]
    calls = []
    monkeypatch.setattr(
        bot, "jackett_search_sync", lambda query, limit: calls.append(query) or results()
    )
    click(bot, failure, ctx, "Повторить")
    assert calls == ["specific query"]
    assert "1/3" in failure.text


def test_deduplicates_hashes_but_not_equal_titles(bot, monkeypatch):
    items = results(3)
    items[1]["url"] = items[0]["url"] + "&dn=duplicate"
    items[2]["title"] = items[0]["title"]
    message, ctx, _ = start(bot, monkeypatch, items)
    assert len(ctx.user_data["search"]["results"]) == 2
    assert message.text.count("Release 0") == 2


def test_long_titles_are_bounded_plain_text_and_unknown_metadata_sorts_last(bot, monkeypatch):
    items = results(3)
    items[0].update(title="😀" * 5000, source="<indexer>", size=None, seeders=None)
    items[1]["seeders"] = 0
    message, ctx, _ = start(bot, monkeypatch, items)
    assert len(message.text.encode("utf-16-le")) // 2 < 4096
    click(bot, message, ctx, "Источники")
    assert "3. 😀" in message.text
    click(bot, message, ctx, "3")
    assert len(message.text.encode("utf-16-le")) // 2 < 4096
    assert "<indexer>" in message.text and "неизвестно" in message.text
    assert all(
        len(b.callback_data.encode()) <= 64 for row in message.markup.inline_keyboard for b in row
    )


def test_parser_keeps_indexer_name_and_rss_size_without_exposing_links(bot):
    items = bot.torznab_items("""<rss><channel><item><title>Example</title>
        <link>https://private.invalid/file?apikey=SECRET</link>
        <size>1024</size><jackettindexer id="test">Test indexer</jackettindexer>
        </item></channel></rss>""")
    assert items[0]["source"] == "Test indexer"
    assert items[0]["size"] == 1024


@pytest.mark.parametrize("size", [0, -1, None])
def test_zero_unknown_size_sorts_after_positive_sizes(bot, monkeypatch, size):
    items = results(3)
    items[0]["size"] = size
    message, ctx, _ = start(bot, monkeypatch, items)
    click(bot, message, ctx, "Размер ↑")
    assert "3. Release 0\n" in message.text
    click(bot, message, ctx, "3")
    assert "Release 0" in message.text


def test_change_query_keeps_retry_available(bot, monkeypatch):
    monkeypatch.setattr(bot, "jackett_search_sync", lambda *args: [])
    message, ctx = Message("query"), context()
    asyncio.run(bot.on_text(update(message), ctx))
    failure = message.replies[-1]
    click(bot, failure, ctx, "Изменить запрос")
    monkeypatch.setattr(bot, "jackett_search_sync", lambda *args: results())
    click(bot, failure, ctx, "Повторить")
    assert "1/3" in failure.text


def test_failed_telegram_edit_never_adds_or_replays_confirmation(bot, monkeypatch):
    from telegram.error import NetworkError

    message, ctx, add = start(bot, monkeypatch)
    click(bot, message, ctx, "Release 0")
    token = button(message, "Скачать")
    message.edit_text = AsyncMock(side_effect=NetworkError("SECRET"))
    asyncio.run(bot.on_pick(update(message, token), ctx))
    asyncio.run(bot.on_pick(update(message, token), ctx))
    assert add.await_count == 0
    assert "SECRET" not in str(message.sent)


def test_add_timeout_is_not_replayed_by_repeated_confirmation(bot, monkeypatch):
    message, ctx, add = start(bot, monkeypatch)
    add.side_effect = requests.Timeout("SECRET")
    click(bot, message, ctx, "Release 0")
    token = button(message, "Скачать")
    asyncio.run(bot.on_pick(update(message, token), ctx))
    asyncio.run(bot.on_pick(update(message, token), ctx))
    assert add.await_count == 1
    assert "SECRET" not in str(message.sent)
    assert "перед повторной" in message.text
    assert "SECRET" not in message.text


def test_optional_quality_then_seeds_and_numbered_buttons(bot, monkeypatch):
    items = results(7)
    names = [
        "Film.720p",
        "Film.1080p.A",
        "Film.2160p",
        "Film.1080p.B",
        "Film.4K",
        "Film.no.label",
        "Film.HDCAM.1080p",
    ]
    for item, name, seeds in zip(items, names, [900, 10, 2, 80, 30, 5000, 9000]):
        item.update(title=name, seeders=seeds)
    message, ctx, add = start(bot, monkeypatch, items)
    assert [b.text for b in message.markup.inline_keyboard[0]] == ["1", "2", "3", "4", "5"]
    assert len(message.markup.inline_keyboard) == 3
    click(bot, message, ctx, "Качество")
    assert message.text.index("Film.4K") < message.text.index("Film.2160p")
    assert message.text.index("Film.1080p.B") < message.text.index("Film.1080p.A")
    assert "Film.no.label" not in message.text and "Film.HDCAM" not in message.text
    assert all(icon in message.text for icon in ("🎬", "💾", "🟢"))
    click(bot, message, ctx, "3")
    assert "Film.1080p.B" in message.text
    assert "по названию" in message.text
    assert add.await_count == 0
    click(bot, message, ctx, "Скачать")
    assert add.await_args.args[0] == items[3]["url"]


def test_numbered_selection_on_later_page_and_sort_menu(bot, monkeypatch):
    message, ctx, add = start(bot, monkeypatch)
    click(bot, message, ctx, "Далее")
    assert [b.text for b in message.markup.inline_keyboard[0]] == ["6", "7", "8", "9", "10"]
    click(bot, message, ctx, "Сортировка")
    click(bot, message, ctx, "Размер ↑")
    assert len(message.markup.inline_keyboard) == 3
    click(bot, message, ctx, "2")
    assert "Release 10" in message.text
    click(bot, message, ctx, "Скачать")
    assert add.await_args.args[0] == results()[10]["url"]


@pytest.mark.parametrize(
    "title,label",
    [
        ("Film.2160p.WEB-DL", "4K"),
        ("Film_4k_HDR", "4K"),
        ("Film UHD", "4K"),
        ("Film 1080P BluRay", "1080p"),
        ("Film.1080i", "1080i"),
        ("Film.720p", "720p"),
        ("Film SD", "SD"),
        ("Film.480p", "480p"),
        ("Film.1080p.HDCAM", "CAM/TS"),
        ("Film.HDTS", "CAM/TS"),
        ("Film.1080p.HDTV", "1080p"),
        ("Film 2024", "—"),
        ("4Kids.Campaign", "—"),
        ("Film 1080", "—"),
    ],
)
def test_quality_labels_require_release_tokens(title, label):
    from search_ui import quality

    assert quality(title)[1] == label


@pytest.mark.parametrize(
    "title,label",
    [
        ("Concert.1080i.HDTV.ts", "1080i"),
        ("Film.2160p.BluRay.TS", "4K"),
        ("Film.1080p.ts", "1080p"),
        ("Film.TS.1080p", "CAM/TS"),
        ("Film.HDCAM.ts", "CAM/TS"),
    ],
)
def test_transport_stream_extension_does_not_mean_camera_recording(title, label):
    from search_ui import quality

    assert quality(title)[1] == label
