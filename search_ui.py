"""Ephemeral, owner-bound search pages and explicit download confirmation."""

import asyncio
import math
import re
import secrets
import time
from types import SimpleNamespace

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

PAGE_SIZE = 5
ENOUGH_SOURCES = 25
QUALITY_FILTERS = {"any": "Любое качество", "1080p": "1080p", "4K": "4K"}
SIZE_FILTERS = {0: "Любой размер", 5: "До 5 ГБ", 10: "До 10 ГБ", 20: "До 20 ГБ"}


class SearchResults(list):
    """List-compatible results with safe per-query coverage counts, never raw errors."""

    def __init__(self, items=(), *, statuses=None):
        super().__init__(items)
        self.total = len(statuses) if statuses is not None else 0
        self.responded = sum(type(s) is int and s == 2 for s in statuses or [])
        failed = sum(type(s) is int and s == 1 for s in statuses or [])
        self.availability = (
            "complete"
            if self.total and self.responded == self.total
            else "partial"
            if self.responded
            else "unavailable"
            if self.total and failed == self.total
            else "unknown"
        )


def search_notice(results):
    status = getattr(results, "availability", "unknown")
    if status == "complete":
        return f"📡 Ответили поисковые источники: {results.responded} из {results.total}."
    if status == "partial":
        return f"⚠️ Поиск неполный: ответили {results.responded} из {results.total} источников."
    if status == "unavailable":
        return "⚠️ Поиск временно недоступен: поисковые источники не ответили успешно."
    return "📡 Состояние поисковых источников неизвестно."


SORTS = {
    "recommended": "⭐ Рекомендуемые",
    "quality": "🎬 Качество",
    "original": "🔎 Порядок поиска",
    "seeds": "🌱 Источники ↓",
    "small": "💾 Размер ↑",
    "large": "💾 Размер ↓",
}
# Delimited release tokens only; resolution is inferred, not a verified media property.
QUALITY_TIERS = (
    (9, "4K", r"2160p|4k|uhd"),
    (8, "1440p", r"1440p"),
    (7, "1080p", r"1080p"),
    (6, "1080i", r"1080i"),
    (5, "720p", r"720p"),
    (4, "576p", r"576p"),
    (3, "480p", r"480p"),
    (2, "SD", r"sd|dvdrip"),
)


def quality(title):
    # A terminal .ts can be a transport-stream filename, not a telesync label.
    text = re.sub(r"\.ts$", "", str(title or "").strip(), flags=re.I)

    def matches(pattern):
        return re.search(r"(?<![^\W_])(?:" + pattern + r")(?![^\W_])", text, re.I)

    # A camera recording must not be promoted just because it also advertises 1080p.
    if matches(r"cam|hdcam|camrip|telesync|hdts|ts"):
        return 1, "CAM/TS"
    for rank, label, pattern in QUALITY_TIERS:
        if matches(pattern):
            return rank, label
    return 0, "—"


def source_count(item):
    value = item.get("seeders")
    return value if isinstance(value, int) and value >= 0 else None


def availability(item):
    seeds = source_count(item)
    if seeds is None:
        return "⚪ Источники неизвестны"
    if seeds == 0:
        return "🔴 Нет источников"
    if seeds < 5:
        return "🟡 Мало источников"
    if seeds < 20:
        return "🟢 Есть источники"
    return "🟢 Много источников"


def recommended_key(item):
    """Product heuristic over the fetched set, never a download-speed guarantee."""
    seeds = source_count(item)
    # Prefer known available releases; unknown availability is distinct from zero.
    band = 2 if seeds is None else 3 if seeds == 0 else 1 if seeds < 5 else 0
    rank, _ = quality(item.get("title"))
    size = item.get("size")
    known_size = isinstance(size, int) and size > 0
    if seeds is not None and seeds >= ENOUGH_SOURCES and rank != 1:
        # Once availability is sufficient, extra sources do not outrank quality/size.
        return (0, -rank, not known_size, size if known_size else 0, 0)
    if rank == 1:
        band += 2  # A busy camera recording is still a poor default recommendation.
    quality_points = {9: 22, 8: 22, 7: 24, 6: 20, 5: 18, 4: 10, 3: 8, 2: 8, 1: -20, 0: 6}
    size = item.get("size")
    size_points = 0
    if isinstance(size, int) and size > 0:
        gib = size / (1024**3)
        size_points = 12 if gib <= 4 else 8 if gib <= 10 else 2 if gib <= 20 else -12
    # Saturation stops huge reported swarm counts from overwhelming size/quality.
    seed_points = min(20, 3 * math.log2(min(seeds or 0, 1024) + 1))
    return 1, band, -(quality_points[rank] + size_points + seed_points), -(seeds or 0), 0


def quality_label(item):
    _, label = quality(item.get("title"))
    return {
        "4K": "Ultra HD (4K)",
        "1440p": "Высокое разрешение",
        "1080p": "Full HD",
        "1080i": "Full HD",
        "720p": "HD",
        "576p": "Обычное качество",
        "480p": "Обычное качество",
        "SD": "Обычное качество",
        "CAM/TS": "Экранная запись",
        "—": "Качество неизвестно",
    }[label]


STALE = "Список устарел. Отправь запрос ещё раз через /search."


def compact(value, limit):
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def release_details(value):
    """Conservative title hints, not verified media metadata; retain ambiguous names."""
    original = str(value or "Без названия")
    text = compact(original, len(original) + 1)
    details = {"heading": text, "episode": None, "audio": None}

    def release_tail(tail):
        tail = tail.lstrip(" ._)]}-")
        return not tail or re.match(
            r"(?:2160p|4k|uhd|1440p|1080[pi]|720p|576p|480p|"
            r"web[- .]?dl|webrip|bluray|bdrip|dvdrip|hdtv)(?!\w)",
            tail,
            re.I,
        )

    episodes = list(
        re.finditer(
            r"(?<!\w)S(\d{1,2})(?:E(\d{1,3})(?:-E?(\d{1,3}))?)?(?!\w|[- ]?[SE]\d)",
            text,
            re.I,
        )
    )
    episode = episodes[0] if len(episodes) == 1 else None
    if (
        episode
        and text[: episode.start()].strip(" ._([{-")
        and not re.search(r"[SE]\d{1,3}[- ]$", text[: episode.start()], re.I)
        and release_tail(text[episode.end() :])
    ):
        season, first, last = episode.groups()
        details["episode"] = f"Сезон {int(season)}"
        if first:
            details["episode"] += (
                f" · Серии {int(first)}–{int(last)}" if last else f" · Серия {int(first)}"
            )
    else:
        episode = None

    cutoff, year = None, None
    for candidate in reversed(list(re.finditer(r"(?<!\w)(?:19|20)\d{2}(?!\w)", text))):
        tail = text[candidate.end() :]
        if episode and candidate.end() <= episode.start():
            tail = text[candidate.end() : episode.start()]
        prefix = text[: candidate.start()].rstrip(" ._([{-")
        if prefix and release_tail(tail):
            bracket = text[candidate.start() - 1 : candidate.start()]
            if (
                bracket in ("(", "[")
                and text[candidate.end() : candidate.end() + 1] == {"(": ")", "[": "]"}[bracket]
            ):
                cutoff, year = candidate.start(), candidate.group()
            else:
                # A bare number may belong to the title (Space Ranger 2049).
                # Keep it as title text, never turn it into a claimed release year.
                cutoff = candidate.end()
            break
    if cutoff is None and episode:
        cutoff = episode.start()
    if cutoff is not None:
        heading = text[:cutoff].rstrip(" ._([{-")
        heading = re.sub(r"_|(?<!\d)\.|\.(?!\d)", " ", heading)
        heading = " ".join(heading.split())
        details["heading"] = heading + (f" ({year})" if year else "")

    # Explicit labelled audio fields only. RUS/ENG elsewhere may describe subtitles
    # or even be part of the film name; tracker identity cannot establish language.
    audio_fields = re.findall(
        r"(?:^|[\s\[(;])(?:audio|звук|аудио|озвучка)\s*:\s*([^\]);|\n]{1,100})",
        original,
        re.I,
    )
    language = r"(?:rus|russian|русский|русская|eng|english|английский|английская)"
    # Accept complete language lists only. Prose, unknown terms, negations or
    # subtitle annotations make the field ambiguous, so leave it out entirely.
    audio = " ".join(
        field
        for field in audio_fields
        if re.fullmatch(rf"\s*{language}(?:\s*[/,+&]\s*{language})*\s*", field, re.I)
    )
    languages = []
    for pattern, label in (
        (r"rus|russian|русский|русская", "Русский"),
        (r"eng|english|английский|английская", "английский"),
    ):
        if re.search(r"(?<!\w)(?:" + pattern + r")(?!\w)", audio, re.I):
            languages.append(label)
    if languages:
        details["audio"] = ", ".join(languages).capitalize()
    return details


def matches_filters(item, session):
    resolution = session.get("quality_filter", "any")
    if resolution != "any" and quality(item.get("title"))[1] != resolution:
        return False
    ceiling = session.get("size_filter", 0)
    size = item.get("size")
    return not ceiling or (isinstance(size, int) and 0 < size <= ceiling * 1024**3)


class SearchBrowser:
    def __init__(self, api):
        self.api = api

    def session(self, update, message, query):
        return {
            "user": update.effective_user.id,
            "chat": update.effective_chat.id,
            "message": message.message_id,
            "expires": time.monotonic() + self.api.ttl,
            "query": query,
            "actions": {},
        }

    async def render(self, message, session, text, buttons):
        token = secrets.token_hex(8)
        actions, rows = {}, []
        for row in buttons:
            rendered = []
            for label, action in row:
                data = f"sr:{token}:{len(actions)}"
                actions[data] = action
                rendered.append(InlineKeyboardButton(label, callback_data=data))
            rows.append(rendered)
        # Never leave a previously valid Download token active during an edit.
        session["actions"] = {}
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(rows),
            parse_mode=None,
            disable_web_page_preview=True,
        )
        session["actions"] = actions

    async def search(self, update, context, query=None, message=None):
        if not self.api.allowed(update):
            return
        query = query if query is not None else (update.message.text or "").strip()
        if not query:
            return
        if message is None:
            message = await update.message.reply_text(
                "👀 Ищу… Индексаторам может понадобиться время."
            )
        else:
            await message.edit_text(
                "👀 Ищу… Индексаторам может понадобиться время.", reply_markup=None
            )
        request = secrets.token_hex(8)
        context.user_data["search_request"] = request
        session = self.session(update, message, query)
        failure = "Поиск временно недоступен. Попробуй ещё раз."
        try:
            results = await asyncio.to_thread(self.api.search, query, self.api.limit)
        except requests.Timeout:
            results = None
            failure = "Поиск не успел завершиться. Попробуй ещё раз."
        except Exception:
            results = None
        if context.user_data.get("search_request") != request:
            await message.edit_text(
                "Открыт более новый поиск. Используй его результаты.", reply_markup=None
            )
            return
        if not results:
            status = getattr(results, "availability", "unknown")
            if results is None:
                text = failure
            elif status == "complete":
                text = "Ничего не нашёл 😕 Попробуй уточнить название или год.\n" + search_notice(
                    results
                )
            elif status == "partial":
                text = (
                    search_notice(results)
                    + "\nВ ответивших источниках ничего не найдено. Попробуй повторить поиск."
                )
            elif status == "unavailable":
                text = search_notice(results) + "\nПопробуй повторить позже."
            else:
                text = (
                    "Ничего не нашёл в полученном ответе.\n"
                    + search_notice(results)
                    + "\nУточни запрос или повтори позже."
                )
            if context.user_data.get("search"):
                text += "\nПредыдущие результаты остаются доступны до истечения срока кнопок."
            await self.render(
                message,
                session,
                text,
                [[("🔄 Повторить", ("retry", None)), ("🔎 Изменить запрос", ("new", None))]],
            )
            context.user_data["search_retry"] = session
            return
        unique, seen = [], set()
        for item in results:
            identity = self.api.infohash(item.get("url") or "")
            if identity and identity in seen:
                continue
            if identity:
                seen.add(identity)
            unique.append(dict(item))
            if len(unique) >= self.api.limit:
                break
        session.update(
            results=unique,
            page=0,
            sort="recommended",
            show_sorts=False,
            show_filters=False,
            quality_filter="any",
            size_filter=0,
            search_notice=search_notice(results),
            search_incomplete=getattr(results, "availability", "unknown")
            in {"partial", "unavailable"},
        )
        await self.list_view(message, session)
        # Replace the previous session only once the new results were delivered.
        context.user_data["search"] = session
        context.user_data.pop("search_retry", None)

    def ordered(self, session):
        indices = [
            index for index, item in enumerate(session["results"]) if matches_filters(item, session)
        ]
        mode = session["sort"]
        if mode == "original":
            return indices
        if mode == "recommended":
            ordered = sorted(indices, key=lambda index: recommended_key(session["results"][index]))
            # Make both common quality choices visible without adding duplicates or
            # promoting poorly seeded entries just to fill a slot.
            reserved = set()
            for rank in (9, 7):
                candidates = [
                    index
                    for index in ordered
                    if quality(session["results"][index].get("title"))[0] == rank
                    and (source_count(session["results"][index]) or 0) >= ENOUGH_SOURCES
                ]
                reserved.update(candidates[:2])
            for index in ordered:
                if len(reserved) >= PAGE_SIZE:
                    break
                reserved.add(index)
            return [index for index in ordered if index in reserved] + [
                index for index in ordered if index not in reserved
            ]
        field = "seeders" if mode in ("quality", "seeds") else "size"

        def key(index):
            value = session["results"][index].get(field)
            known = isinstance(value, int) and (value >= 0 if field == "seeders" else value > 0)
            tie = (not known, (value if mode == "small" else -value) if known else 0)
            if mode == "quality":
                return (-quality(session["results"][index].get("title"))[0], *tie)
            return tie

        return sorted(indices, key=key)

    def metadata(self, item, *, preview=False):
        size = item.get("size")
        size_text = (
            self.api.human_size(size) if isinstance(size, int) and size > 0 else "неизвестно"
        )
        seeds = source_count(item)
        label = quality_label(item)
        if preview:
            raw = quality(item.get("title"))[1]
            exact = str(seeds) if seeds is not None else "неизвестно"
            return (
                f"🎬 Качество: {label} ({raw}, по названию)\n💾 Размер: {size_text}\n"
                f"{availability(item)}\nПолных источников: {exact}"
            )
        return f"🎬 {label} · 💾 {size_text} · {availability(item)}"

    async def list_view(self, message, session):
        indices = self.ordered(session)
        pages = max(1, (len(indices) + PAGE_SIZE - 1) // PAGE_SIZE)
        page = session["page"] = max(0, min(session["page"], pages - 1))
        resolution, ceiling = session.get("quality_filter", "any"), session.get("size_filter", 0)
        filtered = resolution != "any" or bool(ceiling)
        count = f"{len(indices)} из {len(session['results'])}" if filtered else str(len(indices))
        lines = [
            f"🔎 {compact(session['query'], 140)}",
            f"📋 {count} результатов" + (f" · 📄 Страница {page + 1}/{pages}" if indices else ""),
            f"{SORTS[session['sort']]}",
        ]
        if session.get("search_notice"):
            lines.append(session["search_notice"])
        if filtered:
            lines.append(f"🎛 {QUALITY_FILTERS[resolution]} · {SIZE_FILTERS[ceiling]}")
        if filtered or session.get("show_filters"):
            lines.append("Фильтры — по найденным вариантам; качество — по названию.")
        if not indices:
            lines.append(
                "\nПо этим фильтрам в найденных результатах ничего нет. Измени или сбрось фильтры."
            )
        buttons, selections = [], []
        for position in range(page * PAGE_SIZE, min((page + 1) * PAGE_SIZE, len(indices))):
            index = indices[position]
            item = session["results"][index]
            title = item.get("title") or "Без названия"
            lines.append(f"\n{position + 1}. {compact(title, 140)}\n{self.metadata(item)}")
            selections.append((str(position + 1), ("preview", index)))
        if selections:
            buttons.append(selections)
        navigation = []
        if page:
            navigation.append(("← Назад", ("page", page - 1)))
        if page + 1 < pages:
            navigation.append(("Далее →", ("page", page + 1)))
        if navigation:
            buttons.append(navigation)
        if session.get("show_sorts"):
            for modes in (("recommended", "quality"), ("seeds", "original"), ("small", "large")):
                buttons.append(
                    [
                        (("✓ " if session["sort"] == mode else "") + SORTS[mode], ("sort", mode))
                        for mode in modes
                    ]
                )
        if session.get("show_filters"):
            for field, options in (
                ("quality_filter", QUALITY_FILTERS),
                ("size_filter", SIZE_FILTERS),
            ):
                buttons.append(
                    [
                        (
                            (
                                "✓ "
                                if session.get(field, "any" if field == "quality_filter" else 0)
                                == value
                                else ""
                            )
                            + label,
                            (field, value),
                        )
                        for value, label in options.items()
                    ]
                )
        if filtered:
            buttons.append([("↺ Сбросить фильтры", ("reset_filters", None))])
        if session.get("search_incomplete"):
            buttons.append([("🔄 Повторить поиск", ("retry", None))])
        buttons.append(
            [
                (
                    "✖ Скрыть сортировку" if session.get("show_sorts") else "↕️ Сортировка",
                    ("sort_menu", None),
                ),
                (
                    "✖ Скрыть фильтры" if session.get("show_filters") else "🎛 Фильтры",
                    ("filter_menu", None),
                ),
                ("🔎 Новый поиск", ("new", None)),
            ]
        )
        if indices:
            lines.append("\n👇 Нажми номер для просмотра")
        await self.render(message, session, "\n".join(lines), buttons)

    async def preview(self, message, session, index):
        item = session["results"][index]
        details = release_details(item.get("title"))
        text = (
            f"📄 {compact(details['heading'], 1000)}\n\n"
            f"{self.metadata(item, preview=True)}\n📡 Трекер: {compact(item.get('source') or 'не указан', 100)}"
        )
        if details["episode"]:
            text += f"\n📺 {details['episode']} (по названию)"
        if details["audio"]:
            text += f"\n🔊 Аудио: {details['audio']} (по названию)"
        text += "\n\nДобавить этот торрент в загрузки?"
        buttons = [
            [("⬇ Скачать", ("download", index))],
            [("📄 Исходное название", ("original_name", (index, 0)))],
            [("← К результатам", ("list", None)), ("🔎 Новый поиск", ("new", None))],
        ]
        await self.render(message, session, text, buttons)

    async def original_name(self, message, session, index, page):
        original = str(session["results"][index].get("title") or "Без названия")
        # 1400 characters fit even if every character occupies two UTF-16 units.
        pages = max(1, (len(original) + 1399) // 1400)
        page = max(0, min(page, pages - 1))
        text = (
            f"📄 Исходное название · {page + 1}/{pages}\n\n"
            + original[page * 1400 : (page + 1) * 1400]
        )
        navigation = []
        if page:
            navigation.append(("← Назад", ("original_name", (index, page - 1))))
        if page + 1 < pages:
            navigation.append(("Далее →", ("original_name", (index, page + 1))))
        buttons = [navigation] if navigation else []
        buttons.append([("← К описанию", ("preview", index))])
        await self.render(message, session, text, buttons)

    async def feedback(self, message, session, index, outcome):
        status = outcome.get("status")
        heading = {"added": "✅ Добавлено в загрузки", "exists": "ℹ️ Уже есть в загрузках"}.get(
            status, "⚠️ Добавление пока не подтверждено"
        )
        text = f"{heading}\n\n{compact(session['results'][index].get('title'), 1000)}"
        if status not in ("added", "exists"):
            text += "\n\nОткрой загрузки перед повторной попыткой: торрент мог уже добавиться."
        elif outcome.get("watching") is False:
            text += "\n\n⚠️ Не удалось подтвердить уведомления. Проверяй прогресс в загрузках."
        elif outcome.get("watching") is True:
            text += "\n\n🔔 Сообщу, когда скачивание завершится."
        buttons = []
        if outcome.get("target"):
            buttons.append([("📥 Открыть эту загрузку", ("target", outcome["target"]))])
        buttons += [
            [("📥 Все загрузки", ("downloads", None))],
            [("← К результатам", ("list", None)), ("🔎 Новый поиск", ("new", None))],
        ]
        await self.render(message, session, text, buttons)

    async def callback(self, update, context):
        if not self.api.allowed(update):
            return
        query = update.callback_query
        await query.answer()
        session = None
        for key in ("search", "search_retry"):
            candidate = context.user_data.get(key, {})
            if (
                candidate.get("user") == update.effective_user.id
                and candidate.get("chat") == update.effective_chat.id
                and candidate.get("message") == query.message.message_id
                and time.monotonic() < candidate.get("expires", 0)
                and query.data in candidate.get("actions", {})
            ):
                session = candidate
                break
        if session is None:
            await query.message.reply_text(STALE)
            return
        action, value = session["actions"][query.data]
        if action in ("downloads", "target"):
            event = SimpleNamespace(
                message=query.message,
                effective_user=update.effective_user,
                effective_chat=update.effective_chat,
            )
            if action == "target":
                await self.api.open_target(event, context, value)
            else:
                await self.api.open_downloads(event, context)
            return
        if action == "new":
            # This prompt does not change the current view, including Retry buttons.
            await query.message.reply_text("🔎 Отправь новый запрос — название и, если нужно, год.")
            return
        preserve_results = action == "retry" and bool(session.get("results"))
        if preserve_results:
            # Consume Retry once, keeping selection/navigation in the old list
            # usable until a successful replacement has actually been delivered.
            session["actions"].pop(query.data)
        else:
            session["actions"] = {}  # Consume before any await, including mutation.
        try:
            if action == "retry":
                message = (
                    await query.message.reply_text("👀 Повторяю поиск…")
                    if preserve_results
                    else query.message
                )
                await self.search(update, context, session["query"], message)
            elif action == "preview":
                await self.preview(query.message, session, value)
            elif action == "original_name":
                await self.original_name(query.message, session, *value)
            elif action == "download":
                await query.message.edit_text("⏳ Добавляю выбранный торрент…", reply_markup=None)
                outcome = await self.api.add_selected(update, context, session["results"][value])
                await self.feedback(query.message, session, value, outcome)
            else:
                if action == "sort":
                    session.update(sort=value, page=0, show_sorts=False)
                elif action == "sort_menu":
                    session["show_sorts"] = not session.get("show_sorts", False)
                    session["show_filters"] = False
                elif action == "filter_menu":
                    session["show_filters"] = not session.get("show_filters", False)
                    session["show_sorts"] = False
                elif action in ("quality_filter", "size_filter"):
                    session.update({action: value, "page": 0})
                elif action == "reset_filters":
                    session.update(quality_filter="any", size_filter=0, page=0)
                elif action == "page":
                    session["page"] = value
                await self.list_view(query.message, session)
        except TelegramError:
            await query.message.reply_text(
                "Не удалось обновить сообщение. Открой /search заново; "
                "если нажимал «Скачать», сначала проверь /downloads."
            )
