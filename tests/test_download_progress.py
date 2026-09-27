import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.helpers import torrent

GIB = 1024**3


def test_progress_shows_status_bar_received_bytes_speed_and_eta(bot):
    text = bot.format_download_progress(
        torrent(total_size=2 * GIB, amount_left=GIB, dlspeed=1024**2, eta=90), language="ru"
    )
    assert "⬇️ Скачивается" in text and "50%" in text
    assert "▰" in text and "▱" in text
    assert "1.0GB из 2.0GB" in text
    assert "Скорость" in text and "Осталось" in text and "1 мин" in text
    assert "добавлено" not in text
    assert "Обновить" in text


@pytest.mark.parametrize(
    "state,label",
    [
        ("stoppedDL", "⏸ Приостановлено"),
        ("stalledDL", "⏳ Ожидание источников"),
        ("queuedDL", "🕓 В очереди"),
        ("metaDL", "Получение информации"),
        ("checkingDL", "🔍 Проверка файлов"),
        ("error", "❌ Ошибка"),
        ("missingFiles", "Файлы отсутствуют"),
    ],
)
def test_non_downloading_states_do_not_show_stale_remaining_time(bot, state, label):
    text = bot.format_download_progress(torrent(state=state, eta=90, dlspeed=1000), language="ru")
    assert label in text
    assert "1 мин" not in text and "90s" not in text
    assert "Скачивание завершено" not in text
    if state == "metaDL":
        assert "50%" not in text


def test_selected_bytes_and_unknown_size_are_not_invented(bot):
    info = torrent(total_size=10 * GIB, size=2 * GIB, amount_left=GIB)
    assert "1.0GB из 2.0GB" in bot.format_download_progress(info, language="ru")
    text = bot.format_download_progress(torrent(total_size=0, size=0, eta=8640000), language="ru")
    assert "Размер уточняется" in text and "100d" not in text


def test_checking_at_100_percent_is_not_finished(bot):
    info = torrent(state="checkingUP", progress=1, amount_left=0)
    text = bot.format_download_progress(info, language="ru")
    assert "Проверка файлов" in text and "Скачивание завершено" not in text
    info["state"] = "uploading"
    text = bot.format_download_progress(info, language="ru")
    assert "✅ Скачивание завершено" in text and "100%" in text
    assert "Осталось" not in text


def test_watcher_updates_state_even_when_percentage_is_unchanged(bot, monkeypatch):
    states = iter(
        [
            torrent(state="stoppedDL"),
            torrent(state="stalledDL"),
            torrent(state="uploading", progress=1, amount_left=0),
        ]
    )
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [next(states)])
    monkeypatch.setattr(bot, "WATCH_INTERVAL_SEC", 0)
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    asyncio.run(
        bot.watch_torrent_until_done(303, "a" * 40, "Example", 12, SimpleNamespace(bot=transport))
    )
    texts = [call.kwargs["text"] for call in transport.edit_message_text.call_args_list]
    assert "⏸ Приостановлено" in texts[0]
    assert "⏳ Ожидание источников" in texts[1]
    assert "✅ Скачивание завершено" in texts[-1]
    assert "Автообновление" in texts[0]
    transport.send_message.assert_awaited_once()


def test_completed_but_paused_distinguishes_download_from_seeding(bot):
    text = bot.format_download_progress(
        torrent(state="stoppedUP", progress=1, amount_left=0), language="ru"
    )
    assert "✅ Скачивание завершено" in text
    assert "Раздача приостановлена" in text
    assert "Осталось" not in text


def test_new_download_displays_zero_bytes_and_zero_speed(bot):
    text = bot.format_download_progress(
        torrent(progress=0, amount_left=1024, dlspeed=0), language="ru"
    )
    assert "Получено: 0B из 1.0KB" in text
    assert "Скорость: 0B/с" in text
    assert "Осталось: пока неизвестно" in text


def test_explicit_zero_selected_size_never_claims_full_torrent_downloaded(bot):
    text = bot.format_download_progress(
        torrent(size=0, total_size=1024, amount_left=0, progress=0), language="ru"
    )
    assert "Размер уточняется" in text
    assert "1.0KB из 1.0KB" not in text
