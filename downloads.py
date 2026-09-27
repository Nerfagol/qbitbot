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


def title(info, limit=180):
    # Plain text, bounded even for attacker-controlled torrent names.
    return " ".join(str(info.get("name") or "Без названия").split())[:limit]


META = {"metaDL", "forcedMetaDL"}
CHECKING = {"checkingDL", "checkingUP", "checkingResumeData"}
ACTIVE_DOWNLOAD = {"downloading", "forcedDL"}
GROUPS = {
    "attention": "⚠️ Требует внимания",
    "active": "⬇️ В процессе",
    "paused": "⏸ На паузе",
    "completed": "✅ Завершено",
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


def waiting_guidance(info):
    counts = [info.get("num_seeds"), info.get("num_leechs")]
    if all(isinstance(value, int) and value >= 0 for value in counts):
        peers = sum(counts)
        fact = f"Подключённых источников: {peers}." if peers else "Нет подключённых источников."
    else:
        fact = "Число подключённых источников неизвестно."
    reason = (
        "Информация о файлах не получена за 5 минут наблюдения."
        if info.get("state") in META
        else "Нет прогресса скачивания как минимум 5 минут."
    )
    return (
        f"⚠️ {reason}\n{fact}\n"
        "Можно подождать или найти другую раздачу. "
        "В загрузках доступны «Обновить», «Пауза» и «Найти другую раздачу»."
    )


def progress_percent(info):
    return max(0, min(100, int(float(info.get("progress") or 0) * 100)))


def download_status(info, completed=False):
    state = info.get("state")
    if state in CHECKING:
        return "🔍 Проверка файлов"
    if state == "error":
        return "❌ Ошибка загрузки"
    if state == "missingFiles":
        return "❌ Файлы отсутствуют"
    if completed:
        return "✅ Скачивание завершено" + (
            " · ⏸ Раздача приостановлена" if state in PAUSED else ""
        )
    if state in PAUSED:
        return "⏸ Приостановлено"
    if state in META:
        return "🧲 Получение информации о файлах"
    if state == "stalledDL":
        return "⏳ Ожидание источников"
    if state in {"queuedDL", "queuedUP"}:
        return "🕓 В очереди"
    if state in ACTIVE_DOWNLOAD:
        return "⬇️ Скачивается"
    if state in {"uploading", "stalledUP", "forcedUP"}:
        return "⏳ Уточнение завершения"
    return {"moving": "📁 Перемещение файлов", "allocating": "💾 Подготовка места"}.get(
        state, "❔ Состояние уточняется"
    )


def remaining_time(seconds):
    if not isinstance(seconds, (int, float)) or not 0 < seconds < 8640000:
        return "пока неизвестно"
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days} дн {hours} ч"
    if hours:
        return f"{hours} ч {minutes} мин"
    if minutes:
        return f"{minutes} мин {seconds} сек"
    return f"{seconds} сек"


def download_progress(info, api, *, live=False, stalled=False):
    state = info.get("state")
    complete = api.is_completed(info)
    lines = [f"📥 {title(info, 240)}", download_status(info, complete)]
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
                f"💾 Получено: {prefix}{api.human_size(received) or '0B'} из {api.human_size(total)}"
            )
        else:
            lines.append("💾 Размер уточняется")
    if not complete and state in ACTIVE_DOWNLOAD:
        speed = max(0, info.get("dlspeed") or 0)
        speed_text = api.human_speed(speed).replace("/s", "/с") if speed else "0B/с"
        lines.append(f"⬇ Скорость: {speed_text}")
        eta = remaining_time(info.get("eta")) if speed > 0 else "пока неизвестно"
        lines.append(f"⏱ Осталось: {eta}")
    hints = {
        "stalledDL": "Жду подключения источников. Скачивание продолжится автоматически.",
        "queuedDL": "Скачивание начнётся, когда освободится место в очереди.",
        "error": "Открой загрузки и проверь место на диске и доступ к папке.",
        "missingFiles": "Файлы могли быть перемещены или удалены. Проверь папку загрузки.",
    }
    if not complete:
        if stalled and state in META | ACTIVE_DOWNLOAD | {"stalledDL"}:
            lines.append(waiting_guidance(info))
        elif state in PAUSED:
            lines.append("Для продолжения нажми «Продолжить» в загрузках.")
        elif state in META:
            lines.append("Размер и прогресс появятся после получения информации от источников.")
        elif state in CHECKING:
            lines.append("Проверяю уже полученные файлы. Это ещё не подтверждение готовности.")
        elif state in hints:
            lines.append(hints[state])
    if live and not complete and state not in {"error", "missingFiles"}:
        lines.append("🔄 Автообновление при изменениях · управление: /downloads")
    elif not live:
        lines.append(
            "🕒 Данные на " + time.strftime("%H:%M:%S UTC", time.gmtime()) + " · «Обновить»"
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


def download_location(info):
    path = info.get("content_path") or info.get("save_path")
    if not isinstance(path, str) or not path.strip():
        return "📁 Файлы сохранены на устройстве с qBittorrent. Путь пока неизвестен."
    # These are qBittorrent paths; never pretend a container path is a local phone/PC path.
    bounded = path[:600] + ("… (путь сокращён)" if len(path) > 600 else "")
    return f"📁 Расположение в qBittorrent:\n{bounded}"


class DownloadsDashboard:
    def __init__(self, api):
        self.api = api
        self.now = time.monotonic

    async def open(self, update, context):
        if not self.api.allowed(update):
            return
        context.user_data.pop("downloads", None)
        await self.list_view(update, context, 0, initial=True)

    async def open_target(self, update, context, target):
        if not self.api.allowed(update):
            return
        try:
            info = await self.read_target(target)
            if info is None or identity(info) != target:
                await update.message.reply_text(
                    "Загрузка исчезла или изменилась. Открой список загрузок заново.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("📥 Все загрузки", callback_data="nav:downloads")]]
                    ),
                )
                return
            await self.detail(update, context, info, 0, initial=True)
        except Exception:
            await update.message.reply_text(
                "Не удалось открыть загрузку. Попробуй /downloads позже."
            )

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
        try:
            infos = await asyncio.to_thread(self.api.qbit_torrents_info_sync, limit=None)
            waiting = self.api.DOWNLOAD_HEALTH.observe_library(infos)
            groups = {
                info["hash"]: download_group(info, self.api, stalled=waiting[info["hash"]])
                for info in infos
            }
            order = {group: rank for rank, group in enumerate(GROUPS)}
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
                "Не удалось получить загрузки. Попробуй обновить позже.",
                [[("Обновить", ("list", page))]],
                initial=initial,
            )
            return
        pages = max(1, (len(infos) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(0, min(page, pages - 1))
        lines = [note, f"📥 Загрузки — {len(infos)} • страница {page + 1}/{pages}"]
        counts = {group: sum(value == group for value in groups.values()) for group in GROUPS}
        labels = [f"{label}: {counts[group]}" for group, label in GROUPS.items()]
        lines.extend([" · ".join(labels[:2]), " · ".join(labels[2:])])
        choices = []
        previous_group = None
        for number, info in enumerate(
            infos[page * PAGE_SIZE : (page + 1) * PAGE_SIZE], page * PAGE_SIZE + 1
        ):
            group = groups[info["hash"]]
            if group != previous_group:
                lines.append("\n" + GROUPS[group])
                previous_group = group
            pct = progress_percent(info)
            state = download_status(info, self.api.is_completed(info))
            if waiting[info["hash"]]:
                state += (
                    " · ожидание ≥5 мин" if info.get("state") in META else " · нет прогресса ≥5 мин"
                )
            progress = "" if info.get("state") in META else f"{pct}% • "
            lines.append(f"\n{number}. {title(info, 120)}\n{progress}{state}")
            choices.append((str(number), ("detail", identity(info), page)))
        buttons = [choices[start : start + 4] for start in range(0, len(choices), 4)]
        if choices:
            lines.append("\nВыбери номер загрузки ↓")
        if not infos:
            lines.append("Торрентов пока нет.")
        nav = []
        if page:
            nav.append(("← Назад", ("list", page - 1)))
        if page + 1 < pages:
            nav.append(("Далее →", ("list", page + 1)))
        if nav:
            buttons.append(nav)
        buttons.append([("Обновить", ("list", page))])
        await self.render(update, context, "\n".join(filter(None, lines)), buttons, initial=initial)

    async def detail(self, update, context, info, page, note="", *, initial=False):
        state = info.get("state")
        stalled = self.api.DOWNLOAD_HEALTH.observe(info)
        text = (f"{note}\n" + download_progress(info, self.api, stalled=stalled)).strip()
        target = identity(info)
        action, label = ("resume", "▶ Продолжить") if state in PAUSED else ("pause", "⏸ Пауза")
        buttons = [
            [(label, (action, target, page)), ("Обновить", ("detail", target, page))],
            [("🗑 Удалить торрент и файлы", ("ask_delete", target, page))],
            [("← Загрузки", ("list", page))],
        ]
        if not self.api.is_completed(info):
            buttons.insert(1, [("🔎 Найти другую раздачу", ("search", target, page))])
        else:
            text += "\n\n" + download_location(info)
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
        query = update.callback_query
        if not self.api.allowed(update):
            await query.answer("Нет доступа.", show_alert=True)
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
            await query.message.reply_text(
                "Кнопка устарела или принадлежит другому окну. Открой /downloads."
            )
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
                await self.list_view(
                    update, context, page, note="Торрент исчез или изменился. Выбери его заново."
                )
                return
            if kind == "detail":
                await self.detail(update, context, info, page)
            elif kind == "search":
                await self.render(
                    update,
                    context,
                    "🔎 Отправь название и, если знаешь, год — покажу другие варианты.\n"
                    "Текущая загрузка остаётся без изменений.\n\n"
                    f"Сейчас выбрано: {title(info)}",
                    [[("← К загрузке", ("detail", target, page))]],
                )
            elif kind == "ask_delete":
                await self.render(
                    update,
                    context,
                    f"🗑 Удалить торрент и файлы?\n{title(info)}\n\n"
                    "Файлы будут удалены. Это нельзя отменить из бота.",
                    [
                        [("🗑 Подтвердить удаление", ("delete", target, page))],
                        [("Отмена", ("detail", target, page))],
                    ],
                    ttl=CONFIRM_TTL,
                )
            elif kind in ("pause", "resume", "delete"):
                await self.mutate(update, context, kind, target, page)
            else:
                await self.detail(update, context, info, page, note="Операция устарела.")
        except Exception:
            self.api.DOWNLOAD_HEALTH.forget(target[0])
            # The server may have applied a timed-out mutation. Never replay it.
            await self.render(
                update,
                context,
                "Не удалось подтвердить результат. Обнови загрузки перед повторной попыткой.",
                [[("Обновить загрузки", ("list", page))]],
            )

    async def mutate(self, update, context, action, target, page):
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
            note = "Торрент убран. qBittorrent принял удаление файлов."
            await self.list_view(update, context, page, note=note)
        elif info and identity(info) == target:
            await self.detail(
                update,
                context,
                info,
                page,
                note="Изменение подтверждено."
                if confirmed
                else "Изменение пока не подтверждено. Обнови статус.",
            )
        else:
            await self.list_view(
                update,
                context,
                page,
                note="Изменение не подтверждено: торрент исчез или изменился.",
            )
