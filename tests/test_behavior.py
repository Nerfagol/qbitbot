import asyncio
import base64
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock

import pytest
import requests

from tests.helpers import Message, context, torrent, update


@pytest.mark.parametrize(
    "encoded", ["ab" * 20, base64.b32encode(bytes.fromhex("ab" * 20)).decode()]
)
def test_magnet_hash_normalizes_hex_and_base32(bot, encoded):
    assert bot.magnet_infohash_hex(f"magnet:?xt=urn:btih:{encoded}&dn=Example") == "ab" * 20


@pytest.mark.parametrize(
    "url", ["", "magnet:?xt=urn:btih:bad", "https://example.invalid/file.torrent"]
)
def test_non_hash_inputs_have_no_identity(bot, url):
    assert bot.magnet_infohash_hex(url) is None


def test_torznab_prefers_magnet_and_keeps_size_seeders(bot):
    xml = """<rss xmlns:t="http://torznab.com/schemas/2015/feed"><channel><item>
    <title>Test release</title><link>https://example.invalid/file</link>
    <t:attr name="magneturl" value="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/>
    <t:attr name="size" value="2048"/><t:attr name="seeders" value="7"/>
    </item></channel></rss>"""
    assert bot.torznab_items(xml) == [
        {
            "title": "Test release",
            "url": "magnet:?xt=urn:btih:" + "a" * 40,
            "size": 2048,
            "seeders": 7,
        }
    ]


def test_torznab_skips_unusable_results_and_handles_bad_numbers(bot):
    xml = """<rss xmlns:t="urn:torznab"><channel>
    <item><title>No link</title></item>
    <item><title>HTTP fallback</title><link>https://example.invalid/file</link>
    <t:attr name="size" value="unknown"/><t:attr name="seeders" value="bad"/>
    </item></channel></rss>"""
    assert bot.torznab_items(xml) == [
        {
            "title": "HTTP fallback",
            "url": "https://example.invalid/file",
            "size": None,
            "seeders": None,
        }
    ]


def test_redaction_removes_sensitive_query_values(bot):
    result = bot.redact_url(
        "https://example.invalid/torrent?apikey=secret1&passkey=secret2&q=Ubuntu"
    )
    query = parse_qs(urlsplit(result).query)
    assert query == {"apikey": ["***"], "passkey": ["***"], "q": ["Ubuntu"]}


@pytest.mark.parametrize("handler", ["cmd_start", "cmd_help", "cmd_status", "on_text", "on_pick"])
def test_unauthorized_user_cannot_trigger_actions(bot, handler):
    message = Message("query")
    asyncio.run(getattr(bot, handler)(update(message, "pick:1", user_id=999), context()))
    assert message.sent == []


def test_duplicate_magnet_is_not_added_again(bot, monkeypatch):
    existing = torrent()
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kwargs: [existing])

    def unexpected_add(*args):
        pytest.fail("A duplicate torrent must not be added again")

    monkeypatch.setattr(bot, "qbit_add_sync", unexpected_add)
    result = asyncio.run(bot.qbit_add_and_confirm("magnet:?xt=urn:btih:" + "a" * 40))
    assert result["already_exists"] is True
    assert result["info"] == existing
    assert result["ok"] is False


@pytest.mark.parametrize(
    "method,args",
    [
        ("qbit_add_sync", ("magnet:?xt=urn:btih:" + "a" * 40,)),
        ("qbit_add_file_sync", (b"d4:infodee", "test.torrent")),
    ],
)
def test_http_200_with_fails_body_is_not_success(bot, monkeypatch, method, args):
    session = SimpleNamespace(post=lambda *a, **k: SimpleNamespace(status_code=200, text="Fails."))
    monkeypatch.setattr(bot, "qbit_session", lambda: session)
    with pytest.raises(RuntimeError, match="add.*failed"):
        getattr(bot, method)(*args)


def test_new_magnet_confirmation_uses_exact_hash(bot, monkeypatch):
    reads = []
    additions = []

    def info(**kwargs):
        reads.append(kwargs)
        return [] if len(reads) == 1 else [torrent()]

    monkeypatch.setattr(bot, "qbit_torrents_info_sync", info)
    monkeypatch.setattr(bot, "qbit_add_sync", lambda url: additions.append(url) or "Ok.")
    magnet = "magnet:?xt=urn:btih:" + "a" * 40
    result = asyncio.run(bot.qbit_add_and_confirm(magnet))
    assert result["ok"] is True
    assert result["hash"] == "a" * 40
    assert additions == [magnet]
    assert all(call["hashes"] == "a" * 40 for call in reads)


def test_real_completion_edits_progress_and_notifies_once(bot, monkeypatch):
    monkeypatch.setattr(
        bot,
        "qbit_torrents_info_sync",
        lambda **kwargs: [torrent(state="uploading", progress=1.0, amount_left=0)],
    )
    transport = SimpleNamespace(edit_message_text=AsyncMock(), send_message=AsyncMock())
    asyncio.run(
        bot.watch_torrent_until_done(
            303, "a" * 40, "Test download", 10, SimpleNamespace(bot=transport)
        )
    )
    assert "100%" in transport.edit_message_text.call_args.kwargs["text"]
    assert transport.send_message.call_count == 1
    assert "Test download" in transport.send_message.call_args.args[1]


def test_download_file_enforces_size_limit(bot, monkeypatch):
    class Response:
        url = "https://example.invalid/test.torrent"
        headers = {"content-type": "application/x-bittorrent"}
        closed = False

        def raise_for_status(self):
            pass

        def iter_content(self, **kwargs):
            yield b"d4:info"
            yield b"x" * 10

        def close(self):
            self.closed = True

    response = Response()
    monkeypatch.setattr(requests, "get", lambda *a, **k: response)
    monkeypatch.setattr(bot, "TORRENT_FETCH_MAX_BYTES", 8)
    with pytest.raises(RuntimeError, match="too large"):
        bot.download_torrent_file_sync(response.url)
    assert response.closed
