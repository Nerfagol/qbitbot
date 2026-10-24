"""Explicit environment loading, service composition and Telegram startup."""

import os
from pathlib import Path

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from qbitbot.clients.jackett import JackettClient, JackettConfig
from qbitbot.clients.qbittorrent import QBitClient, QBitConfig
from qbitbot.downloads import DownloadHealth
from qbitbot.settings import load_env, read_settings

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def load_runtime(env=None, env_path="bot.env"):
    """Load a private configuration copy; injected values keep precedence."""
    values = dict(os.environ if env is None else env)
    load_env(Path(env_path), values)
    return read_settings(values), values


def configure_handlers(settings, *, env=None, handlers=None):
    """Compose inert handlers explicitly without opening HTTP or SQLite resources."""
    if handlers is None:
        from qbitbot import app as handlers
    values = {} if env is None else env
    config = {
        "_SETTINGS": settings,
        "BOT_TOKEN": settings.bot_token,
        "ALLOWED_USERS": set(settings.allowed_users),
        "JACKETT_TORZNAB_URL": settings.jackett_url,
        "JACKETT_API_KEY": settings.jackett_key,
        "JACKETT_SEARCH_TIMEOUT_SEC": settings.search_timeout,
        "QBIT_URL": settings.qbit_url,
        "QBIT_HOST_HEADER": settings.qbit_host_header,
        "QBIT_USER": settings.qbit_user,
        "QBIT_PASS": settings.qbit_pass,
        "QBIT_SAVEPATH": settings.savepath,
        "QBIT_CATEGORY": settings.category,
        "WATCH_DB_PATH": str(settings.watch_db_path),
        "WATCH_INTERVAL_SEC": settings.watch_interval,
        "WATCH_MISSING_GRACE_SEC": settings.missing_grace,
        "DOWNLOAD_HEALTH": DownloadHealth(max_gap=max(90, 2 * settings.watch_interval)),
        "DIAG_REDACT": values.get("DIAG_REDACT", "1").lower() not in ("0", "false", "no"),
        "TORRENT_FETCH_TIMEOUT_SEC": settings.torrent_timeout,
        "TORRENT_FETCH_MAX_BYTES": settings.torrent_max_bytes,
        "TORRENT_FETCH_USER_AGENT": values.get("TORRENT_FETCH_USER_AGENT", DEFAULT_USER_AGENT),
        "LAST_SEARCH_HEALTH": None,
        "_QBIT_CLIENT": QBitClient(
            QBitConfig(
                settings.qbit_url,
                settings.qbit_user,
                settings.qbit_pass,
                host_header=settings.qbit_host_header,
                savepath=settings.savepath,
                category=settings.category,
            )
        ),
        "_JACKETT_CLIENT": JackettClient(
            JackettConfig(
                settings.jackett_url,
                settings.jackett_key,
                settings.search_timeout,
            )
        ),
    }
    for name, value in config.items():
        setattr(handlers, name, value)
    return handlers


def build_application(settings, *, env=None, handlers=None):
    handlers = configure_handlers(settings, env=env, handlers=handlers)
    values = {} if env is None else env
    builder = ApplicationBuilder().token(settings.bot_token)
    if values.get("PTB_USE_AIOHTTP", "1").lower() not in ("0", "false", "no"):
        try:
            from ptbcontrib.aiohttp_request import AiohttpRequest

            request = AiohttpRequest()
            builder = builder.request(request).get_updates_request(request)
            print("✅ Using AiohttpRequest backend (ptbcontrib).")
        except Exception as error:
            raise RuntimeError(
                "PTB_USE_AIOHTTP=1 requires ptbcontrib.aiohttp_request.\n"
                "Install the optional dependencies:\n"
                "  pip install aiohttp\n"
                "  pip install git+https://github.com/python-telegram-bot/ptbcontrib.git@main\n"
                f"Error type: {type(error).__name__}"
            ) from None
    builder = (
        builder.post_init(handlers.application_start)
        .post_stop(handlers.monitoring_stop)
        .post_shutdown(handlers.monitoring_close)
    )
    application = builder.build()
    for command in ("language", "start", "help", "search", "status", "health", "downloads"):
        application.add_handler(CommandHandler(command, getattr(handlers, "cmd_" + command)))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.dispatch_search)
    )
    for pattern, callback in (
        (r"^lang:", handlers.on_language),
        (r"^nav:", handlers.on_navigation),
        (r"^dl:", handlers.on_downloads),
        (r"^health:", handlers.on_health),
        (r"^go:", handlers.on_torrent_link),
    ):
        application.add_handler(CallbackQueryHandler(callback, pattern=pattern))
    application.add_handler(CallbackQueryHandler(handlers.dispatch_pick))
    application.add_error_handler(handlers.on_error)
    return application


def main():
    settings, values = load_runtime()
    build_application(settings, env=values).run_polling()
