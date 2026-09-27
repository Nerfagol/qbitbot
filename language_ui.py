"""Owner-bound language selection and Telegram command descriptions."""

import secrets
import time

from telegram import BotCommand, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from i18n import tr, normalize_language

COMMANDS = ("search", "downloads", "status", "health", "help", "start", "language")


def command_list(language):
    return [BotCommand(name, tr("menu." + name, language)) for name in COMMANDS]


async def set_private_commands(bot, chat_id, language):
    try:
        for code in ("", "en", "ru"):
            await bot.set_my_commands(
                command_list(language), scope=BotCommandScopeChat(chat_id), language_code=code
            )
    except TelegramError as error:
        print("LANGUAGE MENU ERROR:", type(error).__name__)


class LanguagePicker:
    def __init__(self, service, allowed):
        self.service, self.allowed = service, allowed

    async def open(self, update, context):
        if not self.allowed(update):
            return
        user = update.effective_user.id
        language = self.service.for_user(
            user, getattr(update.effective_user, "language_code", None)
        )
        token = secrets.token_hex(8)
        context.user_data.pop("language", None)
        message = await update.message.reply_text(
            tr("language.prompt", language),
            parse_mode=None,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("English", callback_data=f"lang:{token}:en"),
                        InlineKeyboardButton("Русский", callback_data=f"lang:{token}:ru"),
                    ]
                ]
            ),
        )
        context.user_data["language"] = dict(
            user=user,
            chat=update.effective_chat.id,
            message=message.message_id,
            token=token,
            expires=time.monotonic() + 900,
        )

    async def callback(self, update, context):
        query = update.callback_query
        if not self.allowed(update):
            await query.answer()
            return
        session = context.user_data.get("language", {})
        parts = query.data.split(":")
        valid = (
            len(parts) == 3
            and parts[0] == "lang"
            and parts[1] == session.get("token")
            and parts[2] in ("en", "ru")
            and session.get("user") == update.effective_user.id
            and session.get("chat") == update.effective_chat.id
            and session.get("message") == query.message.message_id
            and time.monotonic() < session.get("expires", 0)
        )
        if not valid:
            # Do not create preferences for someone trying another owner's card.
            row = self.service.store.get(update.effective_user.id)
            language = normalize_language(
                (row["override"] or row["detected"])
                if row
                else getattr(update.effective_user, "language_code", None)
            )
            await query.answer(tr("language.expired", language), show_alert=True)
            return
        context.user_data.pop("language", None)
        language = parts[2]
        self.service.set_for_user(update.effective_user.id, language)
        await query.answer()
        await query.message.edit_text(
            tr("language.saved", language), reply_markup=None, parse_mode=None
        )
        if getattr(update.effective_chat, "type", None) == "private":
            await set_private_commands(context.application.bot, update.effective_chat.id, language)
