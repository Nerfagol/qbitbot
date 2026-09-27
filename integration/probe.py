"""Run inside the bot image against disposable qBittorrent and local HTTP fixtures."""

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import requests

sys.path.insert(0, "/app")
os.environ.update(json.loads(Path("/tmp/verification-config.json").read_text()))
spec = importlib.util.spec_from_file_location("bot", "/app/tg_torrent_bot.py")
bot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bot)


def passed(name):
    print("PASS " + name, flush=True)


def bencode(value):
    if isinstance(value, int):
        return b"i" + str(value).encode() + b"e"
    if isinstance(value, bytes):
        return str(len(value)).encode() + b":" + value
    if isinstance(value, dict):
        return b"d" + b"".join(bencode(k) + bencode(v) for k, v in sorted(value.items())) + b"e"
    raise TypeError(type(value))


def fixture(name):
    payload = b"Locally generated qbitbot verification data.\n" * 256
    Path("/downloads", name).write_bytes(payload)
    info = {
        b"name": name.encode(),
        b"length": len(payload),
        b"piece length": 16384,
        b"pieces": hashlib.sha1(payload).digest(),
        b"private": 1,
    }
    return bencode({b"info": info}), hashlib.sha1(bencode(info)).hexdigest()


def wait_for(predicate, label, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        time.sleep(0.2)
    raise AssertionError("Timed out: " + label)


def info(t_hash):
    rows = bot.qbit_torrents_info_sync(hashes=t_hash, limit=1)
    return rows[0] if rows else None


def api(method, endpoint, **kwargs):
    response = bot.qbit_session().request(
        method, bot.QBIT_URL + "/api/v2/" + endpoint, timeout=10, **kwargs
    )
    response.raise_for_status()
    return response


class DashboardProbe:
    """Drive real Telegram handlers; record only the Telegram transport boundary."""

    def __init__(self):
        self.message_id = 700
        self.text = ""
        self.markup = None
        self.context = SimpleNamespace(user_data={}, application=SimpleNamespace(bot_data={}))
        self.update = SimpleNamespace(
            message=self,
            effective_user=SimpleNamespace(id=101, language_code="ru"),
            effective_chat=SimpleNamespace(id=101),
            callback_query=None,
        )

    async def reply_text(self, text, reply_markup=None, **kwargs):
        self.text, self.markup = text, reply_markup
        return self

    async def edit_text(self, text, reply_markup=None, **kwargs):
        return await self.reply_text(text, reply_markup)

    async def click(self, label, handler=None):
        data = next(
            button.callback_data
            for row in self.markup.inline_keyboard
            for button in row
            if label in button.text
        )
        self.update.callback_query = SimpleNamespace(
            message=self,
            data=data,
            answer=AsyncMock(),
        )
        await (handler or bot.on_downloads)(self.update, self.context)

    async def pick(self, name):
        number = next(
            match.group(1)
            for line in self.text.splitlines()
            if (match := re.match(r"^(\d+)\. (.*)$", line)) and match.group(2) == name
        )
        assert all(len(row) <= 4 for row in self.markup.inline_keyboard)
        await self.click(number)
        assert name in self.text

    async def select(self, name):
        await bot.cmd_downloads(self.update, self.context)
        await self.pick(name)

    async def pause_resume(self):
        await self.select("uploaded.txt")
        await self.click("Пауза")
        assert "Раздача приостановлена" in self.text, self.text
        await self.click("← Загрузки")
        completed = sum(bot.is_completed(row) for row in bot.qbit_torrents_info_sync(limit=None))
        assert completed > 0 and f"Завершено: {completed}" in self.text
        assert "На паузе: 0" in self.text  # Paused seeding is still a completed download.
        await self.pick("uploaded.txt")
        await self.click("Продолжить")
        assert "Изменение подтверждено" in self.text, self.text

    async def delete(self, name, t_hash):
        from monitoring import WatchManager
        from watch_store import WatchStore

        store = WatchStore(bot.WATCH_DB_PATH)
        store.subscribe(101, 101, t_hash, name)
        manager = WatchManager(bot, None, store)
        self.context.application.bot_data["monitoring"] = manager
        try:
            await self.select(name)
            assert not any(
                "Сохранить файлы" in b.text for row in self.markup.inline_keyboard for b in row
            )
            await self.click("Удалить торрент и файлы")
            assert "Файлы будут удалены" in self.text
            await self.click("Отмена")
            assert info(t_hash), "Cancellation must preserve the torrent"
            await self.click("Удалить торрент и файлы")
            assert info(t_hash), "Confirmation must precede deletion"
            await self.click("Подтвердить")
            assert info(t_hash) is None, self.text
            assert store.get(101, t_hash)["status"] == "missing"
        finally:
            await manager.close()
            self.context.application.bot_data.clear()


def main():
    mode = sys.argv[1]
    if mode == "outage":
        try:
            asyncio.run(asyncio.to_thread(bot.qbit_torrents_info_sync))
        except requests.ConnectionError:
            passed("real API outage is surfaced by the low-level client")
            return
        raise AssertionError("Expected connection failure while disposable service is stopped")

    version = api("GET", "app/version").text
    assert version == "v5.1.2", version
    passed("qBittorrent 5.1.2 authentication and version")
    if mode.startswith("watch-"):
        from watch_store import WatchStore

        saved = json.loads(Path("/downloads/sentinel.json").read_text())
        if mode == "watch-seed":
            store = WatchStore(bot.WATCH_DB_PATH)
            store.subscribe(101, 101, saved["hash"], saved["name"])
            store.set_message(101, saved["hash"], 55)
            store.subscribe(101, 202, saved["hash"], saved["name"])
            markup = bot.torrent_navigation(info(saved["hash"]), 101, 202, label="Подробнее")
            store.pending(202, saved["hash"], "Recovered pending completion", markup.to_dict())
            passed("committed active and pending watches before abrupt process exit")
            os._exit(0)  # Deliberately bypass shutdown/close: next container must recover.

        async def recover():
            transport = SimpleNamespace(
                edit_message_text=AsyncMock(),
                send_message=AsyncMock(return_value=SimpleNamespace(message_id=66)),
            )
            app = SimpleNamespace(
                bot=transport,
                bot_data={
                    "languages": SimpleNamespace(
                        for_user=lambda user: "ru", store=SimpleNamespace(close=lambda: None)
                    )
                },
            )
            await bot.monitoring_start(app)
            manager = app.bot_data["monitoring"]
            try:
                if mode == "watch-restore":
                    assert len(manager.tasks) == 2
                    await asyncio.wait_for(asyncio.gather(*manager.tasks.values()), timeout=10)
                    assert transport.send_message.call_count == 2
                    texts = [call.kwargs["text"] for call in transport.send_message.call_args_list]
                    assert any("Скачивание завершено" in text for text in texts)
                    assert "Recovered pending completion" in texts
                    pending = next(
                        call.kwargs
                        for call in transport.send_message.call_args_list
                        if call.kwargs["text"] == "Recovered pending completion"
                    )
                    assert (
                        pending["reply_markup"]
                        .inline_keyboard[0][0]
                        .callback_data.startswith("go:")
                    )
                    passed(
                        "new container restores active watch from live API and saved pending notice"
                    )
                else:
                    assert not manager.tasks
                    assert transport.send_message.call_count == 0
                    passed("later container restart does not repeat delivered completion notices")
                assert not manager.store.unfinished()
            finally:
                await bot.monitoring_stop(app)
                await bot.monitoring_close(app)

        asyncio.run(recover())
        return

    if mode == "reconnect":
        saved = json.loads(Path("/downloads/sentinel.json").read_text())
        assert info(saved["hash"])
        assert Path("/downloads", saved["name"]).read_bytes() == saved["payload"].encode()
        passed("client reconnect and torrent/data persistence after qBittorrent restart")
        return

    api(
        "POST",
        "app/setPreferences",
        data={
            "json": json.dumps(
                {
                    "dht": False,
                    "pex": False,
                    "lsd": False,
                    "queueing_enabled": False,
                    "save_path": "/downloads/",
                    "temp_path_enabled": False,
                }
            )
        },
    )
    file_bytes, file_hash = fixture("uploaded.txt")
    http_bytes, http_hash = fixture("http-added.txt")
    sentinel_bytes, sentinel_hash = fixture("retained.txt")
    concurrent_bytes, concurrent_hash = fixture("concurrent.txt")
    slow_search_entered, slow_search_release = threading.Event(), threading.Event()
    slow_search = {"enabled": False}

    retry_probe = {"failures": 0}
    search_health = {"mode": "partial"}
    health_probe = {"failed": False, "calls": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if parse_qs(urlsplit(self.path).query).get("t") == ["caps"]:
                health_probe["calls"] += 1
                self.send_response(503 if health_probe["failed"] else 200)
                self.end_headers()
                self.wfile.write(
                    b"SECRET" if health_probe["failed"] else b"<caps><searching/></caps>"
                )
                return
            if urlsplit(self.path).path == "/api/v2.0/indexers/all/results":
                if search_health["mode"] == "error":
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b"private diagnostic SECRET")
                    return
                body = json.dumps(
                    {
                        "Indexers": [
                            {"Status": 2},
                            {
                                "Status": 1 if search_health["mode"] == "partial" else 2,
                                "Error": "private diagnostic SECRET",
                            },
                        ],
                        "Results": [
                            {
                                "Title": "Local.fixture.2026.1080p",
                                "Link": "http://fixtures:8765/test.torrent",
                                "Size": 11008,
                                "Seeders": 30,
                                "Tracker": "Local fixture",
                            }
                        ],
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/transient":
                retry_probe["failures"] += 1
                self.send_response(503)
                self.end_headers()
                return
            if urlsplit(self.path).path == "/torznab":
                if slow_search["enabled"]:
                    slow_search_entered.set()
                    if not slow_search_release.wait(15):
                        self.send_error(504)
                        return
                body = b"""<rss xmlns:t="urn:torznab"><channel><item>
                <title>Local.fixture.2026.1080p.WEB-DL</title><link>http://fixtures:8765/test.torrent</link>
                <t:attr name="size" value="11008"/><t:attr name="seeders" value="1"/>
                </item></channel></rss>"""
                content_type = "application/xml"
            elif self.path == "/test.torrent":
                body, content_type = http_bytes, "application/x-bittorrent"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("0.0.0.0", 8765), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        results = asyncio.run(asyncio.to_thread(bot.jackett_search_sync, "fixture"))
        assert len(results) == 1 and results[0]["title"] == "Local.fixture.2026.1080p.WEB-DL"
        passed("Torznab search/parser over real HTTP with real asyncio.to_thread")

        bot.qbit_add_file_sync(file_bytes, "test.torrent")
        wait_for(lambda: info(file_hash), "uploaded torrent appears")
        wait_for(lambda: info(file_hash)["progress"] == 1, "local payload hash check")
        passed("multipart torrent-file upload and payload verification")

        before = len(bot.qbit_torrents_info_sync(limit=None))
        result = asyncio.run(bot.qbit_add_and_confirm("magnet:?xt=urn:btih:" + file_hash))
        assert result["already_exists"] and not result["ok"]
        assert len(bot.qbit_torrents_info_sync(limit=None)) == before
        passed("duplicate magnet detection without a second torrent")

        async def responsive_search():
            probe, controls = DashboardProbe(), DashboardProbe()
            controls.context = probe.context
            probe.text = "fixture"
            slow_search["enabled"] = True
            try:
                await bot.dispatch_search(probe.update, probe.context)
                assert await asyncio.to_thread(slow_search_entered.wait, 5)
                await asyncio.wait_for(bot.cmd_downloads(controls.update, controls.context), 5)
                assert "downloads" in controls.context.user_data
                await asyncio.wait_for(controls.pause_resume(), 8)
                assert probe.context.application.bot_data["search_jobs"].tasks
                slow_search_release.set()
                await asyncio.gather(
                    *probe.context.application.bot_data["search_jobs"].tasks.values()
                )
                assert "Страница 1/1" in probe.text
            finally:
                slow_search_release.set()
                slow_search["enabled"] = False
                await bot.monitoring_stop(probe.context.application)

        asyncio.run(responsive_search())
        passed("Downloads remains responsive while a real threaded HTTP search waits")

        async def search_and_confirm():
            probe = DashboardProbe()
            probe.text = "fixture"
            subscription = AsyncMock()
            probe.context.application.bot_data["monitoring"] = SimpleNamespace(
                subscribe=subscription
            )
            await bot.on_text(probe.update, probe.context)
            assert "Страница 1/1" in probe.text
            await probe.click("Фильтры", bot.on_pick)
            await probe.click("4K", bot.on_pick)
            assert "0 из 1" in probe.text and "ничего" in probe.text
            assert info(http_hash) is None
            await probe.click("Сбросить фильтры", bot.on_pick)
            await probe.click("До 10 ГБ", bot.on_pick)
            assert "1 из 1" in probe.text
            assert info(http_hash) is None
            await probe.click("Сортировка", bot.on_pick)
            await probe.click("Источники", bot.on_pick)
            await probe.click("1", bot.on_pick)
            assert "Добавить этот торрент" in probe.text
            assert "Local fixture 2026" in probe.text
            assert "Качество: Full HD" in probe.text
            await probe.click("Исходное название", bot.on_pick)
            assert "Local.fixture.2026.1080p.WEB-DL" in probe.text
            assert info(http_hash) is None
            await probe.click("К описанию", bot.on_pick)
            assert info(http_hash) is None  # Preview and sorting cannot add anything.
            await probe.click("К результатам", bot.on_pick)
            await probe.click("1", bot.on_pick)
            original_upload = bot.qbit_add_file_sync
            entered, release = threading.Event(), threading.Event()

            def concurrent_upload(data, name):
                # Simulate another client adding while this addition is in flight.
                original_upload(concurrent_bytes, "concurrent.torrent")
                entered.set()
                if not release.wait(15):
                    raise RuntimeError("Test upload barrier timed out")
                return original_upload(data, name)

            bot.qbit_add_file_sync = concurrent_upload
            try:
                await probe.click("Скачать", bot.dispatch_pick)
                assert await asyncio.to_thread(entered.wait, 5)
                controls = DashboardProbe()
                controls.context = probe.context
                await asyncio.wait_for(bot.cmd_downloads(controls.update, controls.context), 5)
                assert "downloads" in controls.context.user_data
                await asyncio.wait_for(controls.pause_resume(), 8)
                release.set()
                await asyncio.gather(
                    *probe.context.application.bot_data["search_jobs"].tasks.values()
                )
            finally:
                release.set()
                bot.qbit_add_file_sync = original_upload
                await probe.context.application.bot_data["search_jobs"].stop()
            assert info(http_hash)
            assert "✅ Добавлено в загрузки" in probe.text
            assert "Открыть эту загрузку" in str(probe.markup)
            subscription.assert_awaited_once_with(101, 101, http_hash, "http-added.txt")
            download_query = probe.update.callback_query
            await probe.click("Открыть эту загрузку", bot.on_pick)
            assert "http-added.txt" in probe.text and "Пауза" in str(probe.markup)
            # A repeated Download callback must not execute the add again.
            probe.update.callback_query = download_query
            await bot.on_pick(probe.update, probe.context)
            assert "устарел" in probe.text
            assert {row["hash"] for row in bot.qbit_torrents_info_sync(limit=None)} == {
                file_hash,
                http_hash,
                concurrent_hash,
            }

        asyncio.run(search_and_confirm())
        passed(
            "Search filters/readable preview/original/back preserve identity; only explicit Download adds via HTTP"
        )

        duplicate_http = asyncio.run(bot.qbit_add_and_confirm("http://fixtures:8765/test.torrent"))
        assert duplicate_http["already_exists"] and duplicate_http["hash"] == http_hash
        assert info(concurrent_hash)
        bot.qbit_control_sync("delete", concurrent_hash)
        wait_for(lambda: info(concurrent_hash) is None, "concurrent fixture removed")
        passed(
            "HTTP file identity ignores concurrent additions, detects duplicates and keeps controls responsive"
        )

        class ReplyProbe(DashboardProbe):
            def __init__(self):
                super().__init__()
                self.replies = []

            async def reply_text(self, text, reply_markup=None, **kwargs):
                reply = ReplyProbe()
                reply.context = self.context
                reply.message_id = self.message_id + 1 + len(self.replies)
                reply.text, reply.markup = text, reply_markup
                self.replies.append(reply)
                return reply

            async def edit_text(self, text, reply_markup=None, **kwargs):
                self.text, self.markup = text, reply_markup
                return self

        async def partial_search_retry():
            original_url = bot.JACKETT_TORZNAB_URL
            bot.JACKETT_TORZNAB_URL = (
                "http://fixtures:8765/api/v2.0/indexers/all/results/torznab/api"
            )
            before = {row["hash"] for row in bot.qbit_torrents_info_sync(limit=None)}
            try:
                incoming = ReplyProbe()
                incoming.text = "fixture"
                await bot.on_text(incoming.update, incoming.context)
                partial = incoming.replies[-1]
                assert "Поиск неполный" in partial.text and "SECRET" not in partial.text
                search_health["mode"] = "error"
                await partial.click("Повторить поиск", bot.on_pick)
                assert "временно недоступен" in partial.replies[-1].text
                assert "SECRET" not in partial.replies[-1].text
                assert partial.context.user_data["search"]["message"] == partial.message_id
                await partial.click("1", bot.on_pick)
                assert "Добавить этот торрент" in partial.text
                await partial.click("К результатам", bot.on_pick)
                search_health["mode"] = "complete"
                await partial.click("Повторить поиск", bot.on_pick)
                assert "2 из 2" in partial.replies[-1].text
                assert partial.context.user_data["search"]["message"] != partial.message_id
                assert {row["hash"] for row in bot.qbit_torrents_info_sync(limit=None)} == before
            finally:
                bot.JACKETT_TORZNAB_URL = original_url

        asyncio.run(partial_search_retry())
        passed(
            "JSON source coverage, partial results survive HTTP 503 retry, successful retry replaces old list"
        )

        async def health_cards():
            from health import HealthManager, check_jackett, check_qbit

            transport = SimpleNamespace(edit_message_text=AsyncMock(), pin_chat_message=AsyncMock())
            health_api = SimpleNamespace(
                allowed=bot.allowed,
                ALLOWED_USERS=bot.ALLOWED_USERS,
                check_qbit=lambda: check_qbit(bot.qbit_session, bot.QBIT_URL),
                check_jackett=lambda: check_jackett(bot.JACKETT_TORZNAB_URL, bot.JACKETT_API_KEY),
                last_search=lambda: bot.LAST_SEARCH_HEALTH,
                language_for_user=lambda user: "ru",
            )
            path = Path(bot.WATCH_DB_PATH).with_suffix(".health.sqlite3")
            manager = HealthManager(health_api, transport, path)
            incoming = DashboardProbe()
            before = {row["hash"] for row in bot.qbit_torrents_info_sync(limit=None)}
            try:
                await manager.open(incoming.update)
                assert (
                    "qBittorrent — доступен" in incoming.text
                    and "Jackett — доступен" in incoming.text
                )
                message_id = incoming.message_id
                await manager.close()
                manager = HealthManager(health_api, transport, path)
                health_probe["failed"] = True
                await manager.cycle()
                text = transport.edit_message_text.call_args.kwargs["text"]
                assert "Jackett — недоступен" in text and "qBittorrent — доступен" in text
                assert "SECRET" not in text
                health_probe["failed"] = False
                await manager.cycle()
                call = transport.edit_message_text.call_args.kwargs
                assert call["message_id"] == message_id and "Jackett — доступен" in call["text"]
                assert health_probe["calls"] == 3
                assert {row["hash"] for row in bot.qbit_torrents_info_sync(limit=None)} == before
                assert not transport.pin_chat_message.await_count
            finally:
                await manager.close()
                path.unlink(missing_ok=True)  # Synthetic chat IDs must not survive this fixture.

        asyncio.run(health_cards())
        passed(
            "Health card restores same message, probes real HTTP, isolates outage/recovery and leaves torrents unchanged"
        )

        dashboard = DashboardProbe()
        asyncio.run(dashboard.pause_resume())
        passed("Downloads handlers pause/resume the selected torrent and confirm live API state")

        async def stuck_download():
            # Unresolvable generated hash, internal network only. Advance the
            # observation clock instead of waiting five wall-clock minutes.
            waiting_hash = hashlib.sha1(b"local metadata waiting fixture").hexdigest()
            bot.qbit_add_sync("magnet:?xt=urn:btih:" + waiting_hash + "&dn=waiting-fixture")
            original_clock = bot.DOWNLOAD_HEALTH.now
            try:
                waiting = wait_for(lambda: info(waiting_hash), "metadata fixture appears")
                assert waiting["state"] in {"metaDL", "forcedMetaDL"}
                for tick in range(0, 301, 60):
                    bot.DOWNLOAD_HEALTH.now = lambda: tick
                    stalled = bot.DOWNLOAD_HEALTH.observe(info(waiting_hash))
                assert stalled
                await bot.cmd_downloads(dashboard.update, dashboard.context)
                assert "Требует внимания: 1" in dashboard.text
                assert "ожидание ≥5 мин" in dashboard.text
                await dashboard.select(waiting["name"][:50])
                assert (
                    "5 минут" in dashboard.text and "Нет подключённых источников" in dashboard.text
                )
                before = {row["hash"] for row in bot.qbit_torrents_info_sync(limit=None)}
                await dashboard.click("Найти другую раздачу")
                assert "Отправь название" in dashboard.text
                assert {row["hash"] for row in bot.qbit_torrents_info_sync(limit=None)} == before
                assert info(waiting_hash)["state"] in {"metaDL", "forcedMetaDL"}
                await dashboard.click("К загрузке")
                await dashboard.click("Пауза")
                assert "Приостановлено" in dashboard.text and "5 минут" not in dashboard.text
                await dashboard.click("← Загрузки")
                assert "Требует внимания: 0" in dashboard.text and "На паузе: 1" in dashboard.text
            finally:
                bot.DOWNLOAD_HEALTH.now = original_clock
                bot.DOWNLOAD_HEALTH.forget(waiting_hash)
                bot.qbit_control_sync("keep", waiting_hash)

        asyncio.run(stuck_download())
        passed(
            "Grouped overview tracks metadata warning, completion and pause; alternative search does not mutate"
        )

        transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
        asyncio.run(
            asyncio.wait_for(
                bot.watch_torrent_until_done(
                    101,
                    file_hash,
                    "uploaded.txt",
                    1,
                    SimpleNamespace(
                        bot=transport, user_id=101, language_for_user=lambda user: "ru"
                    ),
                ),
                timeout=5,
            )
        )
        assert transport.send_message.call_count == 1
        assert "100%" in transport.edit_message_text.call_args.kwargs["text"]
        completion = transport.send_message.call_args
        assert "/downloads/uploaded.txt" in completion.args[1] and "Plex" not in completion.args[1]
        markup = completion.kwargs["reply_markup"]
        assert not any(b.url for row in markup.inline_keyboard for b in row)

        async def open_completed():
            completed = DashboardProbe()
            completed.markup = markup
            await completed.click("Подробнее", bot.on_torrent_link)
            assert "uploaded.txt" in completed.text and "Пауза" in str(completed.markup)
            assert "/downloads/uploaded.txt" in completed.text

        asyncio.run(open_completed())
        passed(
            "Completion contains file location and direct live torrent details without external links"
        )

        async def restore_error_watch():
            from monitoring import WatchManager
            from watch_store import WatchStore

            path = Path("/tmp/error-recovery.sqlite3")
            store = WatchStore(path)
            store.subscribe(101, 101, file_hash, "uploaded.txt")
            store.set_status(101, file_hash, "error")
            store.close()
            transport = SimpleNamespace(
                edit_message_text=AsyncMock(),
                send_message=AsyncMock(return_value=SimpleNamespace(message_id=99)),
            )
            bot.language_for_user = lambda user: "ru"
            manager = WatchManager(bot, transport, WatchStore(path))
            try:
                await manager.restore()
                await asyncio.wait_for(asyncio.gather(*manager.tasks.values()), 10)
                assert manager.store.get(101, file_hash)["status"] == "completed"
                assert any(
                    c.kwargs["text"].startswith("Скачивание завершено:")
                    for c in transport.send_message.call_args_list
                )
            finally:
                await manager.close()

        asyncio.run(restore_error_watch())
        passed("Legacy error subscription reopens and completes against live qBittorrent state")

        original_read = bot.qbit_torrents_info_sync
        original_interval = bot.WATCH_INTERVAL_SEC

        def flaky_read(**kwargs):
            if not retry_probe["failures"]:
                requests.get("http://fixtures:8765/transient", timeout=5).raise_for_status()
            return original_read(**kwargs)

        bot.qbit_torrents_info_sync = flaky_read
        bot.WATCH_INTERVAL_SEC = 1
        recovered = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
        try:
            asyncio.run(
                asyncio.wait_for(
                    bot.watch_torrent_until_done(
                        101,
                        file_hash,
                        "uploaded.txt",
                        2,
                        SimpleNamespace(bot=recovered, language_for_user=lambda user: "ru"),
                    ),
                    timeout=10,
                )
            )
        finally:
            bot.qbit_torrents_info_sync = original_read
            bot.WATCH_INTERVAL_SEC = original_interval
        assert retry_probe["failures"] == 1
        assert recovered.send_message.call_count == 1
        edits = [call.kwargs["text"] for call in recovered.edit_message_text.call_args_list]
        assert "qBittorrent" in edits[0] and "100%" in edits[-1]
        passed("watcher retries real HTTP 503 then completes using live qBittorrent data")

        asyncio.run(dashboard.delete("http-added.txt", http_hash))
        wait_for(lambda: info(http_hash) is None, "torrent deleted")
        wait_for(lambda: not Path("/downloads/http-added.txt").exists(), "data deleted")
        assert Path("/downloads/uploaded.txt").read_bytes() == (
            b"Locally generated qbitbot verification data.\n" * 256
        )
        assert info(file_hash), "Unselected torrent must remain"
        passed(
            "Numbered Downloads selection and confirmed file deletion preserve unrelated data and retire monitoring"
        )
        asyncio.run(dashboard.delete("uploaded.txt", file_hash))
        wait_for(lambda: not Path("/downloads/uploaded.txt").exists(), "uploaded data deleted")

        bot.qbit_add_file_sync(sentinel_bytes, "sentinel.torrent")
        wait_for(lambda: info(sentinel_hash), "persistent sentinel")
        Path("/downloads/sentinel.json").write_text(
            json.dumps(
                {
                    "hash": sentinel_hash,
                    "name": "retained.txt",
                    "payload": Path("/downloads/retained.txt").read_text(),
                }
            )
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()
