"""Readable release previews must not invent metadata or change the selected item."""

import asyncio

import pytest

from tests.helpers import Message, update
from tests.test_search_ui import button, click, results, start


@pytest.mark.parametrize(
    "field",
    [
        "Japanese / Subs: ENG",
        "Japanese / Субтитры RUS",
        "Japanese with English subtitles",
        "English commentary, no Russian audio",
    ],
)
def test_ambiguous_audio_fields_never_claim_languages(field):
    from search_ui import release_details

    assert release_details(f"Film.2024.1080p [Audio: {field}]")["audio"] is None


@pytest.mark.parametrize(
    "name,heading",
    [
        ("Space.Ranger.2049.1080p.BluRay", "Space Ranger 2049"),
        ("Class.of.1999.1080p.BluRay", "Class of 1999"),
        ("Show.2019-2024.1080p", "Show 2019-2024"),
    ],
)
def test_unbracketed_numbers_remain_title_text_not_asserted_years(name, heading):
    from search_ui import release_details

    assert release_details(name)["heading"] == heading


@pytest.mark.parametrize(
    "name,heading,episode",
    [
        (
            "Example.Bright.Adventures.2026.1080p.NF-New-Team.mkv",
            "Example Bright Adventures 2026",
            None,
        ),
        ("Пример / Example (2021) WEB-DL 1080p", "Пример / Example (2021)", None),
        ("2001.A.Test.Journey.1968.1080p", "2001 A Test Journey 1968", None),
        ("Space.Ranger.2049.2017.2160p", "Space Ranger 2049.2017", None),
        ("Pi.3.14.(2024).1080p", "Pi 3.14 (2024)", None),
        ("Show.Name.S02E03.1080p.WEB-DL", "Show Name", "Сезон 2 · Серия 3"),
        ("Show.Name.S02E03-E05.1080p", "Show Name", "Сезон 2 · Серии 3–5"),
        ("Show.Name.S02.1080p", "Show Name", "Сезон 2"),
        ("Show.Name.2024.S02E03.1080p", "Show Name 2024", "Сезон 2 · Серия 3"),
    ],
)
def test_extracts_only_clear_release_markers(name, heading, episode):
    from search_ui import release_details

    details = release_details(name)
    assert details["heading"] == heading
    assert details["episode"] == episode


@pytest.mark.parametrize(
    "name",
    [
        "1984",
        "1917",
        "Release 0",
        "Film.1080p.Balanced",
        "The.2020.Story",
        "Summer.of.1969.Live",
        "Show.S01-S03.1080p",
        "Show.S02E03E04.1080p",
        "S02E03",
        "<b>Unknown</b>",
    ],
)
def test_ambiguous_titles_are_preserved(name):
    from search_ui import release_details

    assert release_details(name)["heading"] == name


@pytest.mark.parametrize(
    "name,audio",
    [
        ("Film.2024.1080p [Audio: RUS / ENG]", "Русский, английский"),
        ("Фильм (2024) 1080p [Звук: русский]", "Русский"),
        ("Film.2024.1080p [Subtitles: RUS]", None),
        ("Film.2024.1080p.DUB.MULTi", None),
        ("English.Russian.Movie.2024.1080p", None),
        ("Film.2024.1080p [Audio: Japanese]", None),
    ],
)
def test_audio_requires_explicit_label_and_known_language(name, audio):
    from search_ui import release_details

    assert release_details(name)["audio"] == audio


def test_preview_readable_details_original_and_add_keep_filters_and_identity(bot, monkeypatch):
    items = results(1)
    original = "Example.Bright.Adventures.2026.1080p.NF-New-Team.mkv"
    items[0].update(title=original, source="Example tracker", size=5 * 1024**3)
    message, ctx, add = start(bot, monkeypatch, items)
    click(bot, message, ctx, "Фильтры")
    click(bot, message, ctx, "1080p")
    click(bot, message, ctx, "1")
    assert "Example Bright Adventures 2026" in message.text
    assert original not in message.text
    assert "Качество: Full HD" in message.text and "Трекер: Example tracker" in message.text
    assert "Аудио:" not in message.text
    click(bot, message, ctx, "Исходное название")
    assert original in message.text and not add.await_count
    assert not any("Скачать" in b.text for row in message.markup.inline_keyboard for b in row)
    click(bot, message, ctx, "К описанию")
    click(bot, message, ctx, "К результатам")
    assert "1 из 1" in message.text
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "Скачать")
    add.assert_awaited_once_with(items[0]["url"], title_hint=original)


def test_long_original_name_is_fully_accessible_in_bounded_plain_text_pages(bot, monkeypatch):
    items = results(1)
    original = "😀" * 4000 + "\n<b>TAIL</b>"
    items[0]["title"] = original
    message, ctx, add = start(bot, monkeypatch, items)
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "Исходное название")
    parts = []
    while True:
        assert len(message.text.encode("utf-16-le")) // 2 < 4096
        parts.append(message.text.split("\n\n", 1)[1])
        if not any("Далее" in b.text for row in message.markup.inline_keyboard for b in row):
            break
        click(bot, message, ctx, "Далее")
    assert "".join(parts) == original
    click(bot, message, ctx, "К описанию")
    assert len(message.text.encode("utf-16-le")) // 2 < 4096
    assert not add.await_count


@pytest.mark.parametrize("bad", ["user", "chat", "message", "expired", "restart", "old"])
def test_original_name_actions_use_same_session_guards(bot, monkeypatch, bad):
    message, ctx, add = start(bot, monkeypatch, results(1))
    click(bot, message, ctx, "1")
    event = update(message, button(message, "Исходное название"))
    if bad == "user":
        event.effective_user.id = 202
    elif bad == "chat":
        event.effective_chat.id = 404
    elif bad == "message":
        event.callback_query.message = Message(message_id=999)
    elif bad == "expired":
        ctx.user_data["search"]["expires"] = 0
    elif bad == "restart":
        ctx.user_data.clear()
    else:
        click(bot, message, ctx, "К результатам")
    asyncio.run(bot.on_pick(event, ctx))
    assert "📄 Исходное название" not in message.text
    assert not add.await_count
