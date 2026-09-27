"""Observed inactivity, honest peer feedback and recovery in real watch loops."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import requests

from tests.helpers import torrent


def sample_until(health, info, end=300, start=0):
    result = False
    for now in range(start, end + 1, 60):
        health.now = lambda: now
        result = health.observe(info)
    return result


@pytest.mark.parametrize(
    "state", ["metaDL", "forcedMetaDL", "stalledDL", "downloading", "forcedDL"]
)
def test_warning_requires_five_minutes_of_observed_inactivity(bot, state):
    health = bot.DOWNLOAD_HEALTH
    info = torrent(state=state, dlspeed=0, num_seeds=0, num_leechs=0)
    assert not sample_until(health, info, 240)
    health.now = lambda: 299
    assert not health.observe(info)
    health.now = lambda: 300
    assert health.observe(info)


@pytest.mark.parametrize(
    "change", [{"downloaded": 1}, {"amount_left": 511}, {"progress": 0.50001}, {"dlspeed": 1}]
)
def test_even_small_transfer_clears_warning(bot, change):
    health = bot.DOWNLOAD_HEALTH
    info = torrent(dlspeed=0, downloaded=0)
    assert sample_until(health, info)
    health.now = lambda: 301
    assert not health.observe({**info, **change})


@pytest.mark.parametrize(
    "state",
    [
        "stoppedDL",
        "pausedDL",
        "queuedDL",
        "checkingDL",
        "checkingUP",
        "uploading",
        "error",
        "missingFiles",
    ],
)
def test_other_states_do_not_accumulate_inactivity(bot, state):
    health = bot.DOWNLOAD_HEALTH
    assert not sample_until(health, torrent(state=state, dlspeed=0))
    health.now = lambda: 301
    assert not health.observe(torrent(dlspeed=0))


@pytest.mark.parametrize(
    "change", [{"added_on": 999}, {"name": "Replacement"}, {"state": "downloading"}]
)
def test_new_identity_or_metadata_transition_starts_fresh(bot, change):
    health = bot.DOWNLOAD_HEALTH
    info = torrent(state="metaDL", dlspeed=0)
    assert sample_until(health, info)
    health.now = lambda: 301
    assert not health.observe({**info, **change})


def test_gap_and_explicit_failure_reset_observation(bot):
    health = bot.DOWNLOAD_HEALTH
    info = torrent(dlspeed=0)
    assert sample_until(health, info)
    health.now = lambda: 600
    assert not health.observe(info)
    assert sample_until(health, info, start=660, end=900)
    health.forget(info["hash"])
    health.now = lambda: 901
    assert not health.observe(info)


@pytest.mark.parametrize(
    "counts,expected",
    [
        ({}, "Число подключённых источников неизвестно"),
        ({"num_seeds": 0, "num_leechs": 0}, "Нет подключённых источников"),
        ({"num_seeds": 0, "num_leechs": 2}, "Подключённых источников: 2"),
    ],
)
def test_warning_reports_connected_peers_without_guessing_network_cause(bot, counts, expected):
    text = bot.format_download_progress(torrent(state="metaDL", **counts), stalled=True)
    assert "5 минут" in text and expected in text
    assert "интернет не работает" not in text
    assert "0%" not in text
    text = bot.format_download_progress(torrent(dlspeed=0, **counts), stalled=True)
    assert "Нет прогресса скачивания" in text


def test_watcher_edits_one_warning_then_recovers_and_completes(bot, monkeypatch):
    clock = [0]
    health = bot.DOWNLOAD_HEALTH
    health.now = lambda: clock[0]
    snapshots = [torrent(state="metaDL", dlspeed=0, num_seeds=0, num_leechs=0)] * 8
    snapshots += [torrent(dlspeed=12), torrent(state="uploading", progress=1, amount_left=0)]
    samples = iter(snapshots)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [next(samples)])

    async def sleep(_):
        clock[0] += 60

    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    asyncio.run(
        bot.watch_torrent_until_done(303, "a" * 40, "Test", 12, SimpleNamespace(bot=transport))
    )
    edits = transport.edit_message_text.call_args_list
    warnings = [call for call in edits if "5 минут" in call.kwargs["text"]]
    assert len(warnings) == 1
    assert warnings[0].kwargs["reply_markup"].inline_keyboard[0][0].callback_data == "nav:downloads"
    assert "Скачивается" in edits[-2].kwargs["text"]
    assert "5 минут" not in edits[-2].kwargs["text"]
    transport.send_message.assert_awaited_once()


def test_outage_does_not_count_as_observed_stall(bot, monkeypatch):
    health = bot.DOWNLOAD_HEALTH
    clock = [0]
    health.now = lambda: clock[0]
    waiting = torrent(state="metaDL", dlspeed=0)
    samples = iter(
        [waiting] * 5
        + [requests.ConnectionError()]
        + [waiting] * 3
        + [torrent(state="uploading", progress=1, amount_left=0)]
    )

    def read(**kw):
        result = next(samples)
        if isinstance(result, Exception):
            raise result
        return [result]

    async def sleep(_):
        clock[0] += 60

    monkeypatch.setattr(bot, "qbit_torrents_info_sync", read)
    monkeypatch.setattr(bot.asyncio, "sleep", sleep)
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    asyncio.run(
        bot.watch_torrent_until_done(303, "a" * 40, "Test", 12, SimpleNamespace(bot=transport))
    )
    texts = [call.kwargs["text"] for call in transport.edit_message_text.call_args_list]
    assert any("Связь" in text for text in texts)
    assert not any("5 минут" in text for text in texts)
