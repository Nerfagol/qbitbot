import asyncio
from unittest.mock import AsyncMock

import pytest
from telegram.error import NetworkError

from tests.helpers import torrent
from tests.test_persistence import async_test, manager


@async_test
@pytest.mark.parametrize("state", ["error", "missingFiles", "unknown"])
@pytest.mark.parametrize("delivery_fails", [False, True])
async def test_torrent_error_recovers_to_completion_without_resubscription(
    bot, monkeypatch, tmp_path, state, delivery_fails
):
    m, telegram = manager(bot, tmp_path)
    states = iter(
        [
            torrent(state=state),
            torrent(state=state),
            torrent(),
            torrent(state="stalledUP", progress=1, amount_left=0),
        ]
    )
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [next(states)])
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    m.store.subscribe(101, 303, "a" * 40, "Example")
    m.store.set_message(303, "a" * 40, 77)
    if delivery_fails:
        telegram.edit_message_text.side_effect = [NetworkError("offline"), None, None, None]
    try:
        await m.restore()
        await asyncio.gather(*m.tasks.values())
        assert m.store.get(303, "a" * 40)["status"] == "completed"
        notices = [
            c
            for c in telegram.send_message.call_args_list
            if c.kwargs.get("text", "").startswith("Скачивание завершено:")
        ]
        assert len(notices) == 1
        assert telegram.edit_message_text.call_args.kwargs["message_id"] == 77
    finally:
        await m.close()


@async_test
@pytest.mark.parametrize("owner", [101, 999])
async def test_upgrade_restores_previous_error_subscriptions_only_for_allowed_owners(
    bot, monkeypatch, tmp_path, owner
):
    m, telegram = manager(bot, tmp_path)
    m.store.subscribe(owner, 303, "a" * 40, "Example")
    m.store.set_status(303, "a" * 40, "error")
    await m.close()
    m, telegram = manager(bot, tmp_path, telegram)
    monkeypatch.setattr(
        bot,
        "qbit_torrents_info_sync",
        lambda **kw: [torrent(state="stalledUP", progress=1, amount_left=0)],
    )
    try:
        await m.restore()
        await asyncio.gather(*m.tasks.values())
        assert m.store.get(303, "a" * 40)["status"] == ("completed" if owner == 101 else "revoked")
        if owner == 999:
            assert not telegram.send_message.called
    finally:
        await m.close()


@async_test
async def test_restart_during_error_keeps_original_progress_card(bot, monkeypatch, tmp_path):
    m, telegram = manager(bot, tmp_path)
    waiting = asyncio.Event()

    async def wait(seconds):
        waiting.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio, "sleep", wait)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [torrent(state="error")])
    m.store.subscribe(101, 303, "a" * 40, "Example")
    m.store.set_message(303, "a" * 40, 77)
    await m.restore()
    await asyncio.wait_for(waiting.wait(), 1)
    assert m.store.get(303, "a" * 40)["status"] == "active"
    await m.close()
    m, telegram = manager(bot, tmp_path, telegram)
    monkeypatch.setattr(
        bot,
        "qbit_torrents_info_sync",
        lambda **kw: [torrent(state="stalledUP", progress=1, amount_left=0)],
    )
    try:
        await m.restore()
        await asyncio.gather(*m.tasks.values())
        assert m.store.get(303, "a" * 40)["status"] == "completed"
        assert telegram.edit_message_text.call_args.kwargs["message_id"] == 77
    finally:
        await m.close()
