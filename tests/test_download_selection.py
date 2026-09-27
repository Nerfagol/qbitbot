"""Compact numbers select the displayed identity; deletion has one file policy."""

import pytest

from tests.helpers import torrent
from tests.test_downloads import click, setup
from tests.test_persistence import async_test


@async_test
async def test_numbers_match_titles_across_pages_and_return_to_same_page(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    library.rows = {
        f"{i:040x}": torrent(hash=f"{i:040x}", name=f"Film {i}", added_on=i) for i in range(10)
    }
    await dashboard.open(event, ctx)
    rows = message.markup.inline_keyboard
    assert [[b.text for b in row] for row in rows[:2]] == [
        ["1", "2", "3", "4"],
        ["5", "6", "7", "8"],
    ]
    for number, i in enumerate(range(9, 1, -1), 1):
        assert f"{number}. Film {i}\n" in message.text
    old_pick = message.button("1")
    await click(dashboard, event, ctx, message.button("Далее"))
    assert [b.text for b in message.markup.inline_keyboard[0]] == ["9", "10"]
    assert "9. Film 1\n" in message.text and "10. Film 0\n" in message.text
    ninth = message.button("9")
    library.rows[f"{8:040x}"]["state"] = "error"  # API order changes after rendering.
    await click(dashboard, event, ctx, ninth)
    assert "Film 1" in message.text
    await click(dashboard, event, ctx, message.button("Пауза"))
    assert library.actions == [("pause", f"{1:040x}")]
    await click(dashboard, event, ctx, message.button("← Загрузки"))
    assert "страница 2/2" in message.text
    await click(dashboard, event, ctx, old_pick)
    assert "устарела" in message.text
    assert len(library.actions) == 1


@async_test
async def test_detail_offers_only_delete_with_files(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    await dashboard.open(event, ctx)
    # Select by stored identity here so this regression isolates the deletion menu.
    token = next(iter(ctx.user_data["downloads"]["actions"]))
    await click(dashboard, event, ctx, token)
    labels = [b.text for row in message.markup.inline_keyboard for b in row]
    assert not any("Сохранить файлы" in label for label in labels)
    assert sum("Удалить торрент и файлы" in label for label in labels) == 1
    assert not library.actions


@async_test
@pytest.mark.parametrize("kind", ["ask_keep", "keep"])
async def test_retired_keep_actions_cannot_remove_torrents(bot, monkeypatch, kind):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    await dashboard.open(event, ctx)
    view = ctx.user_data["downloads"]
    token = next(iter(view["actions"]))
    _, target, page = view["actions"][token]
    view["actions"][token] = (kind, target, page)
    await click(dashboard, event, ctx, token)
    assert not library.actions
    assert not any(action[0] == "keep" for action in ctx.user_data["downloads"]["actions"].values())
