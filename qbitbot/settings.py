"""Validated runtime settings; error messages never contain supplied values."""

import os
import re
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class SettingsError(ValueError):
    """A safe configuration field/rule diagnostic."""


def load_env(path: str | Path = "bot.env", env: MutableMapping[str, str] | None = None) -> None:
    target = os.environ if env is None else env
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            quote = value[0]
            value = value[1:-1].replace("\\" + quote, quote)
        target.setdefault(key, value)


@dataclass(frozen=True, repr=False)
class Settings:
    bot_token: str
    allowed_users: frozenset[int]
    qbit_url: str
    qbit_user: str
    qbit_pass: str
    jackett_url: str
    jackett_key: str
    watch_db_path: Path
    watch_interval: int
    missing_grace: int
    search_timeout: int
    torrent_timeout: int
    torrent_max_bytes: int
    savepath: str | None
    category: str | None


def read_settings(env: Mapping[str, str]) -> Settings:
    def required(name):
        value = env.get(name, "")
        if not value.strip():
            raise SettingsError(f"{name}: required")
        return value

    def positive(name, default):
        try:
            value = int(env.get(name, str(default)))
            if value <= 0:
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise SettingsError(f"{name}: positive integer required") from None

    def url(name):
        value = required(name).strip()
        try:
            parts = urlsplit(value)
            if (
                parts.scheme not in ("http", "https")
                or not parts.hostname
                or parts.username
                or parts.password
                or re.search(r"\s", value)
            ):
                raise ValueError
            parts.port
        except ValueError:
            raise SettingsError(
                f"{name}: HTTP(S) URL without embedded credentials required"
            ) from None
        return value.rstrip("/")

    users = env.get("ALLOWED_USERS", "").split(",")
    if not all(re.fullmatch(r"[0-9]+", v.strip()) and int(v.strip()) > 0 for v in users):
        raise SettingsError("ALLOWED_USERS: comma-separated positive user IDs required")
    return Settings(
        bot_token=required("BOT_TOKEN").strip(),
        allowed_users=frozenset(int(v.strip()) for v in users),
        qbit_url=url("QBIT_URL"),
        qbit_user=required("QBIT_USER"),
        qbit_pass=required("QBIT_PASS"),
        jackett_url=url("JACKETT_TORZNAB_URL"),
        jackett_key=required("JACKETT_API_KEY"),
        watch_db_path=Path(env.get("WATCH_DB_PATH", "state/watches.sqlite3")),
        watch_interval=positive("WATCH_INTERVAL_SEC", 30),
        missing_grace=positive("WATCH_MISSING_GRACE_SEC", 600),
        search_timeout=positive("JACKETT_SEARCH_TIMEOUT_SEC", 25),
        torrent_timeout=positive("TORRENT_FETCH_TIMEOUT_SEC", 25),
        torrent_max_bytes=positive("TORRENT_FETCH_MAX_BYTES", 8388608),
        savepath=env.get("QBIT_SAVEPATH", "").strip() or None,
        category=env.get("QBIT_CATEGORY", "").strip() or None,
    )
