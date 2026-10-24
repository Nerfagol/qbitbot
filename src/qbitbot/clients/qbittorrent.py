"""qBittorrent protocol, authentication and cached-session lifecycle."""

from dataclasses import dataclass
import re
import time
from typing import Dict, List, Optional

import requests


@dataclass(frozen=True, repr=False)
class QBitConfig:
    url: str
    username: str
    password: str
    host_header: str | None = None
    savepath: str | None = None
    category: str | None = None


class QBitClient:
    session_ttl = 30 * 60

    def __init__(self, config, *, session_factory=None, clock=None):
        self.config = config
        self.session_factory = session_factory or (lambda: requests.Session())
        self.clock = clock or time.time
        self._session = None
        self._session_ts = 0.0

    def login(self) -> requests.Session:
        s = self.session_factory()
        s.trust_env = False
        if self.config.host_header:
            s.headers["Host"] = self.config.host_header
        s.resolve_redirects = lambda *args, **kwargs: iter(())
        r = s.post(
            f"{self.config.url}/api/v2/auth/login",
            data={"username": self.config.username, "password": self.config.password},
            timeout=15,
        )
        if not (
            (r.status_code == 200 and r.text.strip() == "Ok.")
            or (r.status_code == 204 and not r.text.strip())
        ):
            raise RuntimeError(f"qBittorrent login failed: {r.status_code} {r.text}")
        return s

    def session(self) -> requests.Session:
        now = self.clock()
        if self._session is None or (now - self._session_ts) > self.session_ttl:
            self._session = self.login()
            self._session_ts = now
            return self._session

        # try a cheap call; if it fails, relogin
        try:
            r = self._session.get(f"{self.config.url}/api/v2/app/version", timeout=10)
            if r.status_code == 200:
                return self._session
        except Exception:
            pass

        self._session = self.login()
        self._session_ts = now
        return self._session

    def info(
        self,
        *,
        hashes: Optional[str] = None,
        filter_: Optional[str] = None,
        sort: str = "added_on",
        reverse: bool = True,
        limit: Optional[int] = 50,
    ) -> List[Dict]:
        s = self.session()
        params = {
            "sort": sort,
            "reverse": "true" if reverse else "false",
        }
        if limit is not None:
            params["limit"] = str(limit)
        if hashes:
            params["hashes"] = hashes
        if filter_:
            params["filter"] = filter_
        r = s.get(f"{self.config.url}/api/v2/torrents/info", params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def control(self, action: str, t_hash: str) -> None:
        # Deliberately prohibit qBittorrent's bulk/all syntax at this boundary.
        endpoints = {"pause": "stop", "resume": "start", "keep": "delete", "delete": "delete"}
        if action not in endpoints or not re.fullmatch(
            r"(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})", t_hash
        ):
            raise ValueError("Invalid torrent control")
        payload = {"hashes": t_hash}
        if action in ("keep", "delete"):
            payload["deleteFiles"] = "true" if action == "delete" else "false"
        response = self.session().post(
            f"{self.config.url}/api/v2/torrents/{endpoints[action]}",
            data=payload,
            timeout=20,
        )
        response.raise_for_status()

    def add_url(self, url: str) -> str:
        s = self.session()
        payload = {"urls": url}
        if self.config.savepath:
            payload["savepath"] = self.config.savepath
        if self.config.category:
            payload["category"] = self.config.category

        r = s.post(f"{self.config.url}/api/v2/torrents/add", data=payload, timeout=25)

        txt = (r.text or "").strip()
        if r.status_code not in (200, 204):
            raise RuntimeError(f"HTTP {r.status_code}: {txt}")
        # ВАЖНО: qBittorrent часто возвращает 200, но в body пишет Fails.
        if txt.lower().startswith("fail"):
            raise RuntimeError(f"qBittorrent add failed: {txt}")
        return txt

    def add_file(self, torrent_bytes: bytes, filename: str = "download.torrent") -> str:
        if not torrent_bytes:
            raise RuntimeError("torrent file is empty")

        s = self.session()
        payload: Dict[str, str] = {}
        if self.config.savepath:
            payload["savepath"] = self.config.savepath
        if self.config.category:
            payload["category"] = self.config.category

        files = {
            "torrents": (filename, torrent_bytes, "application/x-bittorrent"),
        }
        r = s.post(f"{self.config.url}/api/v2/torrents/add", data=payload, files=files, timeout=30)

        txt = (r.text or "").strip()
        if r.status_code not in (200, 204):
            raise RuntimeError(f"HTTP {r.status_code}: {txt}")
        if txt.lower().startswith("fail"):
            raise RuntimeError(f"qBittorrent add(file) failed: {txt}")
        return txt
