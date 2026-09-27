"""Synthetic Telegram transport exercising real handlers inside the public image."""

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

sys.path.insert(0, "/app")
import tg_torrent_bot as bot  # noqa: E402
from fixtures import sample  # noqa: E402
from health import check_jackett  # noqa: E402
from setup_check import run_checks  # noqa: E402


class Card:
    def __init__(self):
        self.message_id = 1
        self.text = ""
        self.markup = None

    async def reply_text(self, text, **kwargs):
        self.message_id += 1
        return await self.edit_text(text, **kwargs)

    async def edit_text(self, text, **kwargs):
        self.text, self.markup = text, kwargs.get("reply_markup")
        return self

    async def click(self, label, handler, event, context):
        data = next(
            b.callback_data for row in self.markup.inline_keyboard for b in row if label in b.text
        )
        event.callback_query = SimpleNamespace(data=data, message=self, answer=AsyncMock())
        await handler(event, context)


async def exercise():
    checks = []
    assert all(result.ok for result in run_checks(bot._SETTINGS))
    checks.append("real qBittorrent and Jackett authenticated APIs; writable state")
    transport = SimpleNamespace(
        set_my_commands=AsyncMock(),
        set_chat_menu_button=AsyncMock(),
        edit_message_text=AsyncMock(),
        send_message=AsyncMock(return_value=SimpleNamespace(message_id=900)),
        pin_chat_message=AsyncMock(),
    )
    app = SimpleNamespace(bot=transport, bot_data={})
    fixture = sample("Generated fixture.bin")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if urlsplit(self.path).path == "/fixture.torrent":
                data = fixture["torrent"]
            else:
                data = b"""<rss xmlns:t="urn:torznab"><channel><item><title>Generated.fixture.2026.1080p.WEB-DL</title><link>http://127.0.0.1:8765/fixture.torrent</link><size>4096</size><t:attr name="seeders" value="30"/></item></channel></rss>"""
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_url = bot.JACKETT_TORZNAB_URL
    try:
        await bot.application_start(app)
        for user, lang, download, pause, resume, delete, confirm, completed in (
            (
                101,
                "en",
                "Download",
                "Pause",
                "Resume",
                "Delete torrent and files",
                "Confirm deletion",
                "System health",
            ),
            (
                202,
                "ru",
                "Скачать",
                "Пауза",
                "Продолжить",
                "Удалить торрент и файлы",
                "Подтвердить удаление",
                "Состояние системы",
            ),
        ):
            card = Card()
            event = SimpleNamespace(
                message=card,
                effective_user=SimpleNamespace(id=user, language_code=lang),
                effective_chat=SimpleNamespace(id=user, type="private"),
                callback_query=None,
            )
            context = SimpleNamespace(user_data={}, application=app)
            await bot.cmd_start(event, context)
            assert ("Hello!" if lang == "en" else "Привет!") in card.text
            await bot.cmd_health(event, context)
            assert completed in card.text
            # Only the search URL points to generated HTTP data; health uses real Jackett.
            bot.JACKETT_TORZNAB_URL = "http://127.0.0.1:8765/torznab"
            card.text = "generated fixture"
            await bot.on_text(event, context)
            await card.click("1", bot.on_pick, event, context)
            await card.click(download, bot.on_pick, event, context)
            assert bot.qbit_torrents_info_sync(hashes=fixture["hash"], limit=1)
            await bot.cmd_downloads(event, context)
            await card.click("1", bot.on_downloads, event, context)
            await card.click(pause, bot.on_downloads, event, context)
            await card.click(resume, bot.on_downloads, event, context)
            await card.click(delete, bot.on_downloads, event, context)
            assert "Generated fixture.bin" in card.text
            await card.click(confirm, bot.on_downloads, event, context)
            for _ in range(30):
                if not bot.qbit_torrents_info_sync(hashes=fixture["hash"], limit=1):
                    break
                await asyncio.sleep(0.2)
            assert not bot.qbit_torrents_info_sync(hashes=fixture["hash"], limit=1)
            bot.JACKETT_TORZNAB_URL = original_url
            checks.append(
                lang
                + " lifecycle, search, explicit add, numbered controls, pause/resume, confirmed file deletion, health"
            )
        # Read-only container paths must fail storage diagnostics without relaxing modes.
        from dataclasses import replace
        from pathlib import Path

        cfg = replace(bot._SETTINGS, watch_db_path=Path("/proc/qbitbot-test/watches.sqlite3"))
        assert any(r.message_key == "setup.storage" for r in run_checks(cfg))
        checks.append("state permission failure remains actionable")
    finally:
        bot.JACKETT_TORZNAB_URL = original_url
        await bot.monitoring_close(app)
        server.shutdown()
        server.server_close()
    return checks


if __name__ == "__main__":
    if sys.argv[1] == "outage":
        try:
            check_jackett(bot.JACKETT_TORZNAB_URL, bot.JACKETT_API_KEY)
        except Exception:
            print(json.dumps({"checks": ["dependency outage surfaced"]}))
        else:
            raise AssertionError("Expected unavailable dependency")
    else:
        print(json.dumps({"checks": asyncio.run(exercise())}))
