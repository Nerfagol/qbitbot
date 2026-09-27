"""Exercise the actual dashboard against a stateful fake qBittorrent boundary."""

import asyncio
import importlib
from types import SimpleNamespace

import pytest
import requests

from tests.helpers import torrent
from tests.test_persistence import async_test


class Message:
    def __init__(self):
        self.message_id = 77
        self.text = ""
        self.markup = None

    async def reply_text(self, text, reply_markup=None, **kwargs):
        self.text, self.markup = text, reply_markup
        return self

    async def edit_text(self, text, reply_markup=None, **kwargs):
        self.text, self.markup = text, reply_markup
        return self

    def button(self, label):
        return next(
            b.callback_data for row in self.markup.inline_keyboard for b in row if label in b.text
        )


class Library:
    def __init__(self):
        self.rows = {"a" * 40: torrent(added_on=123)}
        self.actions = []
        self.apply = True

    def read(self, *, hashes=None, **kwargs):
        return [dict(row) for key, row in self.rows.items() if not hashes or key == hashes]

    def control(self, action, t_hash):
        self.actions.append((action, t_hash))
        if not self.apply:
            return
        if action in ("keep", "delete"):
            self.rows.pop(t_hash, None)
        else:
            self.rows[t_hash]["state"] = "stoppedDL" if action == "pause" else "downloading"


def setup(bot, monkeypatch):
    module = importlib.import_module("downloads")
    library = Library()
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", library.read)
    monkeypatch.setattr(bot, "qbit_control_sync", library.control)
    dashboard = module.DownloadsDashboard(bot)
    message = Message()
    ctx = SimpleNamespace(user_data={}, application=SimpleNamespace(bot_data={}))
    event = SimpleNamespace(
        message=message,
        effective_chat=SimpleNamespace(id=303),
        effective_user=SimpleNamespace(id=101),
        callback_query=None,
    )
    return dashboard, library, message, ctx, event


async def click(dashboard, event, ctx, data):
    async def answer(*args, **kwargs):
        pass

    event.callback_query = SimpleNamespace(data=data, message=event.message, answer=answer)
    await dashboard.callback(event, ctx)


@async_test
async def test_pause_resume_uses_selected_hash_after_list_reordering(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    await dashboard.open(event, ctx)
    pick = message.button("1")
    library.rows = {"b" * 40: torrent(hash="b" * 40, name="New"), **library.rows}
    await click(dashboard, event, ctx, pick)
    await click(dashboard, event, ctx, message.button("Пауза"))
    assert library.actions == [("pause", "a" * 40)]
    assert "Приостановлено" in message.text
    await click(dashboard, event, ctx, message.button("Продолжить"))
    assert library.actions[-1] == ("resume", "a" * 40)
    assert "Скачивается" in message.text


@async_test
async def test_stuck_detail_offers_non_mutating_search_and_keeps_controls(bot, monkeypatch):
    from tests.test_download_health import sample_until

    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    info = library.rows["a" * 40]
    info.update(state="metaDL", dlspeed=0, num_seeds=0, num_leechs=0)
    assert sample_until(bot.DOWNLOAD_HEALTH, info)
    await dashboard.open(event, ctx)
    await click(dashboard, event, ctx, message.button("1"))
    assert "5 минут" in message.text
    assert message.button("Пауза") and message.button("Обновить")
    await click(dashboard, event, ctx, message.button("Найти другую раздачу"))
    assert "название" in message.text and "год" in message.text
    assert not library.actions and len(library.rows) == 1


@async_test
@pytest.mark.parametrize("interruption", ["pause", "progress", "missing", "outage", "search"])
async def test_dashboard_observations_reset_waiting_timer(bot, monkeypatch, interruption):
    from tests.test_download_health import sample_until

    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    info = library.rows["a" * 40]
    info.update(dlspeed=0)
    await dashboard.open(event, ctx)
    await click(dashboard, event, ctx, message.button("1"))
    health = bot.DOWNLOAD_HEALTH
    assert not sample_until(health, info, 240)
    health.now = lambda: 270
    if interruption == "outage":

        def unavailable(**kw):
            raise requests.ConnectionError()

        monkeypatch.setattr(bot, "qbit_torrents_info_sync", unavailable)
    elif interruption == "missing":
        library.rows.clear()
    elif interruption == "progress":
        info["amount_left"] -= 1
    else:
        info["state"] = "stoppedDL"
    if interruption == "search":
        await click(dashboard, event, ctx, message.button("Найти другую раздачу"))
    else:
        await dashboard.open(event, ctx)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", library.read)
    library.rows[info["hash"]] = info
    info["state"] = "downloading"
    health.now = lambda: 300
    assert not health.observe(info)


@async_test
async def test_deletion_requires_explicit_single_use_confirmation(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    await dashboard.open(event, ctx)
    await click(dashboard, event, ctx, message.button("1"))
    await click(dashboard, event, ctx, message.button("Удалить торрент и файлы"))
    assert not library.actions
    assert "Test download" in message.text
    assert "Файлы будут удалены" in message.text
    confirm = message.button("Подтвердить")
    await click(dashboard, event, ctx, confirm)
    assert library.actions == [("delete", "a" * 40)]
    assert not library.rows
    await click(dashboard, event, ctx, confirm)
    assert len(library.actions) == 1


@async_test
@pytest.mark.parametrize(
    "bad", ["user", "unauthorized", "chat", "message", "expired", "forged", "restart"]
)
@pytest.mark.parametrize(
    "label", ["Пауза", "Найти другую раздачу", "Удалить торрент и файлы", "Подтвердить"]
)
async def test_callbacks_reject_wrong_context_without_mutation(bot, monkeypatch, bad, label):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    await dashboard.open(event, ctx)
    await click(dashboard, event, ctx, message.button("1"))
    if label == "Подтвердить":
        await click(dashboard, event, ctx, message.button("Удалить торрент и файлы"))
    pause = message.button(label)
    if bad == "user":
        event.effective_user.id = 202  # Also allowlisted, but not the dashboard owner.
    elif bad == "unauthorized":
        event.effective_user.id = 999
    elif bad == "chat":
        event.effective_chat.id = 404
    elif bad == "message":
        message.message_id += 1
    elif bad == "expired":
        monkeypatch.setattr(dashboard, "now", lambda: 10**15)
    elif bad == "forged":
        pause += "junk"
    elif bad == "restart":
        ctx.user_data.clear()
    await click(dashboard, event, ctx, pause)
    assert not library.actions
    assert "Отправь название" not in message.text


@async_test
@pytest.mark.parametrize(
    "label", ["Пауза", "Найти другую раздачу", "Удалить торрент и файлы", "Подтвердить"]
)
async def test_missing_or_readded_torrent_requires_fresh_selection(bot, monkeypatch, label):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    await dashboard.open(event, ctx)
    await click(dashboard, event, ctx, message.button("1"))
    if label == "Подтвердить":
        await click(dashboard, event, ctx, message.button("Удалить торрент и файлы"))
    pause = message.button(label)
    library.rows["a" * 40]["added_on"] = 999
    await click(dashboard, event, ctx, pause)
    assert not library.actions
    assert "изменился" in message.text


@async_test
async def test_api_acknowledgement_is_not_confirmed_state(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    library.apply = False
    monkeypatch.setattr(asyncio, "sleep", lambda *_: _ready())
    await dashboard.open(event, ctx)
    await click(dashboard, event, ctx, message.button("1"))
    await click(dashboard, event, ctx, message.button("Пауза"))
    assert "не подтверждено" in message.text
    assert library.actions == [("pause", "a" * 40)]


async def _ready():
    pass


@pytest.mark.parametrize(
    "action,endpoint,extra",
    [
        ("pause", "stop", {}),
        ("resume", "start", {}),
        ("keep", "delete", {"deleteFiles": "false"}),
        ("delete", "delete", {"deleteFiles": "true"}),
    ],
)
def test_control_posts_exact_hash_and_file_policy(bot, monkeypatch, action, endpoint, extra):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(raise_for_status=lambda: None)

    monkeypatch.setattr(bot, "qbit_session", lambda: SimpleNamespace(post=post))
    bot.qbit_control_sync(action, "a" * 40)
    assert calls == [
        (
            "http://qbit.invalid/api/v2/torrents/" + endpoint,
            {"data": {"hashes": "a" * 40, **extra}, "timeout": 20},
        )
    ]


@pytest.mark.parametrize("t_hash", ["all", "", "a" * 40 + "|" + "b" * 40, "bad"])
def test_control_rejects_bulk_or_invalid_targets(bot, monkeypatch, t_hash):
    monkeypatch.setattr(bot, "qbit_session", lambda: pytest.fail("No request allowed"))
    with pytest.raises(ValueError):
        bot.qbit_control_sync("delete", t_hash)


@async_test
async def test_cancel_deletion_preserves_torrent_and_files(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    await dashboard.open(event, ctx)
    await click(dashboard, event, ctx, message.button("1"))
    await click(dashboard, event, ctx, message.button("Удалить торрент и файлы"))
    old_confirmation = message.button("Подтвердить")
    await click(dashboard, event, ctx, message.button("Отмена"))
    await click(dashboard, event, ctx, old_confirmation)
    assert not library.actions
    assert "a" * 40 in library.rows


@async_test
async def test_delete_timeout_is_not_replayed_and_no_raw_error_is_shown(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)

    def uncertain(action, t_hash):
        library.actions.append((action, t_hash))
        raise requests.Timeout("https://private.invalid?apikey=secret")

    monkeypatch.setattr(bot, "qbit_control_sync", uncertain)
    await dashboard.open(event, ctx)
    await click(dashboard, event, ctx, message.button("1"))
    await click(dashboard, event, ctx, message.button("Удалить торрент и файлы"))
    confirm = message.button("Подтвердить")
    await click(dashboard, event, ctx, confirm)
    assert "Не удалось подтвердить" in message.text
    assert "secret" not in message.text and "private.invalid" not in message.text
    await click(dashboard, event, ctx, confirm)
    assert len(library.actions) == 1


@async_test
async def test_empty_and_paginated_long_titles_stay_within_telegram_limits(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    library.rows = {
        f"{i:040x}": torrent(hash=f"{i:040x}", name="🧲" * 500 + str(i), added_on=i)
        for i in range(18)
    }
    await dashboard.open(event, ctx)
    assert "1/3" in message.text
    assert len(message.text.encode("utf-16-le")) // 2 <= 4096
    for row in message.markup.inline_keyboard:
        for button in row:
            assert len(button.callback_data.encode()) <= 64
    await click(dashboard, event, ctx, message.button("Далее"))
    assert "2/3" in message.text
    library.rows.clear()
    await click(dashboard, event, ctx, message.button("Обновить"))
    assert "Торрентов пока нет" in message.text
    assert "1/1" in message.text


@async_test
async def test_unauthorized_open_performs_no_reads(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    event.effective_user.id = 999
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: pytest.fail("Denied"))
    await dashboard.open(event, ctx)
    assert message.markup is None


@async_test
async def test_missing_torrent_does_not_send_delete(bot, monkeypatch):
    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    await dashboard.open(event, ctx)
    await click(dashboard, event, ctx, message.button("1"))
    await click(dashboard, event, ctx, message.button("Удалить торрент и файлы"))
    confirm = message.button("Подтвердить")
    library.rows.clear()
    await click(dashboard, event, ctx, confirm)
    assert not library.actions
    assert "исчез" in message.text


@async_test
async def test_commands_and_callback_wrappers_open_real_dashboard(bot, monkeypatch):
    _, library, message, ctx, event = setup(bot, monkeypatch)
    await bot.cmd_downloads(event, ctx)
    callback = message.button("1")

    async def answer(*args, **kwargs):
        pass

    event.callback_query = SimpleNamespace(data=callback, message=message, answer=answer)
    await bot.on_downloads(event, ctx)
    assert "Скачивается" in message.text
    assert message.button("Пауза")


@async_test
async def test_confirmed_delete_cancels_saved_watches_across_chats(bot, tmp_path, monkeypatch):
    from monitoring import WatchManager
    from watch_store import WatchStore

    dashboard, library, message, ctx, event = setup(bot, monkeypatch)
    store = WatchStore(tmp_path / "watches.sqlite3")
    store.subscribe(101, 303, "a" * 40, "Example")
    store.subscribe(202, 404, "a" * 40, "Example")
    store.pending(404, "a" * 40, "Old notice")
    manager = WatchManager(bot, None, store)
    ctx.application.bot_data["monitoring"] = manager
    # Hold existing tasks at an unrelated await; successful removal must cancel them.
    task = asyncio.create_task(asyncio.Event().wait())
    manager.tasks[(303, "a" * 40)] = task
    try:
        await dashboard.open(event, ctx)
        await click(dashboard, event, ctx, message.button("1"))
        await click(dashboard, event, ctx, message.button("Удалить торрент и файлы"))
        await click(dashboard, event, ctx, message.button("Подтвердить"))
        assert not library.rows
        assert task.cancelled()
        assert store.unfinished() == []
        assert "qBittorrent принял удаление файлов" in message.text
    finally:
        await manager.close()
