import asyncio

import pytest

from qbitbot.downloads import download_status
from tests.helpers import Message, context, torrent, update
from tests.test_downloads import setup, click


@pytest.mark.parametrize(
    "language,pause,confirm,finished",
    [
        ("en", "Pause", "Confirm deletion", "accepted file deletion"),
        ("ru", "Пауза", "Подтвердить удаление", "принял удаление файлов"),
    ],
)
def test_numbered_controls_pause_and_delete_in_each_language(
    bot, monkeypatch, language, pause, confirm, finished
):
    dashboard, library, msg, ctx, event = setup(bot, monkeypatch)
    monkeypatch.setattr(bot, "language_for_user", lambda user: language, raising=False)

    async def scenario():
        await dashboard.open(event, ctx)
        assert msg.markup.inline_keyboard[0][0].text == "1"
        await click(dashboard, event, ctx, msg.button("1"))
        await click(dashboard, event, ctx, msg.button(pause))
        assert library.actions == [("pause", "a" * 40)]
        await click(
            dashboard,
            event,
            ctx,
            msg.button(
                "Delete torrent and files" if language == "en" else "Удалить торрент и файлы"
            ),
        )
        token = msg.button(confirm)
        await click(dashboard, event, ctx, token)
        assert finished in msg.text
        await click(dashboard, event, ctx, token)
        assert library.actions.count(("delete", "a" * 40)) == 1
        assert not library.rows

    asyncio.run(scenario())


def test_language_switch_keeps_named_deletion_target(bot, monkeypatch):
    dashboard, library, msg, ctx, event = setup(bot, monkeypatch)
    language = ["ru"]
    monkeypatch.setattr(bot, "language_for_user", lambda user: language[0], raising=False)

    async def scenario():
        await dashboard.open(event, ctx)
        await click(dashboard, event, ctx, msg.button("1"))
        token = msg.button("Удалить торрент и файлы")
        language[0] = "en"
        await click(dashboard, event, ctx, token)
        assert "Test download" in msg.text and "Delete torrent and files?" in msg.text
        assert not library.actions
        await click(dashboard, event, ctx, msg.button("Confirm deletion"))
        assert library.actions == [("delete", "a" * 40)]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "state,expected",
    [
        ("metaDL", "file information"),
        ("checkingUP", "Checking files"),
        ("stoppedDL", "Paused"),
        ("queuedDL", "Queued"),
        ("error", "Download error"),
        ("missingFiles", "Files missing"),
    ],
)
def test_english_status_never_claims_100_percent_completion(state, expected):
    assert expected in download_status(torrent(state=state, progress=1), language="en")


def test_status_command_uses_selected_language(bot, monkeypatch):
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [torrent()])
    msg = Message()
    event = update(msg)
    event.effective_user.language_code = "en"
    asyncio.run(bot.cmd_status(event, context()))
    assert "Downloading" in msg.sent[-1]["text"] and "Test download" in msg.sent[-1]["text"]


@pytest.mark.parametrize("language,empty", [("en", "Nothing"), ("ru", "Сейчас ничего")])
def test_status_empty_is_localized(bot, monkeypatch, language, empty):
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [])
    msg = Message()
    event = update(msg)
    event.effective_user.language_code = language
    asyncio.run(bot.cmd_status(event, context()))
    assert empty in msg.sent[-1]["text"]
