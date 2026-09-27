import asyncio
import hashlib
from unittest.mock import Mock, AsyncMock

import pytest

from integration.fixtures import sample
from tests.helpers import torrent


def setup_http(bot, monkeypatch):
    fixture = sample("requested.txt")
    data, expected = fixture["torrent"], fixture["hash"]
    monkeypatch.setattr(bot, "resolve_http_redirect_to_magnet_sync", lambda url: None)
    monkeypatch.setattr(
        bot,
        "download_torrent_file_sync",
        lambda url: {"bytes": data, "filename": "fixture.torrent"},
    )
    upload = Mock(return_value="Ok.")
    monkeypatch.setattr(bot, "qbit_add_file_sync", upload)
    monkeypatch.setattr(bot, "qbit_add_sync", Mock(return_value="Ok."))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return data, expected, upload


def test_http_add_ignores_unrelated_concurrent_torrent(bot, monkeypatch):
    data, expected, upload = setup_http(bot, monkeypatch)
    unrelated = torrent(hash="b" * 40, name="Unrelated")
    wanted = torrent(hash=expected, name="requested.txt")

    def read(**kwargs):
        rows = ([unrelated] if bot.qbit_add_sync.called or upload.called else []) + (
            [wanted] if upload.called else []
        )
        return [
            r for r in rows if not kwargs.get("hashes") or r["hash"] in kwargs["hashes"].split("|")
        ]

    monkeypatch.setattr(bot, "qbit_torrents_info_sync", read)
    result = asyncio.run(bot.qbit_add_and_confirm("https://fixture.invalid/file"))
    assert result["ok"] and result["hash"] == expected
    upload.assert_called_once_with(data, "fixture.torrent")
    bot.qbit_add_sync.assert_not_called()


def test_http_duplicate_is_recognized_by_file_identity(bot, monkeypatch):
    _, expected, upload = setup_http(bot, monkeypatch)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [torrent(hash=expected)])
    result = asyncio.run(bot.qbit_add_and_confirm("https://fixture.invalid/file"))
    assert result["already_exists"] and result["hash"] == expected
    upload.assert_not_called()
    bot.qbit_add_sync.assert_not_called()


def test_http_missing_target_never_confirms_another_torrent(bot, monkeypatch):
    _, _, upload = setup_http(bot, monkeypatch)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [torrent(hash="b" * 40)])
    result = asyncio.run(bot.qbit_add_and_confirm("https://fixture.invalid/file"))
    assert not result["ok"] and result["info"] is None
    assert upload.call_count == 1


def test_unparseable_magnet_is_not_added_or_guessed(bot, monkeypatch):
    add = Mock(return_value="Ok.")
    monkeypatch.setattr(bot, "qbit_add_sync", add)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [torrent()])
    result = asyncio.run(bot.qbit_add_and_confirm("magnet:?xt=urn:btih:invalid"))
    assert not result["ok"]
    add.assert_not_called()


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"<html>bad</html>",
        b"d4:infodee",
        b"d4:infoi1ee",
        b"d4:infode4:infodee",
        b"d4:info" + b"l" * 70 + b"e" * 70 + b"e",
        b"d4:infodeejunk",
    ],
)
def test_invalid_metadata_cannot_be_uploaded(bot, monkeypatch, data):
    _, _, upload = setup_http(bot, monkeypatch)
    monkeypatch.setattr(bot, "download_torrent_file_sync", lambda url: {"bytes": data})
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [])
    with pytest.raises(ValueError):
        asyncio.run(bot.qbit_add_and_confirm("https://fixture.invalid/file"))
    upload.assert_not_called()


def test_hash_uses_original_info_bytes_not_reencoded_dictionary(bot):
    raw = b"d4:name1:x6:lengthi1e12:piece lengthi1e6:pieces20:abcdefghijklmnopqrste"
    assert hashlib.sha1(raw).hexdigest() in bot.torrent_infohashes(b"d4:info" + raw + b"e")


@pytest.mark.parametrize("hybrid", [False, True])
def test_v2_metadata_uses_sha256_and_hybrid_also_supports_v1(bot, hybrid):
    from integration.fixtures import bencode

    info = {
        b"name": b"x",
        b"piece length": 16384,
        b"meta version": 2,
        b"file tree": {b"x": {b"": {b"length": 1, b"pieces root": b"a" * 32}}},
    }
    if hybrid:
        info.update({b"length": 1, b"pieces": b"b" * 20})
    raw = bencode(info)
    expected = {hashlib.sha256(raw).hexdigest(), hashlib.sha256(raw).hexdigest()[:40]}
    if hybrid:
        expected.add(hashlib.sha1(raw).hexdigest())
    assert bot.torrent_infohashes(b"d4:info" + raw + b"e") == expected


def test_http_redirect_to_magnet_confirms_exact_hash(bot, monkeypatch):
    expected = "a" * 40
    monkeypatch.setattr(
        bot, "resolve_http_redirect_to_magnet_sync", lambda url: "magnet:?xt=urn:btih:" + expected
    )
    add = Mock(return_value="Ok.")
    monkeypatch.setattr(bot, "qbit_add_sync", add)
    monkeypatch.setattr(
        bot, "qbit_torrents_info_sync", lambda **kw: [torrent()] if add.called else []
    )
    result = asyncio.run(bot.qbit_add_and_confirm("https://fixture.invalid/redirect"))
    assert result["ok"] and result["hash"] == expected
    add.assert_called_once()


def test_http_upload_timeout_is_never_replayed(bot, monkeypatch):
    import requests

    _, _, upload = setup_http(bot, monkeypatch)
    upload.side_effect = requests.Timeout("private://secret")
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [])
    with pytest.raises(requests.Timeout):
        asyncio.run(bot.qbit_add_and_confirm("https://fixture.invalid/file"))
    assert upload.call_count == 1
    bot.qbit_add_sync.assert_not_called()
