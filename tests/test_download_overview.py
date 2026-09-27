"""Overview groups reflect actual lifecycle without changing control targets."""

import pytest

from tests.helpers import torrent
from tests.test_download_health import sample_until
from tests.test_downloads import click, setup
from tests.test_persistence import async_test


@pytest.mark.parametrize(
    "state,progress,left,stalled,expected",
    [
        ("downloading", 0.5, 512, False, "active"),
        ("downloading", 0.5, 512, True, "attention"),
        ("metaDL", 0, 0, False, "active"),
        ("metaDL", 0, 0, True, "attention"),
        ("forcedMetaDL", 0, 0, False, "active"),
        ("stalledDL", 0.5, 512, False, "active"),
        ("stalledDL", 0.5, 512, True, "attention"),
        ("queuedDL", 0.5, 512, False, "active"),
        ("checkingUP", 1, 0, False, "active"),
        ("moving", 0.5, 512, False, "active"),
        ("stoppedDL", 0.5, 512, False, "paused"),
        ("pausedDL", 0.5, 512, False, "paused"),
        ("stoppedUP", 1, 0, False, "completed"),
        ("uploading", 1, 0, False, "completed"),
        ("stalledUP", 1, 0, False, "completed"),
        ("uploading", 1, 1, False, "active"),
        ("error", 1, 0, False, "attention"),
        ("missingFiles", 1, 0, False, "attention"),
        ("unknown", 0, 0, False, "attention"),
        (None, 0, 0, False, "attention"),
    ],
)
def test_lifecycle_groups_require_confirmed_completion(
    bot, state, progress, left, stalled, expected
):
    from qbitbot.downloads import download_group

    assert (
        download_group(
            torrent(state=state, progress=progress, amount_left=left), bot, stalled=stalled
        )
        == expected
    )


def mixed_library(library):
    states = ["uploading", "stoppedDL", "downloading", "error", "checkingUP"]
    library.rows = {
        f"{i:040x}": torrent(
            hash=f"{i:040x}",
            name=f"Item {i}",
            added_on=i,
            state=state,
            progress=1 if i in (0, 4) else 0.5,
            amount_left=0 if i in (0, 4) else 512,
        )
        for i, state in enumerate(states)
    }


@async_test
async def test_overview_counts_and_problem_first_order(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    mixed_library(library)
    await dashboard.open(event, ctx)
    text = message.text
    assert "Требует внимания: 1" in text
    assert "В процессе: 2" in text and "На паузе: 1" in text and "Завершено: 1" in text
    positions = [text.index(f"Item {i}\n") for i in (3, 4, 2, 1, 0)]
    assert positions == sorted(positions)
    assert not library.actions


@async_test
async def test_waiting_group_changes_only_after_observation_and_clears_on_recovery(
    bot, monkeypatch
):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    info = library.rows["a" * 40]
    info.update(state="metaDL", dlspeed=0)
    assert not sample_until(bot.DOWNLOAD_HEALTH, info, 240)
    await dashboard.open(event, ctx)
    assert "Требует внимания: 0" in message.text
    bot.DOWNLOAD_HEALTH.now = lambda: 300
    await click(dashboard, event, ctx, message.button("Обновить"))
    assert "Требует внимания: 1" in message.text and "ожидание ≥5 мин" in message.text
    info.update(state="downloading", dlspeed=1)
    await click(dashboard, event, ctx, message.button("Обновить"))
    assert "Требует внимания: 0" in message.text and "В процессе: 1" in message.text


@async_test
async def test_group_reordering_keeps_selected_target_and_pause_updates_counts(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    mixed_library(library)
    await dashboard.open(event, ctx)
    selected = message.button("3")
    library.rows[f"{0:040x}"].update(state="error")
    await click(dashboard, event, ctx, selected)
    assert "Item 2" in message.text
    await click(dashboard, event, ctx, message.button("Пауза"))
    assert library.actions == [("pause", f"{2:040x}")]
    await click(dashboard, event, ctx, message.button("← Загрузки"))
    assert "На паузе: 2" in message.text and "Требует внимания: 2" in message.text


@async_test
async def test_group_counts_cover_whole_library_and_headers_repeat_across_pages(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    library.rows = {
        f"{i:040x}": torrent(
            hash=f"{i:040x}", name=f"Item {i}", added_on=i, state="error" if i < 10 else "stoppedDL"
        )
        for i in range(18)
    }
    await dashboard.open(event, ctx)
    assert "1/3" in message.text and "Требует внимания: 10" in message.text
    await click(dashboard, event, ctx, message.button("Далее"))
    assert "2/3" in message.text and "На паузе: 8" in message.text
    assert "⚠️ Требует внимания\n" in message.text and "⏸ На паузе\n" in message.text
    await click(dashboard, event, ctx, message.button("Далее"))
    assert "3/3" in message.text and "⏸ На паузе\n" in message.text
    library.rows.clear()
    await click(dashboard, event, ctx, message.button("Обновить"))
    assert "1/1" in message.text and "Торрентов пока нет" in message.text
    assert "Требует внимания: 0" in message.text
