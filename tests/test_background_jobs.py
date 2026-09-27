import asyncio
from unittest.mock import AsyncMock

from tests.helpers import Message, context, update
from tests.test_persistence import async_test
from tests.test_search_ui import results, button


@async_test
async def test_search_does_not_hold_downloads_or_accept_unbounded_jobs(bot, monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()

    async def search(event, ctx):
        started.set()
        await release.wait()

    monkeypatch.setattr(bot, "on_text", search)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [])
    ctx = context()
    event = update(Message("Film"))
    await bot.dispatch_search(event, ctx)
    await started.wait()
    await bot.cmd_downloads(update(Message()), ctx)
    assert "downloads" in ctx.user_data
    other = Message("Another title")
    await bot.dispatch_search(update(other), ctx)
    assert "дождись" in other.sent[-1]["text"].lower()
    jobs = ctx.application.bot_data["search_jobs"]
    assert len(jobs.tasks) == 1
    release.set()
    await asyncio.gather(*jobs.tasks.values())
    await bot.monitoring_stop(ctx.application)


@async_test
async def test_pending_add_allows_downloads_but_duplicate_click_cannot_add_twice(bot, monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def add(event, ctx, item):
        calls.append(item)
        started.set()
        await release.wait()
        return {"status": "uncertain"}

    monkeypatch.setattr(bot, "jackett_search_sync", lambda *args: results(1))
    monkeypatch.setattr(bot, "add_selected", add)
    monkeypatch.setattr(bot, "qbit_torrents_info_sync", lambda **kw: [])
    ctx = context()
    msg = Message("Film")
    await bot.on_text(update(msg), ctx)
    card = msg.replies[-1]
    await bot.on_pick(update(card, button(card, "1")), ctx)
    token = button(card, "Скачать")
    await bot.dispatch_pick(update(card, token), ctx)
    await started.wait()
    await bot.dispatch_pick(update(card, token), ctx)
    await bot.cmd_downloads(update(Message()), ctx)
    assert "downloads" in ctx.user_data and len(calls) == 1
    release.set()
    await asyncio.gather(*ctx.application.bot_data["search_jobs"].tasks.values())
    await bot.dispatch_pick(update(card, token), ctx)
    assert len(calls) == 1


@async_test
async def test_job_shutdown_cancels_owned_work_and_rejects_new_work(bot, monkeypatch):
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def search(event, ctx):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(bot, "on_text", search)
    ctx = context()
    await bot.dispatch_search(update(Message("Film")), ctx)
    await started.wait()
    await bot.monitoring_stop(ctx.application)
    assert cancelled.is_set()
    assert not ctx.application.bot_data["search_jobs"].tasks
    message = Message("Next")
    await bot.dispatch_search(update(message), ctx)
    assert message.sent


@async_test
async def test_job_errors_are_redacted_and_release_user_slot(bot, monkeypatch, capsys):
    async def search(event, ctx):
        raise RuntimeError("private://secret")

    monkeypatch.setattr(bot, "on_text", search)
    ctx = context()
    message = Message("Film")
    await bot.dispatch_search(update(message), ctx)
    await asyncio.gather(*ctx.application.bot_data["search_jobs"].tasks.values())
    assert message.sent and "private" not in str(message.sent)
    assert "private" not in capsys.readouterr().out
    assert not ctx.application.bot_data["search_jobs"].tasks


@async_test
async def test_unauthorized_user_cannot_schedule_search(bot, monkeypatch):
    work = AsyncMock()
    monkeypatch.setattr(bot, "on_text", work)
    ctx = context()
    await bot.dispatch_search(update(Message("Film"), user_id=999), ctx)
    assert not ctx.application.bot_data
    work.assert_not_awaited()


@async_test
async def test_another_allowed_user_can_search_while_first_is_waiting(bot, monkeypatch):
    release = asyncio.Event()
    started = []

    async def search(event, ctx):
        started.append(event.effective_user.id)
        await release.wait()

    monkeypatch.setattr(bot, "on_text", search)
    ctx = context()
    other = context()
    other.application = ctx.application
    await bot.dispatch_search(update(Message("A")), ctx)
    await bot.dispatch_search(update(Message("B"), user_id=202), other)
    await asyncio.sleep(0)
    assert sorted(started) == [101, 202]
    release.set()
    await asyncio.gather(*ctx.application.bot_data["search_jobs"].tasks.values())


def test_registered_text_handler_returns_before_search_finishes(bot, monkeypatch):
    from telegram.ext import Application, MessageHandler

    captured = []
    monkeypatch.setattr(Application, "run_polling", lambda app: captured.append(app))
    bot.main()
    handler = next(
        h for group in captured[0].handlers.values() for h in group if isinstance(h, MessageHandler)
    )

    async def scenario():
        release = asyncio.Event()

        async def search(event, ctx):
            await release.wait()

        monkeypatch.setattr(bot, "on_text", search)
        ctx = context()
        try:
            await asyncio.wait_for(handler.callback(update(Message("Film")), ctx), 0.5)
            assert ctx.application.bot_data["search_jobs"].tasks
        finally:
            release.set()
            await bot.monitoring_stop(ctx.application)

    asyncio.run(scenario())
