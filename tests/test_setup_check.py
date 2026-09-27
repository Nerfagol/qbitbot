import tempfile

import requests

import setup_check
from settings import read_settings
from tests.test_settings import valid_env


def rig(monkeypatch, tmp_path, *, password_ok=True, outage=False):
    calls = []

    class Response:
        status_code = 200

        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    class Client:
        def post(self, url, **kw):
            calls.append(("POST", url, kw))
            if outage:
                raise requests.Timeout("private URL and secret")
            return Response("Ok." if password_ok else "private response")

        def get(self, url, **kw):
            calls.append(("GET", url, kw))
            return Response("v5.1.2")

        def close(self):
            pass

    def get(url, **kw):
        calls.append(("GET", url, kw))
        return Response("<caps><searching/></caps>")

    monkeypatch.setattr(setup_check.requests, "Session", Client)
    monkeypatch.setattr(setup_check.requests, "get", get)
    sleeps = []
    monkeypatch.setattr(setup_check.time, "sleep", sleeps.append)
    cfg = read_settings(
        {**valid_env(), "WATCH_DB_PATH": str(tmp_path / "state" / "watches.sqlite3")}
    )
    return cfg, calls, sleeps


def test_probe_leaves_existing_database_unchanged(monkeypatch, tmp_path):
    cfg, calls, _ = rig(monkeypatch, tmp_path)
    cfg.watch_db_path.parent.mkdir()
    cfg.watch_db_path.write_bytes(b"untouched existing database")
    result = setup_check.run_checks(cfg)
    assert all(r.ok for r in result)
    assert cfg.watch_db_path.read_bytes() == b"untouched existing database"
    assert list(cfg.watch_db_path.parent.iterdir()) == [cfg.watch_db_path]
    assert all(c[2]["timeout"] == (5, 10) for c in calls)


def test_no_api_mutations(monkeypatch, tmp_path):
    cfg, calls, _ = rig(monkeypatch, tmp_path)
    assert all(r.ok for r in setup_check.run_checks(cfg))
    assert [(m, u.rsplit("/", 1)[-1]) for m, u, _ in calls] == [
        ("POST", "login"),
        ("GET", "version"),
        ("GET", "api"),
    ]
    assert calls[-1][2]["params"]["t"] == "caps"


def test_permission_error_is_actionable(monkeypatch, tmp_path):
    cfg, _, _ = rig(monkeypatch, tmp_path)

    def deny(*a, **kw):
        raise PermissionError("private storage path")

    monkeypatch.setattr(tempfile, "TemporaryFile", deny)
    state = next(r for r in setup_check.run_checks(cfg) if r.service == "state")
    assert not state.ok and state.message_key == "setup.storage"
    assert "private" not in repr(state)


def test_http_timeout_is_bounded(monkeypatch, tmp_path):
    cfg, calls, sleeps = rig(monkeypatch, tmp_path, outage=True)
    result = setup_check.run_checks(cfg)
    assert not result[0].ok and result[0].message_key == "setup.timeout"
    assert len([c for c in calls if c[0] == "POST"]) == 3
    assert sleeps == [2, 2]


def test_wrong_password_does_not_echo_response(monkeypatch, tmp_path):
    cfg, calls, sleeps = rig(monkeypatch, tmp_path, password_ok=False)
    result = setup_check.run_checks(cfg)
    assert not result[0].ok and result[0].message_key == "setup.auth"
    assert "private response" not in repr(result)
    assert len([c for c in calls if c[0] == "POST"]) == 1 and not sleeps
