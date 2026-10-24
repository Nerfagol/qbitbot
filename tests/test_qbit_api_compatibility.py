"""qBittorrent 5.x authentication and mutation response compatibility."""

from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("status,text", [(200, "Ok."), (204, "")])
def test_login_accepts_legacy_and_no_content_success(bot, monkeypatch, status, text):
    client = SimpleNamespace(post=lambda *a, **k: SimpleNamespace(status_code=status, text=text))
    monkeypatch.setattr(bot.requests, "Session", lambda: client)
    assert bot.qbit_login_session() is client


@pytest.mark.parametrize(
    "status,text",
    [(200, ""), (200, "Fails."), (204, "Fails."), (201, "Ok."), (401, ""), (403, "")],
)
def test_login_rejects_unsuccessful_or_unexpected_responses(bot, monkeypatch, status, text):
    client = SimpleNamespace(post=lambda *a, **k: SimpleNamespace(status_code=status, text=text))
    monkeypatch.setattr(bot.requests, "Session", lambda: client)
    with pytest.raises(RuntimeError, match="login failed"):
        bot.qbit_login_session()


@pytest.mark.parametrize("status,text", [(200, "Ok."), (204, "")])
@pytest.mark.parametrize(
    "method,args",
    [
        ("qbit_add_sync", ("magnet:?xt=urn:btih:" + "a" * 40,)),
        ("qbit_add_file_sync", (b"d4:infodee", "test.torrent")),
    ],
)
def test_add_accepts_legacy_and_no_content_success(bot, monkeypatch, status, text, method, args):
    client = SimpleNamespace(post=lambda *a, **k: SimpleNamespace(status_code=status, text=text))
    monkeypatch.setattr(bot, "qbit_session", lambda: client)
    assert getattr(bot, method)(*args) == text


def test_login_disables_environment_credentials_and_automatic_redirects(bot, monkeypatch):
    client = SimpleNamespace(
        trust_env=True,
        resolve_redirects=lambda *a, **k: iter(["unexpected redirect"]),
        post=lambda *a, **k: SimpleNamespace(status_code=200, text="Ok."),
    )
    monkeypatch.setattr(bot.requests, "Session", lambda: client)
    bot.qbit_login_session()
    assert client.trust_env is False
    assert list(client.resolve_redirects(None, None)) == []


def test_configured_host_header_is_used_without_changing_api_destination(bot, monkeypatch):
    calls = []
    client = SimpleNamespace(
        headers={},
        post=lambda url, **kw: calls.append(url) or SimpleNamespace(status_code=204, text=""),
    )
    monkeypatch.setattr(bot.requests, "Session", lambda: client)
    monkeypatch.setattr(bot, "QBIT_HOST_HEADER", "nas.example:13800")
    assert bot.qbit_login_session() is client
    assert client.headers["Host"] == "nas.example:13800"
    assert calls == [bot.QBIT_URL + "/api/v2/auth/login"]
