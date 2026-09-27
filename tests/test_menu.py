import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from tests.helpers import Message, context, update


def test_start_has_short_guide_and_navigation_buttons(bot):
    message = Message()
    asyncio.run(bot.cmd_start(update(message), context()))
    sent = message.sent[-1]
    assert len(sent["text"]) < 900
    assert "название" in sent["text"].lower()
    assert "загруз" in sent["text"].lower()
    assert "сохранить файлы" not in sent["text"].lower()
    actions = {b.callback_data for row in sent["reply_markup"].inline_keyboard for b in row}
    assert actions == {"nav:search", "nav:downloads", "nav:health", "nav:help"}


def test_registers_commands_and_native_menu(bot):
    transport = SimpleNamespace(set_my_commands=AsyncMock(), set_chat_menu_button=AsyncMock())
    asyncio.run(bot.configure_menu(SimpleNamespace(bot=transport)))
    commands = transport.set_my_commands.call_args.args[0]
    assert {command.command for command in commands} == {
        "start",
        "search",
        "downloads",
        "status",
        "health",
        "help",
    }
    assert transport.set_chat_menu_button.call_args.kwargs["menu_button"].type == "commands"


def test_search_prompt_leaves_next_text_as_normal_search(bot, monkeypatch):
    message = Message()
    ctx = context()
    search = []
    monkeypatch.setattr(bot, "jackett_search_sync", lambda query, limit: search.append(query) or [])
    asyncio.run(bot.cmd_search(update(message), ctx))
    assert not search
    assert "название" in message.sent[-1]["text"].lower()
    asyncio.run(bot.on_text(update(Message("Example 2026")), ctx))
    assert search == ["Example 2026"]


def test_navigation_opens_downloads_using_callback_message(bot, monkeypatch):
    message = Message()
    ctx = context()
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kwargs: [])
    event = update(message, "nav:downloads")
    event.message = None  # Real callback updates have no top-level message.
    asyncio.run(bot.on_navigation(event, ctx))
    assert "Торрентов пока нет" in message.sent[-1]["text"]
    assert "downloads" in ctx.user_data


def test_unauthorized_navigation_cannot_open_dashboard(bot, monkeypatch):
    monkeypatch.setattr(
        bot, "qbit_torrents_info_sync", lambda **kw: (_ for _ in ()).throw(AssertionError())
    )
    message = Message()
    asyncio.run(bot.on_navigation(update(message, "nav:downloads", user_id=999), context()))
    assert message.sent == []


def test_menu_network_failure_does_not_prevent_monitoring_start(bot, tmp_path, monkeypatch, capsys):
    from telegram.error import NetworkError

    monkeypatch.setattr(bot, "WATCH_DB_PATH", str(tmp_path / "menu-start.sqlite3"))
    app = SimpleNamespace(
        bot_data={},
        bot=SimpleNamespace(
            set_my_commands=AsyncMock(side_effect=NetworkError("https://private.invalid/token")),
            set_chat_menu_button=AsyncMock(),
        ),
    )

    async def scenario():
        await bot.application_start(app)
        assert "monitoring" in app.bot_data
        assert app.bot_data["monitoring"].store.unfinished() == []
        await bot.monitoring_close(app)

    asyncio.run(scenario())
    assert "private.invalid" not in capsys.readouterr().out
