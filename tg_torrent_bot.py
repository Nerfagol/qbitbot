import os
import sys
import time
import asyncio
import hashlib
import requests
import xml.etree.ElementTree as ET
import base64
import binascii
import re
import io
import hmac
from types import SimpleNamespace
from pathlib import Path
from i18n import tr, normalize_language
from preferences import LanguageService, PreferenceStore
from language_ui import LanguagePicker, command_list, set_private_commands
from health import HealthManager, check_jackett, check_qbit
from watch_store import WatchStore
from downloads import download_location, title as download_title, identity, torrent_link, link_hash, DownloadHealth, DownloadsDashboard, download_progress, download_status, progress_percent
from search_ui import SearchBrowser, SearchResults
from monitoring import WatchManager, WatchStopped, SearchJobs
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, unquote, urljoin
from typing import List, Dict, Optional, Tuple, Set

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile, BotCommand, MenuButtonCommands
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Environment files are optional; injected environment values take precedence.
from settings import load_env, read_settings

load_env()
_SETTINGS = read_settings(os.environ)
BOT_TOKEN = _SETTINGS.bot_token
ALLOWED_USERS = set(_SETTINGS.allowed_users)
JACKETT_TORZNAB_URL = _SETTINGS.jackett_url
JACKETT_API_KEY = _SETTINGS.jackett_key
JACKETT_SEARCH_TIMEOUT_SEC = _SETTINGS.search_timeout
QBIT_URL = _SETTINGS.qbit_url
QBIT_USER = _SETTINGS.qbit_user
QBIT_PASS = _SETTINGS.qbit_pass
QBIT_SAVEPATH = _SETTINGS.savepath
QBIT_CATEGORY = _SETTINGS.category

RESULTS_LIMIT = 50
SEARCH_TTL_SEC = 15 * 60

# qBittorrent polling
WATCH_DB_PATH = str(_SETTINGS.watch_db_path)
WATCH_INTERVAL_SEC = _SETTINGS.watch_interval
WATCH_MISSING_GRACE_SEC = _SETTINGS.missing_grace
WATCH_PROGRESS_STEP = 10  # notify every N%

DOWNLOAD_HEALTH = DownloadHealth(max_gap=max(90, 2 * WATCH_INTERVAL_SEC))

# diagnostics
DIAG_REDACT = os.environ.get("DIAG_REDACT", "1").lower() not in ("0","false","no")

# HTTP .torrent fallback download
TORRENT_FETCH_TIMEOUT_SEC = _SETTINGS.torrent_timeout
TORRENT_FETCH_MAX_BYTES = _SETTINGS.torrent_max_bytes
TORRENT_FETCH_USER_AGENT = os.environ.get(
    "TORRENT_FETCH_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
)

# ----------------- helpers -----------------
def allowed(update: Update) -> bool:
    return update.effective_user is not None and update.effective_user.id in ALLOWED_USERS


def human_size(n: Optional[int]) -> str:
    if not n:
        return ""
    x = float(n)
    units = ["B", "KB", "MB", "GB", "TB"]
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.1f}{u}" if u != "B" else f"{int(x)}B"
        x /= 1024
    return ""


def human_speed(bps: Optional[int]) -> str:
    if bps is None:
        return ""
    return f"{human_size(int(bps))}/s"


def human_eta(sec: Optional[int]) -> str:
    if sec is None or sec < 0 or sec >= 8640000:
        return ""
    if sec == 0:
        return "0s"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def format_download_progress(info, *, live=False, stalled=False, language="en"):
    return download_progress(info, SimpleNamespace(
        is_completed=is_completed, human_size=human_size, human_speed=human_speed,
    ), live=live, stalled=stalled, language=language)


# ---- qBittorrent API (sync, called via asyncio.to_thread) ----
_QBIT_SESSION: Optional[requests.Session] = None
_QBIT_SESSION_TS: float = 0.0
_QBIT_SESSION_TTL_SEC = 30 * 60  # 30 minutes


def qbit_login_session() -> requests.Session:
    s = requests.Session()
    r = s.post(
        f"{QBIT_URL}/api/v2/auth/login",
        data={"username": QBIT_USER, "password": QBIT_PASS},
        timeout=15,
    )
    if r.status_code != 200 or r.text.strip() != "Ok.":
        raise RuntimeError(f"qBittorrent login failed: {r.status_code} {r.text}")
    return s


def qbit_session() -> requests.Session:
    global _QBIT_SESSION, _QBIT_SESSION_TS
    now = time.time()
    if _QBIT_SESSION is None or (now - _QBIT_SESSION_TS) > _QBIT_SESSION_TTL_SEC:
        _QBIT_SESSION = qbit_login_session()
        _QBIT_SESSION_TS = now
        return _QBIT_SESSION

    # try a cheap call; if it fails, relogin
    try:
        r = _QBIT_SESSION.get(f"{QBIT_URL}/api/v2/app/version", timeout=10)
        if r.status_code == 200:
            return _QBIT_SESSION
    except Exception:
        pass

    _QBIT_SESSION = qbit_login_session()
    _QBIT_SESSION_TS = now
    return _QBIT_SESSION


def qbit_torrents_info_sync(
    *,
    hashes: Optional[str] = None,
    filter_: Optional[str] = None,
    sort: str = "added_on",
    reverse: bool = True,
    limit: Optional[int] = 50,
) -> List[Dict]:
    s = qbit_session()
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
    r = s.get(f"{QBIT_URL}/api/v2/torrents/info", params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def qbit_control_sync(action: str, t_hash: str) -> None:
    # Deliberately prohibit qBittorrent's bulk/all syntax at this boundary.
    endpoints = {"pause": "stop", "resume": "start", "keep": "delete", "delete": "delete"}
    if action not in endpoints or not re.fullmatch(r"(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})", t_hash):
        raise ValueError("Invalid torrent control")
    payload = {"hashes": t_hash}
    if action in ("keep", "delete"):
        payload["deleteFiles"] = "true" if action == "delete" else "false"
    response = qbit_session().post(
        f"{QBIT_URL}/api/v2/torrents/{endpoints[action]}", data=payload, timeout=20,
    )
    response.raise_for_status()


def qbit_add_sync(url: str) -> str:
    s = qbit_session()
    payload = {"urls": url}
    if QBIT_SAVEPATH:
        payload["savepath"] = QBIT_SAVEPATH
    if QBIT_CATEGORY:
        payload["category"] = QBIT_CATEGORY

    r = s.post(f"{QBIT_URL}/api/v2/torrents/add", data=payload, timeout=25)

    txt = (r.text or "").strip()
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {txt}")
    # ВАЖНО: qBittorrent часто возвращает 200, но в body пишет Fails.
    if txt.lower().startswith("fail"):
        raise RuntimeError(f"qBittorrent add failed: {txt}")
    return txt


def qbit_add_file_sync(torrent_bytes: bytes, filename: str = "download.torrent") -> str:
    if not torrent_bytes:
        raise RuntimeError("torrent file is empty")

    s = qbit_session()
    payload: Dict[str, str] = {}
    if QBIT_SAVEPATH:
        payload["savepath"] = QBIT_SAVEPATH
    if QBIT_CATEGORY:
        payload["category"] = QBIT_CATEGORY

    files = {
        "torrents": (filename, torrent_bytes, "application/x-bittorrent"),
    }
    r = s.post(f"{QBIT_URL}/api/v2/torrents/add", data=payload, files=files, timeout=30)

    txt = (r.text or "").strip()
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {txt}")
    if txt.lower().startswith("fail"):
        raise RuntimeError(f"qBittorrent add(file) failed: {txt}")
    return txt


def _filename_from_content_disposition(cd: str) -> Optional[str]:
    if not cd:
        return None
    m_star = re.search(r"filename\*=UTF-8''([^;]+)", cd, flags=re.IGNORECASE)
    if m_star:
        name = unquote(m_star.group(1)).strip().strip('"')
        return os.path.basename(name) or None

    m = re.search(r'filename="?([^\";]+)"?', cd, flags=re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip('"')
        return os.path.basename(name) or None
    return None


def looks_like_torrent_bytes(data: bytes) -> bool:
    if not data or data[:1] != b"d":
        return False
    head = data[:8192]
    return (b":announce" in head) or (b":info" in head)


def resolve_http_redirect_to_magnet_sync(url: str) -> Optional[str]:
    """If HTTP(S) URL redirects to magnet:, return the magnet URL, else None."""
    headers = {"User-Agent": TORRENT_FETCH_USER_AGENT}
    cur = url
    for _ in range(10):
        r = requests.get(
            cur,
            allow_redirects=False,
            stream=True,
            timeout=TORRENT_FETCH_TIMEOUT_SEC,
            headers=headers,
        )
        try:
            if r.status_code in (301, 302, 303, 307, 308):
                loc = (r.headers.get("location") or "").strip()
                if not loc:
                    return None
                loc = urljoin(cur, loc)
                if loc.lower().startswith("magnet:?"):
                    return loc
                if loc.lower().startswith(("http://", "https://")):
                    cur = loc
                    continue
                return None
            return None
        finally:
            r.close()
    return None


def download_torrent_file_sync(url: str) -> Dict:
    headers = {
        "User-Agent": TORRENT_FETCH_USER_AGENT,
        "Accept": "application/x-bittorrent,application/octet-stream,*/*",
    }
    out: Dict = {
        "final_url": None,
        "content_type": None,
        "content_length": None,
        "filename": None,
        "size": 0,
    }

    r = requests.get(
        url,
        allow_redirects=True,
        stream=True,
        timeout=TORRENT_FETCH_TIMEOUT_SEC,
        headers=headers,
    )
    try:
        r.raise_for_status()
        out["final_url"] = str(r.url)
        out["content_type"] = r.headers.get("content-type")
        out["content_length"] = r.headers.get("content-length")

        chunks: List[bytes] = []
        total = 0
        for chunk in r.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > TORRENT_FETCH_MAX_BYTES:
                raise RuntimeError(
                    f"torrent file too large: {total} bytes (limit {TORRENT_FETCH_MAX_BYTES})"
                )
            chunks.append(chunk)

        data = b"".join(chunks)
        out["size"] = len(data)
        if not data:
            raise RuntimeError("empty HTTP body")

        content_type = (out.get("content_type") or "").lower()
        if not looks_like_torrent_bytes(data):
            sample = data[:120].decode("utf-8", errors="replace").replace("\n", " ").replace("\r", " ")
            raise RuntimeError(
                "downloaded content is not a .torrent file "
                f"(content-type={content_type or 'unknown'}, sample={sample!r})"
            )

        name = _filename_from_content_disposition(r.headers.get("content-disposition", ""))
        if not name:
            path_name = os.path.basename(urlsplit(str(r.url)).path)
            name = unquote(path_name) if path_name else "download.torrent"
        if not name.lower().endswith(".torrent"):
            name = f"{name}.torrent"
        out["filename"] = name
        out["bytes"] = data
        return out
    finally:
        r.close()


# ---- Magnet hash extraction ----
_MAGNET_HASH_RE = re.compile(r"xt=urn:btih:([A-Za-z0-9]+)", flags=re.IGNORECASE)


def _btih_to_hex(h: str) -> Optional[str]:
    h = (h or "").strip()
    if not h:
        return None
    if re.fullmatch(r"[A-Fa-f0-9]{40}", h):
        return h.lower()
    if re.fullmatch(r"[A-Za-z2-7]{32}", h):
        try:
            raw = base64.b32decode(h.upper())
            return binascii.hexlify(raw).decode("ascii").lower()
        except Exception:
            return None
    return None


def magnet_infohash_hex(url: str) -> Optional[str]:
    if not url:
        return None
    u = url.strip()

    # Preferred parser path: parse xt query param from magnet URL.
    try:
        parts = urlsplit(u)
        for k, v in parse_qsl(parts.query, keep_blank_values=True):
            if k.lower() != "xt":
                continue
            val = unquote(v).strip()
            if val.lower().startswith("urn:btih:"):
                btih = val.split(":", 2)[-1]
                hex_hash = _btih_to_hex(btih)
                if hex_hash:
                    return hex_hash
    except Exception:
        pass

    # Fallback regex path for non-standard formatting.
    m = _MAGNET_HASH_RE.search(unquote(u))
    if not m:
        return None
    return _btih_to_hex(m.group(1))





SENSITIVE_QUERY_KEYS = {"apikey", "jackett_apikey", "passkey", "token", "auth", "key"}

def redact_url(url: str) -> str:
    """
    Redact sensitive query params to avoid leaking API keys in chat logs.
    Example: ...?apikey=***&passkey=***
    """
    try:
        parts = urlsplit(url)
        q = []
        for k, v in parse_qsl(parts.query, keep_blank_values=True):
            if k.lower() in SENSITIVE_QUERY_KEYS:
                q.append((k, "***"))
            else:
                q.append((k, v))
        new_query = urlencode(q, doseq=True)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
    except Exception:
        return url

async def send_text_as_file(message, filename: str, text: str, caption: str = ""):
    bio = io.BytesIO(text.encode("utf-8"))
    bio.name = filename
    await message.reply_document(document=InputFile(bio, filename=filename), caption=caption)

async def send_long_text(message, header: str, text: str):
    """
    Telegram messages have length limits. If `text` is too long, send it as a .txt file.
    """
    if not text:
        return
    if len(text) <= 3800:
        await message.reply_text(f"{header}\n{text}", disable_web_page_preview=True)
    else:
        await send_text_as_file(message, "debug_url.txt", text, caption=header)

def url_kind(url: str) -> str:
    u = (url or "").lower()
    if u.startswith("magnet:?"):
        return "magnet"
    if u.startswith("http://") or u.startswith("https://"):
        return "http"
    return "other"


def probe_url_sync(url: str) -> Dict:
    """Lightweight диагностика для HTTP ссылок (без существенной загрузки)."""
    out: Dict = {"ok": False, "status": None, "final_url": None, "content_type": None, "note": ""}

    try:
        r = requests.head(url, allow_redirects=True, timeout=12)
        out.update(
            ok=True,
            method="HEAD",
            status=r.status_code,
            final_url=str(r.url),
            content_type=r.headers.get("content-type"),
            content_length=r.headers.get("content-length"),
        )
        # Many endpoints don't support HEAD (405). In that case, fall back to GET.
        if r.status_code == 405:
            raise RuntimeError("HEAD not allowed (405)")
        # If HEAD errors or doesn't provide content-type, try GET to learn what it actually returns.
        if r.status_code >= 400:
            raise RuntimeError(f"HEAD returned {r.status_code}")
        if (out.get("content_type") is None) and (200 <= r.status_code < 400):
            raise RuntimeError("HEAD ok but no content-type")
        return out
    except Exception:
        pass

    try:
        r = requests.get(url, allow_redirects=True, stream=True, timeout=12)
        _ = r.raw.read(2048) if r.raw else b""
        r.close()
        out.update(
            ok=True,
            method="GET",
            status=r.status_code,
            final_url=str(r.url),
            content_type=r.headers.get("content-type"),
            content_length=r.headers.get("content-length"),
        )
        return out
    except Exception as e:
        out["note"] = str(e)
        return out


async def probe_url(url: str) -> Dict:
    return await asyncio.to_thread(probe_url_sync, url)

def torrent_infohashes(data: bytes) -> Set[str]:
    """Hash the exact info dictionary; reject malformed/ambiguous metainfo."""
    if not data or len(data) > TORRENT_FETCH_MAX_BYTES:
        raise ValueError("Invalid metainfo size")
    info_bytes = None
    nodes = 0

    def parse(pos, depth=0):
        nonlocal info_bytes, nodes
        nodes += 1
        if depth > 64 or nodes > 100000 or pos >= len(data):
            raise ValueError("Invalid metainfo structure")
        token = data[pos:pos+1]
        if token == b"i":
            end = data.find(b"e", pos + 1)
            raw = data[pos+1:end]
            if end < 0 or not re.fullmatch(rb"0|-?[1-9][0-9]{0,19}", raw):
                raise ValueError("Invalid metainfo integer")
            return int(raw), end + 1
        if token in (b"d", b"l"):
            value = {} if token == b"d" else []
            pos += 1
            while data[pos:pos+1] != b"e":
                if token == b"d":
                    key, pos = parse(pos, depth + 1)
                    if not isinstance(key, bytes) or key in value:
                        raise ValueError("Invalid metainfo key")
                    start = pos
                    item, pos = parse(pos, depth + 1)
                    value[key] = item
                    if depth == 0 and key == b"info":
                        info_bytes = data[start:pos]
                else:
                    item, pos = parse(pos, depth + 1)
                    value.append(item)
            return value, pos + 1
        end = data.find(b":", pos)
        raw = data[pos:end]
        if end < 0 or not re.fullmatch(rb"0|[1-9][0-9]{0,8}", raw):
            raise ValueError("Invalid metainfo string")
        stop = end + 1 + int(raw)
        if stop > len(data):
            raise ValueError("Truncated metainfo")
        return data[end+1:stop], stop

    root, end = parse(0)
    info = root.get(b"info") if isinstance(root, dict) else None
    if end != len(data) or not isinstance(info, dict) or not info_bytes:
        raise ValueError("Missing metainfo dictionary")
    if not isinstance(info.get(b"name"), bytes) or not info[b"name"]:
        raise ValueError("Missing torrent name")
    if not isinstance(info.get(b"piece length"), int) or info[b"piece length"] <= 0:
        raise ValueError("Invalid piece length")
    hashes = set()
    version = info.get(b"meta version", 1)
    if version not in (1, 2):
        raise ValueError("Unsupported metainfo version")
    pieces = info.get(b"pieces")
    if isinstance(pieces, bytes) and len(pieces) % 20 == 0:
        hashes.add(hashlib.sha1(info_bytes).hexdigest())
    if version == 2 and isinstance(info.get(b"file tree"), dict) and info[b"file tree"]:
        digest = hashlib.sha256(info_bytes).hexdigest()
        hashes.update((digest, digest[:40]))
    if not hashes:
        raise ValueError("Missing torrent identity")
    return hashes


async def qbit_add_and_confirm(url: str, title_hint: str = "") -> Dict:
    """Add only identifiable torrents, then confirm the exact metadata hash."""
    kind = url_kind(url)
    fetched = None
    t_hash = magnet_infohash_hex(url)
    if kind == "http":
        magnet = await asyncio.to_thread(resolve_http_redirect_to_magnet_sync, url)
        if magnet:
            return await qbit_add_and_confirm(magnet, title_hint=title_hint)
        fetched = await asyncio.to_thread(download_torrent_file_sync, url)
        hashes = torrent_infohashes(fetched["bytes"])
    elif kind == "magnet" and t_hash:
        hashes = {t_hash}
    else:
        # Never infer identity from another client's simultaneous addition.
        return {"ok": False, "hash": None, "info": None, "add_reply": ""}

    async def find_target():
        infos = await asyncio.to_thread(qbit_torrents_info_sync, hashes="|".join(sorted(hashes)), limit=None)
        return next((t for t in infos if str(t.get("hash") or "").lower() in hashes), None)

    existing = await find_target()
    if existing:
        return {"ok": False, "already_exists": True, "hash": existing["hash"], "info": existing, "add_reply": ""}
    if fetched:
        reply = await asyncio.to_thread(qbit_add_file_sync, fetched["bytes"], fetched.get("filename") or "download.torrent")
    else:
        reply = await asyncio.to_thread(qbit_add_sync, url)
    for _ in range(20):
        info = await find_target()
        if info:
            return {"ok": True, "hash": info["hash"], "info": info, "add_reply": reply}
        await asyncio.sleep(0.5)
    return {"ok": False, "hash": None, "info": None, "add_reply": reply}


def is_completed(t: Dict) -> bool:
    # Metadata/checking/error states can report zero remaining bytes too.
    completed_states = {"uploading", "stalledUP", "queuedUP", "stoppedUP", "forcedUP", "pausedUP"}
    if t.get("state") not in completed_states:
        return False
    try:
        return (
            float(t.get("total_size", 0)) > 0
            and float(t.get("amount_left", -1)) == 0
            and float(t.get("progress", 0)) == 1.0
        )
    except (TypeError, ValueError, OverflowError):
        return False


def is_error_state(state: Optional[str]) -> bool:
    if not state:
        return False
    s = state.lower()
    return ("error" in s) or ("missing" in s) or ("unknown" in s)


async def watch_torrent_until_done(
    chat_id: int,
    t_hash: str,
    title: str,
    progress_message_id: int,
    context: ContextTypes.DEFAULT_TYPE,
):
    missing_since = None
    failures = 0
    last_text = ""

    while True:
        language = getattr(context, "language_for_user", lambda user: "en")(getattr(context, "user_id", None))
        try:
            info_list = await asyncio.to_thread(qbit_torrents_info_sync, hashes=t_hash, limit=1)
        except (requests.RequestException, RuntimeError, ValueError):
            failures += 1
            DOWNLOAD_HEALTH.forget(t_hash)
            missing_since = None
            warning = tr("notice.outage", language)
            if last_text != warning:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id, message_id=progress_message_id, text=warning,
                    )
                    last_text = warning
                except WatchStopped:
                    raise
                except Exception:
                    pass
            delay = min(max(1, WATCH_INTERVAL_SEC) * (2 ** min(failures - 1, 9)), 300)
            await asyncio.sleep(delay)
            continue
        failures = 0
        info = info_list[0] if info_list else None

        if not info:
            DOWNLOAD_HEALTH.forget(t_hash)
            if missing_since is None:
                missing_since = time.monotonic()
            if time.monotonic() - missing_since > WATCH_MISSING_GRACE_SEC:
                err_text = tr("notice.missing", language, title=str(title)[:240])
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_message_id,
                    text=err_text,
                )
                return "missing"
            await asyncio.sleep(WATCH_INTERVAL_SEC)
            continue

        missing_since = None
        name = info.get("name") or title
        state = info.get("state")
        stalled = DOWNLOAD_HEALTH.observe(info)
        text = format_download_progress(info, live=True, stalled=stalled, language=language)
        markup = torrent_navigation(info, getattr(context, "user_id", None), chat_id, language=language) if stalled else None

        if text != last_text:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=progress_message_id,
                    text=text, reply_markup=markup,
                )
                last_text = text
            except WatchStopped:
                raise
            except Exception as e:
                if is_error_state(state):
                    raise
                if "message is not modified" not in str(e).lower():
                    pass

        # Errors may recover after Resume, a recheck or storage repair. Keep watching.

        if is_completed(info):
            markup = torrent_navigation(info, getattr(context, "user_id", None), chat_id, label=tr("notice.details", language), language=language)
            await context.bot.send_message(
                chat_id,
                tr("notice.completed", language, title=download_title(info, 500, language=language),
                   size=human_size(info.get('total_size')), location=download_location(info, language=language)),
                reply_markup=markup,
            )
            return

        await asyncio.sleep(WATCH_INTERVAL_SEC)


# ---- Jackett / Torznab helpers ----
def torznab_items(xml_text: str) -> List[Dict]:
    """
    Robust Torznab parser:
    - supports namespaced or non-namespaced torznab:attr
    - prefers magneturl attr; falls back to <link>
    """
    root = ET.fromstring(xml_text)
    if root.tag != "rss" or root.find("channel") is None or any(
        element.tag.rsplit("}", 1)[-1] == "error" for element in root.iter()
    ):
        raise ValueError("Search response unavailable")
    out: List[Dict] = []

    # channel/item is standard for torznab
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip() or "Untitled"
        link = (item.findtext("link") or "").strip() or None

        try:
            size = int(item.findtext("size") or "")
        except ValueError:
            size = None
        seeders = None
        magnet = None

        # Match any namespace: {anything}attr
        for attr in item.findall(".//{*}attr"):
            name = attr.attrib.get("name")
            val = attr.attrib.get("value")
            if not name or val is None:
                continue
            if name == "size":
                try:
                    size = int(val)
                except Exception:
                    pass
            elif name == "seeders":
                try:
                    seeders = int(val)
                except Exception:
                    pass
            elif name == "magneturl":
                magnet = val

        url = magnet or link
        if not url:
            continue

        out.append(
            {
                "title": title,
                "url": url,
                "size": size,
                "seeders": seeders,
            }
        )
        source = (item.findtext("jackettindexer") or "").strip()
        if source:
            out[-1]["source"] = source

    return out


def jackett_response(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("Results"), list):
        raise ValueError("Search response unavailable")
    items = []
    for row in payload["Results"]:
        if not isinstance(row, dict):
            raise ValueError("Search response unavailable")
        url = row.get("MagnetUri") or row.get("Link")
        if not isinstance(url, str) or not url.startswith(("magnet:?", "http://", "https://")):
            continue
        items.append({
            "title": str(row.get("Title") or "Untitled"), "url": url,
            "size": row.get("Size") if type(row.get("Size")) is int else None,
            "seeders": row.get("Seeders") if type(row.get("Seeders")) is int else None,
            "source": str(row.get("Tracker") or ""),
        })
    if payload["Results"] and not items:
        raise ValueError("Search response unavailable")
    indexers = payload.get("Indexers")
    statuses = [row.get("Status") if isinstance(row, dict) else None for row in indexers] if isinstance(indexers, list) else None
    return SearchResults(items, statuses=statuses)


def _jackett_search_sync(query: str, limit: int = RESULTS_LIMIT) -> List[Dict]:
    parts = urlsplit(JACKETT_TORZNAB_URL)
    # Jackett's manual-search response includes per-query indexer statuses.
    # Custom Torznab URLs retain their existing query semantics, with unknown coverage.
    if not parts.query and re.fullmatch(r".*/api/v2\.0/indexers/[^/]+/results/torznab/api/?", parts.path):
        path = parts.path.rstrip("/")[:-len("/torznab/api")]
        url = urlunsplit(parts._replace(path=path, fragment=""))
        r = requests.get(url, params={"apikey": JACKETT_API_KEY, "query": query}, timeout=(5, JACKETT_SEARCH_TIMEOUT_SEC))
        r.raise_for_status()
        return jackett_response(r.json())
    params = {"apikey": JACKETT_API_KEY, "q": query, "limit": str(limit)}
    r = requests.get(JACKETT_TORZNAB_URL, params=params, timeout=(5, JACKETT_SEARCH_TIMEOUT_SEC))
    r.raise_for_status()
    return SearchResults(torznab_items(r.text))


LAST_SEARCH_HEALTH = None


def jackett_search_sync(query: str, limit: int = RESULTS_LIMIT) -> List[Dict]:
    global LAST_SEARCH_HEALTH
    try:
        results = _jackett_search_sync(query, limit)
    except Exception:
        LAST_SEARCH_HEALTH = {"time": time.time(), "failed": True}
        raise
    LAST_SEARCH_HEALTH = {
        "time": time.time(), "failed": False,
        "responded": getattr(results, "responded", 0), "total": getattr(results, "total", 0),
    }
    return results


def format_torrent_line(t: Dict, *, language="en") -> str:
    name = str(t.get("name") or t.get("hash", "")[:8])[:120]
    state = download_status(t, is_completed(t), language=language)
    progress = "" if t.get("state") in {"metaDL", "forcedMetaDL"} else f"{progress_percent(t)}% · "
    return f"• {name} — {progress}{state}"


# ----------------- telegram handlers -----------------
def language_service(context):
    data = context.application.bot_data
    if "languages" not in data:
        data["languages"] = LanguageService(PreferenceStore(Path(WATCH_DB_PATH).with_suffix(".preferences.sqlite3")))
    return data["languages"]


def language_for_update(update, context):
    if not allowed(update):
        return "en"
    return language_service(context).for_user(update.effective_user.id, getattr(update.effective_user, "language_code", None))


def navigation_keyboard(language="en"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr("nav.search", language), callback_data="nav:search"),
         InlineKeyboardButton(tr("nav.downloads", language), callback_data="nav:downloads")],
        [InlineKeyboardButton(tr("nav.health", language), callback_data="nav:health"),
         InlineKeyboardButton(tr("nav.help", language), callback_data="nav:help")],
        [InlineKeyboardButton("🌐 Language / Язык", callback_data="nav:language")],
    ])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    language = language_for_update(update, context)
    await update.message.reply_text(tr("help.start", language), reply_markup=navigation_keyboard(language), parse_mode=None)


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    await update.message.reply_text(tr("help.search", language_for_update(update, context)), parse_mode=None)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    language = language_for_update(update, context)
    await update.message.reply_text(tr("help.help", language), reply_markup=navigation_keyboard(language), parse_mode=None)


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed(update):
        await LanguagePicker(language_service(context), allowed).open(update, context)


async def on_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if allowed(update):
        await LanguagePicker(language_service(context), allowed).callback(update, context)
    else:
        await update.callback_query.answer()


async def on_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not allowed(update):
        return
    handler = {"nav:search": cmd_search, "nav:downloads": cmd_downloads, "nav:help": cmd_help, "nav:health": cmd_health, "nav:language": cmd_language}.get(query.data)
    if handler:
        # Commands reply to the originating message; callback updates have no .message.
        event = SimpleNamespace(message=query.message, effective_user=update.effective_user,
                                effective_chat=update.effective_chat)
        await handler(event, context)


async def configure_menu(application):
    for language, code in (("en", ""), ("en", "en"), ("ru", "ru")):
        await application.bot.set_my_commands(command_list(language), language_code=code)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    service = getattr(application, "bot_data", {}).get("languages")
    if service:
        for row in service.store.overrides():
            if row["user_id"] in ALLOWED_USERS:
                await set_private_commands(application.bot, row["user_id"], row["override"])


async def application_start(application):
    application.bot_data["languages"] = LanguageService(PreferenceStore(Path(WATCH_DB_PATH).with_suffix(".preferences.sqlite3")))
    try:
        await configure_menu(application)
    except TelegramError as error:
        # Cosmetic registration must not block download monitoring. Retry next startup.
        print("MENU SETUP ERROR:", type(error).__name__)
    await monitoring_start(application)
    try:
        manager = HealthManager(SimpleNamespace(
            allowed=allowed, ALLOWED_USERS=ALLOWED_USERS,
            check_qbit=lambda: check_qbit(qbit_session, QBIT_URL),
            check_jackett=lambda: check_jackett(JACKETT_TORZNAB_URL, JACKETT_API_KEY),
            last_search=lambda: LAST_SEARCH_HEALTH,
            language_for_user=application.bot_data["languages"].for_user,
        ), application.bot, Path(WATCH_DB_PATH).with_suffix(".health.sqlite3"))
        application.bot_data["health"] = manager
        manager.start()
    except Exception as error:
        print("HEALTH START ERROR:", type(error).__name__)


async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    language_for_update(update, context)
    manager = context.application.bot_data.get("health")
    if manager:
        await manager.open(update)
    else:
        await update.message.reply_text(tr("health.not_ready", language_for_update(update, context)))


async def on_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language_for_update(update, context)
    manager = context.application.bot_data.get("health")
    if manager:
        await manager.callback(update)
    else:
        await update.callback_query.answer(tr("health.open_later", language_for_update(update, context)), show_alert=True)


def downloads_dashboard(language_for_user=lambda user: "en"):
    return DownloadsDashboard(SimpleNamespace(
        allowed=allowed, DOWNLOAD_HEALTH=DOWNLOAD_HEALTH, language_for_user=language_for_user,
        qbit_torrents_info_sync=qbit_torrents_info_sync,
        qbit_control_sync=qbit_control_sync, human_eta=human_eta,
        human_size=human_size, human_speed=human_speed, is_completed=is_completed,
    ))


async def cmd_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language_for_update(update, context)
    await downloads_dashboard(language_service(context).for_user).open(update, context)


async def on_downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language_for_update(update, context)
    await downloads_dashboard(language_service(context).for_user).callback(update, context)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not allowed(update):
        return
    language = language_for_update(update, context)

    await update.message.reply_text(tr("status.checking", language))
    try:
        downloading = await asyncio.to_thread(qbit_torrents_info_sync, filter_="downloading", limit=10)
        stalled = await asyncio.to_thread(qbit_torrents_info_sync, filter_="stalled", limit=10)
    except Exception as e:
        await update.message.reply_text(tr("status.failed", language))
        return

    lines = []
    if downloading:
        lines.append(tr("status.downloading", language))
        lines.extend([format_torrent_line(t, language=language) for t in downloading])
    if stalled:
        lines.append(tr("status.waiting", language))
        lines.extend([format_torrent_line(t, language=language) for t in stalled])

    if not lines:
        # покажем последние несколько
        try:
            recent = await asyncio.to_thread(qbit_torrents_info_sync, limit=5)
        except Exception:
            recent = []
        if recent:
            lines.append(tr("status.recent", language))
            lines.extend([format_torrent_line(t, language=language) for t in recent])
        else:
            lines.append(tr("status.empty", language))

    await update.message.reply_text("\n".join(lines))


def search_browser(language_for_user=lambda user: "en"):
    return SearchBrowser(SimpleNamespace(
        language_for_user=language_for_user,
        allowed=allowed, search=jackett_search_sync, limit=RESULTS_LIMIT,
        ttl=SEARCH_TTL_SEC, human_size=human_size, infohash=magnet_infohash_hex,
        add_selected=add_selected, open_downloads=cmd_downloads,
        open_target=lambda event, ctx, target: downloads_dashboard(language_for_user).open_target(event, ctx, target),
    ))


def search_jobs(context):
    return context.application.bot_data.setdefault("search_jobs", SearchJobs(language_service(context).for_user))


async def dispatch_search(update, context):
    if allowed(update):
        language_for_update(update, context)
        await search_jobs(context).start(update, context, on_text)


async def dispatch_pick(update, context):
    if not allowed(update):
        return
    language_for_update(update, context)
    jobs = search_jobs(context)
    if jobs.busy(update.effective_user.id):
        await jobs.unavailable(update)
        return
    data = update.callback_query.data
    actions = [context.user_data.get(key, {}).get("actions", {}).get(data, (None, None))[0]
               for key in ("search", "search_retry")]
    if any(action in ("download", "retry") for action in actions):
        await jobs.start(update, context, on_pick)
    else:
        await on_pick(update, context)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language_for_update(update, context)
    await search_browser(language_service(context).for_user).search(update, context)


def torrent_navigation(info, user_id, chat_id, *, label=None, language="en"):
    label = label or tr("search.open_download", language)
    buttons = []
    if user_id is not None:
        try:
            buttons.append([InlineKeyboardButton(label, callback_data=torrent_link(info, user_id, chat_id, BOT_TOKEN))])
        except ValueError:
            pass
    buttons.append([InlineKeyboardButton(tr("search.all_downloads", language), callback_data="nav:downloads")])
    return InlineKeyboardMarkup(buttons)


async def on_torrent_link(update, context):
    query = update.callback_query
    await query.answer()
    if not allowed(update):
        return
    language = language_for_update(update, context)
    try:
        t_hash = link_hash(query.data)
        rows = await asyncio.to_thread(qbit_torrents_info_sync, hashes=t_hash, limit=1)
        info = next((row for row in rows if row.get("hash") == t_hash), None)
        if not info or not hmac.compare_digest(
            query.data, torrent_link(info, update.effective_user.id, update.effective_chat.id, BOT_TOKEN)
        ):
            raise ValueError("Stale torrent link")
    except Exception:
        await query.message.reply_text(
            tr("download.link_failed", language),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr("search.all_downloads", language), callback_data="nav:downloads")]]),
        )
        return
    event = SimpleNamespace(message=query.message, effective_user=update.effective_user, effective_chat=update.effective_chat)
    # Read-only navigation creates fresh owner/chat/message-bound controls.
    await downloads_dashboard(language_service(context).for_user).detail(event, context, info, 0, initial=True)


async def on_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language_for_update(update, context)
    await search_browser(language_service(context).for_user).callback(update, context)


async def add_selected(update, context, item):
    # Only the search UI consumes Download tokens and presents the outcome.
    try:
        res = await qbit_add_and_confirm(item["url"], title_hint=item["title"])
    except Exception:
        return {"status": "uncertain"}

    exists = bool(res.get("already_exists"))
    if not exists and not (res.get("ok") and res.get("hash")):
        # Never turn an HTTP acknowledgement or raw diagnostics into a success claim.
        return {"status": "uncertain"}
    info = res.get("info") or {}
    watching = None
    if res.get("hash") and (not exists or not is_completed(info)):
        watching = await subscribe_selection(
            update, context, res["hash"], info.get("name") or item["title"],
        )
    return {"status": "exists" if exists else "added", "watching": watching,
            "target": identity(info) if info.get("hash") == res.get("hash") and info.get("hash") else None}


async def subscribe_selection(update, context, t_hash, title):
    try:
        await context.application.bot_data["monitoring"].subscribe(
            update.effective_user.id, update.effective_chat.id, t_hash, title,
        )
        return True
    except Exception as error:
        print("WATCH SUBSCRIBE ERROR:", type(error).__name__)
        return False


async def monitoring_start(application):
    api = SimpleNamespace(
        ALLOWED_USERS=ALLOWED_USERS, WATCH_INTERVAL_SEC=WATCH_INTERVAL_SEC,
        watch_torrent_until_done=watch_torrent_until_done,
        language_for_user=application.bot_data.get("languages").for_user if application.bot_data.get("languages") else (lambda user: "en"),
    )
    manager = WatchManager(api, application.bot, WatchStore(WATCH_DB_PATH))
    application.bot_data["monitoring"] = manager
    await manager.restore()


async def monitoring_stop(application):
    jobs = application.bot_data.get("search_jobs")
    if jobs:
        await jobs.stop()
    health = application.bot_data.get("health")
    if health:
        await health.stop()
    manager = application.bot_data.get("monitoring")
    if manager:
        await manager.stop()


async def monitoring_close(application):
    jobs = application.bot_data.get("search_jobs")
    if jobs:
        await jobs.stop()
    health = application.bot_data.pop("health", None)
    if health:
        await health.close()
    manager = application.bot_data.pop("monitoring", None)
    if manager:
        await manager.close()

    service = application.bot_data.pop("languages", None)
    if service:
        service.store.close()


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    # чтобы бот не падал молча
    try:
        print("ERROR:", type(context.error).__name__)
    except Exception:
        pass


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty (set it in bot.env)")
    if not (JACKETT_TORZNAB_URL and JACKETT_API_KEY):
        raise RuntimeError("Jackett config missing (JACKETT_TORZNAB_URL/JACKETT_API_KEY)")
    if not (QBIT_URL and QBIT_USER and QBIT_PASS):
        raise RuntimeError("qBittorrent config missing (QBIT_URL/QBIT_USER/QBIT_PASS)")
    if not ALLOWED_USERS:
        raise RuntimeError("ALLOWED_USERS is empty (add your Telegram ID)")

    builder = ApplicationBuilder().token(BOT_TOKEN)

    # On some Windows setups, the default HTTPXRequest (httpx/anyio) init may become very slow.
    # If you hit startup hangs, use the aiohttp backend from ptbcontrib:
    #   pip install aiohttp
    #   pip install git+https://github.com/python-telegram-bot/ptbcontrib.git@main
    # You can disable this behavior via PTB_USE_AIOHTTP=0.
    use_aiohttp = os.getenv("PTB_USE_AIOHTTP", "1").lower() not in ("0", "false", "no")
    if use_aiohttp:
        try:
            from ptbcontrib.aiohttp_request import AiohttpRequest
            req = AiohttpRequest()
            builder = builder.request(req).get_updates_request(req)
            print("✅ Using AiohttpRequest backend (ptbcontrib).")
        except Exception as e:
            raise RuntimeError(
                "PTB_USE_AIOHTTP=1 requires ptbcontrib.aiohttp_request.\n"
                "Install the optional dependencies:\n"
                "  pip install aiohttp\n"
                "  pip install git+https://github.com/python-telegram-bot/ptbcontrib.git@main\n"
                f"Error type: {type(e).__name__}"
            )

    builder = builder.post_init(application_start).post_stop(monitoring_stop).post_shutdown(monitoring_close)
    app = builder.build()
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("health", cmd_health))
    app.add_handler(CommandHandler("downloads", cmd_downloads))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, dispatch_search))
    app.add_handler(CallbackQueryHandler(on_language, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(on_navigation, pattern=r"^nav:"))
    app.add_handler(CallbackQueryHandler(on_downloads, pattern=r"^dl:"))
    app.add_handler(CallbackQueryHandler(on_health, pattern=r"^health:"))
    app.add_handler(CallbackQueryHandler(on_torrent_link, pattern=r"^go:"))
    app.add_handler(CallbackQueryHandler(dispatch_pick))
    app.add_error_handler(on_error)

    app.run_polling()


if __name__ == "__main__":
    main()
