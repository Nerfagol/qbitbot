"""Short-lived, owner-bound Telegram views for the shared torrent library."""

import asyncio
import base64
import hashlib
import hmac
import json
import re
import secrets
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import tr, normalize_language

PAGE_SIZE = 8
VIEW_TTL = 15 * 60
CONFIRM_TTL = 120
PAUSED = {"stoppedDL", "stoppedUP", "pausedDL", "pausedUP"}
RUNNING = {
    "downloading",
    "uploading",
    "stalledDL",
    "stalledUP",
    "forcedDL",
    "forcedUP",
    "queuedDL",
    "queuedUP",
    "metaDL",
    "forcedMetaDL",
    "allocating",
    "moving",
    "checkingDL",
    "checkingUP",
    "checkingResumeData",
}


def title(info, limit=180, *, language="en"):
    # Plain text, bounded even for attacker-controlled torrent names.
    return " ".join(str(info.get("name") or tr("download.untitled", language)).split())[:limit]


META = {"metaDL", "forcedMetaDL"}
CHECKING = {"checkingDL", "checkingUP", "checkingResumeData"}
ACTIVE_DOWNLOAD = {"downloading", "forcedDL"}


def group_labels(language):
    return {
        "attention": tr("download.group.attention", language),
        "active": tr("download.group.active", language),
        "paused": tr("download.group.paused", language),
        "completed": tr("download.group.completed", language),
    }


def download_group(info, api, *, stalled=False):
    state = info.get("state")
    if state not in RUNNING | PAUSED:
        return "attention"
    if api.is_completed(info):
        return "completed"
    if state in PAUSED:
        return "paused"
    if stalled and state in META | ACTIVE_DOWNLOAD | {"stalledDL"}:
        return "attention"
    return "active"


class DownloadHealth:
    """Conservative, bounded observations; restart/outages begin a fresh interval."""

    def __init__(self, max_gap=90):
        self.now = time.monotonic
        self.max_gap = max_gap
        self.samples = {}

    def forget(self, torrent_hash):
        self.samples.pop(torrent_hash, None)

    def observe_library(self, infos):
        present = {info.get("hash") for info in infos}
        for key in set(self.samples) - present:
            self.forget(key)
        return {info["hash"]: self.observe(info) for info in infos}

    def observe(self, info):
        key = info.get("hash")
        state = info.get("state")
        if not key:
            return False
        if state not in META | ACTIVE_DOWNLOAD | {"stalledDL"}:
            self.forget(key)
            return False
        now = self.now()
        # Full counters avoid treating sub-percent progress as a stall.
        marker = (
            identity(info),
            state in META,
            None
            if state in META
            else tuple(info.get(k) for k in ("downloaded", "amount_left", "progress")),
        )
        previous = self.samples.get(key)
        since = now
        if previous and previous[0] == marker and 0 <= now - previous[2] <= self.max_gap:
            since = previous[1]
        if state not in META and (info.get("dlspeed") or 0) > 0:
            since = now
        if key not in self.samples and len(self.samples) >= 1024:
            self.samples.pop(next(iter(self.samples)))
        self.samples[key] = (marker, since, now)
        return now - since >= 300


def waiting_guidance(info, *, language="en"):
    counts = [info.get("num_seeds"), info.get("num_leechs")]
    if all(isinstance(value, int) and value >= 0 for value in counts):
        peers = sum(counts)
        fact = (
            tr("download.peers.connected", language, v0=peers)
            if peers
            else tr("download.peers.none", language)
        )
    else:
        fact = tr("download.peers.unknown", language)
    reason = (
        tr("download.stalled.metadata", language)
        if info.get("state") in META
        else tr("download.stalled.transfer", language)
    )
    return tr("download.stalled.guidance", language, v0=reason, v1=fact)


def progress_percent(info):
    return max(0, min(100, int(float(info.get("progress") or 0) * 100)))


def download_status(info, completed=False, *, language="en"):
    state = info.get("state")
    if state in CHECKING:
        return tr("download.state.checking", language)
    if state == "error":
        return tr("download.state.error", language)
    if state == "missingFiles":
        return tr("download.state.missing", language)
    if completed:
        return tr("download.state.complete", language) + (
            tr("download.state.sharing_paused", language) if state in PAUSED else ""
        )
    if state in PAUSED:
        return tr("download.state.paused", language)
    if state in META:
        return tr("download.state.metadata", language)
    if state == "stalledDL":
        return tr("download.state.waiting", language)
    if state in {"queuedDL", "queuedUP"}:
        return tr("download.state.queued", language)
    if state in ACTIVE_DOWNLOAD:
        return tr("download.state.downloading", language)
    if state in {"uploading", "stalledUP", "forcedUP"}:
        return tr("download.state.confirming", language)
    return {
        "moving": tr("download.state.moving", language),
        "allocating": tr("download.state.allocating", language),
    }.get(state, tr("download.state.unknown", language))


def remaining_time(seconds, *, language="en"):
    if not isinstance(seconds, (int, float)) or not 0 < seconds < 8640000:
        return tr("download.eta.unknown", language)
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return tr("download.eta.days", language, v0=days, v1=hours)
    if hours:
        return tr("download.eta.hours", language, v0=hours, v1=minutes)
    if minutes:
        return tr("download.eta.minutes", language, v0=minutes, v1=seconds)
    return tr("download.eta.seconds", language, v0=seconds)


def download_progress(info, api, *, live=False, stalled=False, language="en"):
    state = info.get("state")
    complete = api.is_completed(info)
    lines = [
        f"📥 {title(info, 240, language=language)}",
        download_status(info, complete, language=language),
    ]
    pct = progress_percent(info)
    if state not in META:
        filled = pct // 10
        lines.append(f"📊 {'▰' * filled}{'▱' * (10 - filled)} {pct}%")
        total = info.get("size")
        if total is None:
            total = info.get("total_size")
        if isinstance(total, int) and total > 0:
            left = info.get("amount_left")
            if isinstance(left, int) and 0 <= left <= total:
                received, prefix = total - left, ""
            else:
                received, prefix = int(total * pct / 100), "≈ "
            lines.append(
                tr(
                    "download.received",
                    language,
                    v0=prefix,
                    v1=api.human_size(received) or "0B",
                    v2=api.human_size(total),
                )
            )
        else:
            lines.append(tr("download.size_unknown", language))
    if not complete and state in ACTIVE_DOWNLOAD:
        speed = max(0, info.get("dlspeed") or 0)
        speed_text = (
            api.human_speed(speed).replace("/s", tr("download.per_second", language))
            if speed
            else tr("download.zero_speed", language)
        )
        lines.append(tr("download.speed", language, v0=speed_text))
        eta = (
            remaining_time(info.get("eta"), language=language)
            if speed > 0
            else tr("download.eta.unknown", language)
        )
        lines.append(tr("download.remaining", language, v0=eta))
    hints = {
        "stalledDL": tr("download.hint.waiting", language),
        "queuedDL": tr("download.hint.queued", language),
        "error": tr("download.hint.error", language),
        "missingFiles": tr("download.hint.missing", language),
    }
    if not complete:
        if stalled and state in META | ACTIVE_DOWNLOAD | {"stalledDL"}:
            lines.append(waiting_guidance(info, language=language))
        elif state in PAUSED:
            lines.append(tr("download.hint.paused", language))
        elif state in META:
            lines.append(tr("download.hint.metadata", language))
        elif state in CHECKING:
            lines.append(tr("download.hint.checking", language))
        elif state in hints:
            lines.append(hints[state])
    if live and not complete and state not in {"error", "missingFiles"}:
        lines.append(tr("download.auto_update", language))
    elif not live:
        lines.append(
            tr("download.snapshot", language)
            + time.strftime("%H:%M:%S UTC", time.gmtime())
            + tr("download.refresh_hint", language)
        )
    return "\n".join(lines)


def identity(info):
    return (info["hash"], info.get("added_on"), info.get("name"))


def torrent_link(info, user, chat, secret):
    """Read-only link; controls are created only after rechecking the live identity."""
    t_hash = info.get("hash", "")
    if not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", t_hash) or not secret:
        raise ValueError("Invalid torrent link target")
    encoded = base64.urlsafe_b64encode(bytes.fromhex(t_hash)).decode().rstrip("=")
    payload = json.dumps(["torrent-link-v1", user, chat, identity(info)], ensure_ascii=True)
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"go:{encoded}:{signature}"


def link_hash(data):
    match = re.fullmatch(r"go:([A-Za-z0-9_-]{27}|[A-Za-z0-9_-]{43}):[a-f0-9]{16}", data)
    if not match:
        raise ValueError("Invalid torrent link")
    return base64.urlsafe_b64decode(match[1] + "=" * (-len(match[1]) % 4)).hex()


def download_location(info, *, language="en"):
    path = info.get("content_path") or info.get("save_path")
    if not isinstance(path, str) or not path.strip():
        return tr("download.location.unknown", language)
    # These are qBittorrent paths; never pretend a container path is a local phone/PC path.
    bounded = path[:600] + (tr("download.location.shortened", language) if len(path) > 600 else "")
    return tr("download.location.path", language, v0=bounded)


class DownloadsDashboard:
    def __init__(self, api):
        self.api = api
        self.now = time.monotonic

    def language(self, update):
        user = update.effective_user
        fallback = normalize_language(getattr(user, "language_code", None))
        if not user or not self.api.allowed(update):
            return fallback
        return getattr(self.api, "language_for_user", lambda user_id: fallback)(user.id)

    async def open(self, update, context):
        if not self.api.allowed(update):
            return
        context.user_data.pop("downloads", None)
        await self.list_view(update, context, 0, initial=True)

    async def open_target(self, update, context, target):
        language = self.language(update)
        if not self.api.allowed(update):
            return
        try:
            info = await self.read_target(target)
            if info is None or identity(info) != target:
                await update.message.reply_text(
                    tr("download.target_changed", language),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    tr("download.all", language), callback_data="nav:downloads"
                                )
                            ]
                        ]
                    ),
                )
                return
            await self.detail(update, context, info, 0, initial=True)
        except Exception:
            await update.message.reply_text(tr("download.open_failed", language))

    async def render(self, update, context, text, buttons, *, initial=False, ttl=VIEW_TTL):
        token = secrets.token_hex(8)
        actions, rows = {}, []
        for row in buttons:
            rendered = []
            for label, action in row:
                data = f"dl:{token}:{len(actions)}"
                actions[data] = action
                rendered.append(InlineKeyboardButton(label, callback_data=data))
            rows.append(rendered)
        view = {
            "user": update.effective_user.id,
            "chat": update.effective_chat.id,
            "expires": self.now() + ttl,
            "actions": actions,
        }
        # Invalidate previous buttons before awaiting Telegram delivery.
        context.user_data["downloads"] = view
        markup = InlineKeyboardMarkup(rows)
        if initial:
            message = await update.message.reply_text(text, reply_markup=markup, parse_mode=None)
        else:
            message = update.callback_query.message
            await message.edit_text(text, reply_markup=markup, parse_mode=None)
        view["message"] = message.message_id

    async def list_view(self, update, context, page, *, initial=False, note=""):
        language = self.language(update)
        try:
            infos = await asyncio.to_thread(self.api.qbit_torrents_info_sync, limit=None)
            waiting = self.api.DOWNLOAD_HEALTH.observe_library(infos)
            groups = {
                info["hash"]: download_group(info, self.api, stalled=waiting[info["hash"]])
                for info in infos
            }
            order = {group: rank for rank, group in enumerate(group_labels(language))}
            infos.sort(
                key=lambda info: (
                    order[groups[info["hash"]]],
                    -int(info.get("added_on") or 0),
                    info["hash"],
                )
            )
        except Exception:
            self.api.DOWNLOAD_HEALTH.observe_library([])
            await self.render(
                update,
                context,
                tr("download.list_failed", language),
                [[(tr("download.refresh", language), ("list", page))]],
                initial=initial,
            )
            return
        pages = max(1, (len(infos) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, pages - 1))
        lines = [note, tr("download.heading", language, v0=len(infos), v1=page + 1, v2=pages)]
        counts = {
            group: sum(value == group for value in groups.values())
            for group in group_labels(language)
        }
        labels = [f"{label}: {counts[group]}" for group, label in group_labels(language).items()]
        lines.extend([" · ".join(labels[:2]), " · ".join(labels[2:])])
        choices = []
        previous_group = None
        for number, info in enumerate(
            infos[page * PAGE_SIZE : (page + 1) * PAGE_SIZE], page * PAGE_SIZE + 1
        ):
            group = groups[info["hash"]]
            if group != previous_group:
                lines.append("\n" + group_labels(language)[group])
                previous_group = group
            pct = progress_percent(info)
            state = download_status(info, self.api.is_completed(info), language=language)
            if waiting[info["hash"]]:
                state += (
                    tr("download.waiting_marker", language)
                    if info.get("state") in META
                    else tr("download.stalled_marker", language)
                )
            progress = "" if info.get("state") in META else f"{pct}% • "
            lines.append(f"\n{number}. {title(info, 120, language=language)}\n{progress}{state}")
            choices.append((str(number), ("detail", identity(info), page)))
        buttons = [choices[start : start + 4] for start in range(0, len(choices), 4)]
        if choices:
            lines.append(tr("download.select_number", language))
        if not infos:
            lines.append(tr("download.empty", language))
        nav = []
        if page:
            nav.append((tr("download.back", language), ("list", page - 1)))
        if page + 1 < pages:
            nav.append((tr("download.next", language), ("list", page + 1)))
        if nav:
            buttons.append(nav)
        buttons.append([(tr("download.refresh", language), ("list", page))])
        await self.render(update, context, "\n".join(filter(None, lines)), buttons, initial=initial)

    async def detail(self, update, context, info, page, note="", *, initial=False):
        language = self.language(update)
        state = info.get("state")
        stalled = self.api.DOWNLOAD_HEALTH.observe(info)
        text = (
            f"{note}\n" + download_progress(info, self.api, stalled=stalled, language=language)
        ).strip()
        target = identity(info)
        action, label = (
            ("resume", tr("download.resume", language))
            if state in PAUSED
            else ("pause", tr("download.pause", language))
        )
        buttons = [
            [
                (label, (action, target, page)),
                (tr("download.refresh", language), ("detail", target, page)),
            ],
            [(tr("download.delete", language), ("ask_delete", target, page))],
            [(tr("download.back_list", language), ("list", page))],
        ]
        if not self.api.is_completed(info):
            buttons.insert(1, [(tr("download.find_another", language), ("search", target, page))])
        else:
            text += "\n\n" + download_location(info, language=language)
        await self.render(update, context, text, buttons, initial=initial)

    async def read_target(self, target):
        infos = await asyncio.to_thread(self.api.qbit_torrents_info_sync, hashes=target[0], limit=1)
        info = next((info for info in infos if info.get("hash") == target[0]), None)
        if info:
            self.api.DOWNLOAD_HEALTH.observe(info)
        else:
            self.api.DOWNLOAD_HEALTH.forget(target[0])
        return info

    async def callback(self, update, context):
        language = self.language(update)
        query = update.callback_query
        if not self.api.allowed(update):
            await query.answer(tr("download.denied", language), show_alert=True)
            return
        await query.answer()
        view = context.user_data.get("downloads", {})
        if (
            view.get("user") != update.effective_user.id
            or view.get("chat") != update.effective_chat.id
            or view.get("message") != getattr(query.message, "message_id", None)
            or self.now() >= view.get("expires", 0)
            or query.data not in view.get("actions", {})
        ):
            # Do not overwrite another user's dashboard.
            await query.message.reply_text(tr("download.stale", language))
            return
        action = view["actions"][query.data]
        view["actions"] = {}  # Consume once, before any I/O or mutation.
        kind = action[0]
        if kind == "list":
            await self.list_view(update, context, action[1])
            return
        _, target, page = action
        try:
            info = await self.read_target(target)
            if info is None or identity(info) != target:
                self.api.DOWNLOAD_HEALTH.forget(target[0])
                await self.list_view(update, context, page, note=tr("download.changed", language))
                return
            if kind == "detail":
                await self.detail(update, context, info, page)
            elif kind == "search":
                await self.render(
                    update,
                    context,
                    tr("download.alternative", language, v0=title(info, language=language)),
                    [[(tr("download.back_detail", language), ("detail", target, page))]],
                )
            elif kind == "ask_delete":
                await self.render(
                    update,
                    context,
                    tr("download.confirm_question", language, v0=title(info, language=language)),
                    [
                        [(tr("download.confirm_delete", language), ("delete", target, page))],
                        [(tr("download.cancel", language), ("detail", target, page))],
                    ],
                    ttl=CONFIRM_TTL,
                )
            elif kind in ("pause", "resume", "delete"):
                await self.mutate(update, context, kind, target, page)
            else:
                await self.detail(
                    update, context, info, page, note=tr("download.operation_stale", language)
                )
        except Exception:
            self.api.DOWNLOAD_HEALTH.forget(target[0])
            # The server may have applied a timed-out mutation. Never replay it.
            await self.render(
                update,
                context,
                tr("download.uncertain", language),
                [[(tr("download.refresh_all", language), ("list", page))]],
            )

    async def mutate(self, update, context, action, target, page):
        language = self.language(update)
        if action not in ("pause", "resume", "delete"):
            raise ValueError("Unsupported dashboard action")
        await asyncio.to_thread(self.api.qbit_control_sync, action, target[0])
        self.api.DOWNLOAD_HEALTH.forget(target[0])
        info, confirmed = None, False
        for attempt in range(5):
            info = await self.read_target(target)
            if action == "delete":
                confirmed = info is None
            elif info and identity(info) == target:
                confirmed = info.get("state") in (PAUSED if action == "pause" else RUNNING)
            if confirmed:
                break
            if attempt < 4:
                await asyncio.sleep(0.4)
        if action == "delete" and confirmed:
            manager = context.application.bot_data.get("monitoring")
            if manager:
                await manager.removed(target[0])
            note = tr("download.deleted", language)
            await self.list_view(update, context, page, note=note)
        elif info and identity(info) == target:
            await self.detail(
                update,
                context,
                info,
                page,
                note=tr("download.confirmed", language)
                if confirmed
                else tr("download.not_confirmed", language),
            )
        else:
            await self.list_view(
                update,
                context,
                page,
                note=tr("download.changed_unconfirmed", language),
            )
