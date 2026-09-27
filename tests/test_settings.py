from pathlib import Path

import pytest

from settings import SettingsError, load_env, read_settings


def valid_env():
    return dict(
        BOT_TOKEN="123456:TEST_ONLY",
        ALLOWED_USERS="101,202",
        QBIT_URL="http://qbit.invalid:8080",
        QBIT_USER="test",
        QBIT_PASS="synthetic",
        JACKETT_TORZNAB_URL="http://jackett.invalid/api",
        JACKETT_API_KEY="synthetic",
    )


@pytest.mark.parametrize("value", ["", "101,oops", "0", "-1", "101,", "1.2"])
def test_allowlist_rejects_empty_or_partially_invalid(value):
    with pytest.raises(SettingsError, match="ALLOWED_USERS"):
        read_settings({**valid_env(), "ALLOWED_USERS": value})


def test_credentials_preserved():
    secret = " test $literal #value 'quoted' "
    cfg = read_settings({**valid_env(), "QBIT_PASS": secret, "ALLOWED_USERS": "101,101"})
    assert cfg.qbit_pass == secret
    assert cfg.allowed_users == frozenset({101})
    assert secret not in repr(cfg)
    assert cfg.watch_db_path == Path("state/watches.sqlite3")
    assert (
        cfg.watch_interval,
        cfg.missing_grace,
        cfg.search_timeout,
        cfg.torrent_timeout,
        cfg.torrent_max_bytes,
    ) == (30, 600, 25, 25, 8388608)


@pytest.mark.parametrize(
    "field,value",
    [
        ("WATCH_INTERVAL_SEC", "private-value"),
        ("WATCH_INTERVAL_SEC", "0"),
        ("WATCH_MISSING_GRACE_SEC", "-2"),
        ("JACKETT_SEARCH_TIMEOUT_SEC", "0"),
        ("TORRENT_FETCH_TIMEOUT_SEC", "-1"),
        ("TORRENT_FETCH_MAX_BYTES", "0"),
        ("QBIT_URL", "file:///private-value"),
        ("QBIT_URL", "http://"),
        ("QBIT_URL", "http://host.invalid:bad"),
        ("BOT_TOKEN", ""),
        ("QBIT_PASS", ""),
    ],
)
def test_numeric_and_url_errors_redacted(field, value):
    with pytest.raises(SettingsError) as caught:
        read_settings({**valid_env(), field: value})
    assert field in str(caught.value)
    assert "private-value" not in str(caught.value)


def test_env_file_quotes_and_existing_environment(tmp_path):
    path = tmp_path / "bot.env"
    path.write_text("QBIT_PASS='a $b #c \\'quoted\\''\nALLOWED_USERS=101\n")
    env = {"ALLOWED_USERS": "202"}
    load_env(path, env)
    assert env == {"ALLOWED_USERS": "202", "QBIT_PASS": "a $b #c 'quoted'"}
