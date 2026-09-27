import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from language_ui import LanguagePicker
from preferences import LanguageService, PreferenceStore
from tests.helpers import Message, context, update


def rig(tmp_path):
    store = PreferenceStore(tmp_path / "prefs.sqlite3")
    service = LanguageService(store)
    picker = LanguagePicker(service, lambda event: event.effective_user.id in {101, 202})
    ctx = context()
    ctx.application.bot = SimpleNamespace(set_my_commands=AsyncMock())
    return store, service, picker, ctx


def test_selection_is_persisted_and_menu_uses_override(tmp_path):
    store, service, picker, ctx = rig(tmp_path)

    async def scenario():
        msg = Message()
        event = update(msg)
        event.effective_chat.type = "private"
        event.effective_user.language_code = "ru"
        await picker.open(event, ctx)
        card = msg.replies[-1]
        assert "Выбери" in card.text
        data = card.markup.inline_keyboard[0][0].callback_data
        event = update(card, data)
        event.effective_chat.type = "private"
        event.callback_query.answer = AsyncMock()
        await picker.callback(event, ctx)
        assert service.for_user(101, "ru") == "en"
        assert card.text == "Language saved: English."
        assert {
            c.kwargs["language_code"] for c in ctx.application.bot.set_my_commands.call_args_list
        } == {"", "en", "ru"}
        assert all(
            c.kwargs["scope"].chat_id == 303
            for c in ctx.application.bot.set_my_commands.call_args_list
        )
        await picker.callback(event, ctx)
        assert service.for_user(101) == "en"

    asyncio.run(scenario())
    store.close()


@pytest.mark.parametrize("change", ["user", "revoked", "chat", "message", "expired"])
def test_language_buttons_reject_foreign_or_stale_selection(tmp_path, change):
    store, service, picker, ctx = rig(tmp_path)

    async def scenario():
        msg = Message()
        await picker.open(update(msg), ctx)
        card = msg.replies[-1]
        event = update(card, card.markup.inline_keyboard[0][0].callback_data)
        event.callback_query.answer = AsyncMock()
        if change == "user":
            event.effective_user.id = 202
        if change == "revoked":
            event.effective_user.id = 999
        if change == "chat":
            event.effective_chat.id = 404
        if change == "message":
            card.message_id += 1
        if change == "expired":
            ctx.user_data["language"]["expires"] = 0
        await picker.callback(event, ctx)
        assert store.get(101)["override"] is None
        assert store.get(202) is None

    asyncio.run(scenario())
    store.close()


def test_menu_failure_does_not_undo_saved_preference(tmp_path):
    from telegram.error import NetworkError

    store, service, picker, ctx = rig(tmp_path)
    ctx.application.bot.set_my_commands.side_effect = NetworkError("private diagnostic")

    async def scenario():
        msg = Message()
        await picker.open(update(msg), ctx)
        card = msg.replies[-1]
        event = update(card, card.markup.inline_keyboard[0][0].callback_data)
        event.effective_chat.type = "private"
        event.callback_query.answer = AsyncMock()
        await picker.callback(event, ctx)
        assert service.for_user(101) == "en"

    asyncio.run(scenario())
    store.close()


def test_real_start_defaults_to_english_without_telegram_language(bot):
    msg = Message()
    event = update(msg)
    event.effective_user.language_code = None
    ctx = context()
    asyncio.run(bot.cmd_start(event, ctx))
    assert msg.sent[-1]["text"].startswith("Hello!")
    assert any(
        b.callback_data == "nav:language"
        for row in msg.sent[-1]["reply_markup"].inline_keyboard
        for b in row
    )
    ctx.application.bot_data["languages"].store.close()


def test_group_choice_does_not_change_shared_command_menu(tmp_path):
    store, service, picker, ctx = rig(tmp_path)

    async def scenario():
        msg = Message()
        await picker.open(update(msg), ctx)
        card = msg.replies[-1]
        event = update(card, card.markup.inline_keyboard[0][0].callback_data)
        event.effective_chat.type = "group"
        event.callback_query.answer = AsyncMock()
        await picker.callback(event, ctx)
        assert service.for_user(101) == "en"
        ctx.application.bot.set_my_commands.assert_not_called()

    asyncio.run(scenario())
    store.close()


def test_expired_language_card_uses_saved_language_without_foreign_write(tmp_path):
    store, service, picker, ctx = rig(tmp_path)
    service.set_for_user(101, "ru")

    async def scenario():
        event = update(Message(), "lang:expired:en")
        event.callback_query.answer = AsyncMock()
        await picker.callback(event, ctx)
        assert "устарел" in event.callback_query.answer.call_args.args[0]
        assert store.get(202) is None

    asyncio.run(scenario())
    store.close()
