"""Explicit startup and independent service-client boundaries; synthetic I/O only."""

from contextlib import contextmanager
from dataclasses import replace
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from qbitbot.settings import read_settings


def settings():
    return read_settings(
        {
            "BOT_TOKEN": "123456:SYNTHETIC",
            "ALLOWED_USERS": "101",
            "QBIT_URL": "http://qbit.invalid",
            "QBIT_USER": "test-user",
            "QBIT_PASS": "synthetic-password",
            "JACKETT_TORZNAB_URL": "http://jackett.invalid/api",
            "JACKETT_API_KEY": "synthetic-key",
        }
    )


def test_imports_do_not_read_environment_config_or_create_state(tmp_path):
    (tmp_path / "bot.env").write_text("ALLOWED_USERS=invalid\n")
    code = (
        "import os,socket; from pathlib import Path; "
        "os.environ.clear(); "
        "deny=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network during import')); "
        "socket.socket.connect=deny; socket.socket.connect_ex=deny; socket.getaddrinfo=deny; "
        "import qbitbot.app,qbitbot.startup,qbitbot.clients.qbittorrent,qbitbot.clients.jackett; "
        "assert qbitbot.app._SETTINGS is None; "
        "assert not qbitbot.app.ALLOWED_USERS; "
        "assert sorted(p.name for p in Path('.').iterdir())==['bot.env']"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        env={},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_explicit_runtime_load_preserves_injected_environment_and_does_not_mutate_it(tmp_path):
    from qbitbot.startup import load_runtime

    path = tmp_path / "bot.env"
    path.write_text("ALLOWED_USERS=999\nTORRENT_FETCH_USER_AGENT=fixture-agent\n")
    env = {
        "BOT_TOKEN": "123456:SYNTHETIC",
        "ALLOWED_USERS": "101",
        "QBIT_URL": "http://qbit.invalid",
        "QBIT_USER": "user",
        "QBIT_PASS": "password",
        "JACKETT_TORZNAB_URL": "http://jackett.invalid/api",
        "JACKETT_API_KEY": "key",
    }
    before = dict(env)
    config, values = load_runtime(env, path)
    assert config.allowed_users == frozenset({101})
    assert values["TORRENT_FETCH_USER_AGENT"] == "fixture-agent"
    assert env == before


def test_qbit_client_cache_relogin_and_transport_protections():
    from qbitbot.clients.qbittorrent import QBitClient, QBitConfig

    now = [100.0]
    sessions = []

    class Session:
        def __init__(self):
            self.headers = {}
            self.calls = []
            self.valid = True
            sessions.append(self)

        def post(self, url, **kw):
            self.calls.append((url, kw))
            return SimpleNamespace(status_code=204, text="")

        def get(self, *args, **kw):
            return SimpleNamespace(status_code=200 if self.valid else 403)

    cfg = QBitConfig("http://qbit.invalid", "user", "private-pass", host_header="nas.example:8080")
    client = QBitClient(cfg, session_factory=Session, clock=lambda: now[0])
    first = client.session()
    assert client.session() is first
    assert first.trust_env is False and list(first.resolve_redirects(None, None)) == []
    assert first.headers["Host"] == "nas.example:8080"
    first.valid = False
    second = client.session()
    assert second is not first
    now[0] += 1801
    assert client.session() is not second
    assert len(sessions) == 3
    assert "private-pass" not in repr(cfg)


@pytest.mark.parametrize(
    "url,json_api",
    [
        ("http://jackett.invalid/api/v2.0/indexers/all/results/torznab/api", True),
        ("http://jackett.invalid/custom", False),
    ],
)
def test_jackett_client_owns_bounded_trusted_origin_search(monkeypatch, url, json_api):
    from qbitbot.clients import jackett

    calls = []
    body = (
        json.dumps({"Results": [], "Indexers": [{"Status": 2}]}).encode()
        if json_api
        else b"<rss><channel/></rss>"
    )
    response = SimpleNamespace(
        headers={},
        closed=False,
        raise_for_status=lambda: None,
        iter_content=lambda **kw: iter([body]),
    )

    @contextmanager
    def request(method, destination, **kw):
        calls.append((destination, kw))
        try:
            yield response
        finally:
            response.closed = True

    monkeypatch.setattr(jackett, "open_response", request)
    client = jackett.JackettClient(jackett.JackettConfig(url, "private-key", 9))
    result = client.search("query", 3)
    assert result == [] and response.closed
    assert calls[0][1]["trusted_url"] == url
    assert calls[0][1]["allow_external_redirects"] is False
    assert calls[0][1]["timeout"] == (5, 9)
    assert "private-key" not in repr(client.config)
    monkeypatch.setattr(jackett, "MAX_SEARCH_BYTES", 1)
    with pytest.raises(ValueError):
        client.search("query")


def test_configuration_builds_handlers_explicitly_without_opening_databases(tmp_path):
    from qbitbot.startup import configure_handlers

    handlers = SimpleNamespace()
    config = replace(settings(), watch_db_path=tmp_path / "state" / "watches.sqlite3")
    assert (
        configure_handlers(
            config,
            env={"DIAG_REDACT": "0", "TORRENT_FETCH_USER_AGENT": "fixture-agent"},
            handlers=handlers,
        )
        is handlers
    )
    assert handlers._SETTINGS is config and handlers.ALLOWED_USERS == {101}
    assert handlers.JACKETT_TORZNAB_URL == handlers._JACKETT_CLIENT.config.url
    assert handlers.QBIT_URL == handlers._QBIT_CLIENT.config.url
    assert handlers.DIAG_REDACT is False and handlers.TORRENT_FETCH_USER_AGENT == "fixture-agent"
    assert not (tmp_path / "state").exists()
