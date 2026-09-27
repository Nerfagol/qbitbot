"""Coverage comes from Jackett's query response, never missing result sources."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import requests

from tests.helpers import Message, context, update
from tests.test_search_ui import button, click


def payload(statuses=(2, 1), *, items=True):
    return {
        "Indexers": [
            {"Status": status, "Name": "DO_NOT_LEAK", "Error": "https://private/?apikey=SECRET"}
            for status in statuses
        ],
        "Results": [
            {
                "Title": "Fixture.2026.1080p",
                "MagnetUri": "magnet:?xt=urn:btih:" + "a" * 40,
                "Link": "https://private/file?apikey=SECRET",
                "Size": 1024,
                "Seeders": 30,
                "Tracker": "Fixture tracker",
            }
        ]
        if items
        else [],
    }


@pytest.mark.parametrize(
    "statuses,availability",
    [
        ([2, 2], "complete"),
        ([2, 1], "partial"),
        ([1, 1], "unavailable"),
        ([0, 0], "unknown"),
        ([2, 0], "partial"),
        ([], "unknown"),
        ([True], "unknown"),
    ],
)
def test_response_status_is_evidence_not_inferred_from_results(bot, statuses, availability):
    result = bot.jackett_response(payload(statuses, items=False))
    assert result.availability == availability
    assert result.responded == sum(type(value) is int and value == 2 for value in statuses)
    assert "SECRET" not in repr(vars(result))


def test_adapter_preserves_magnet_and_file_links_with_safe_fields(bot):
    data = payload()
    data["Results"].append(
        {"Title": "HTTP result", "Link": "https://fixture/file.torrent", "Tracker": "Second"}
    )
    result = bot.jackett_response(data)
    assert result[0]["url"].startswith("magnet:")
    assert result[1]["url"] == "https://fixture/file.torrent"
    assert result[0]["source"] == "Fixture tracker"
    assert result[1]["size"] is None and result[1]["seeders"] is None


@pytest.mark.parametrize(
    "data", [{}, {"Results": {}}, {"Results": None}, [], {"Results": ["not an item"]}]
)
def test_invalid_search_payload_is_not_an_empty_success(bot, data):
    with pytest.raises(ValueError):
        bot.jackett_response(data)


def test_search_uses_same_origin_json_endpoint_with_query_and_timeout(bot, monkeypatch):
    monkeypatch.setattr(
        bot,
        "JACKETT_TORZNAB_URL",
        "http://jackett.invalid/base/api/v2.0/indexers/all/results/torznab/api",
    )
    calls = []

    def get(url, **kw):
        calls.append((url, kw))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload())

    monkeypatch.setattr(bot.requests, "get", get)
    result = bot.jackett_search_sync("ubuntu", 50)
    assert result.availability == "partial"
    assert calls[0][0] == "http://jackett.invalid/base/api/v2.0/indexers/all/results"
    assert calls[0][1]["params"]["query"] == "ubuntu"
    assert calls[0][1]["timeout"] == (5, bot.JACKETT_SEARCH_TIMEOUT_SEC)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "xml", ['<error code="100" description="SECRET"/>', "<html><body>Login</body></html>", "<rss/>"]
)
def test_torznab_errors_and_non_rss_are_failures_even_with_http_200(bot, xml):
    with pytest.raises(ValueError, match="Search response unavailable"):
        bot.torznab_items(xml)


def run_search(bot, monkeypatch, statuses, *, items=True):
    monkeypatch.setattr(
        bot,
        "jackett_search_sync",
        lambda *args: bot.jackett_response(payload(statuses, items=items)),
    )
    add = AsyncMock(return_value={"ok": False})
    monkeypatch.setattr(bot, "qbit_add_and_confirm", add)
    request, ctx = Message("fixture query"), context()
    asyncio.run(bot.on_text(update(request), ctx))
    return request.replies[-1], ctx, add


@pytest.mark.parametrize(
    "statuses,phrase",
    [
        ([2, 2], "Ничего не нашёл"),
        ([2, 1], "Поиск неполный"),
        ([1, 1], "Поиск временно недоступен"),
        ([0, 0], "неизвестно"),
    ],
)
def test_empty_results_distinguish_coverage_from_failure(bot, monkeypatch, statuses, phrase):
    message, ctx, add = run_search(bot, monkeypatch, statuses, items=False)
    assert phrase in message.text
    assert "SECRET" not in message.text and "DO_NOT_LEAK" not in message.text
    assert button(message, "Повторить") and button(message, "Изменить запрос")
    assert not add.await_count


def test_partial_results_remain_selectable_and_notice_survives_filters_and_back(bot, monkeypatch):
    message, ctx, add = run_search(bot, monkeypatch, [2, 1])
    assert "Поиск неполный" in message.text and "1 из 2" in message.text
    assert "SECRET" not in message.text
    click(bot, message, ctx, "Фильтры")
    click(bot, message, ctx, "1080p")
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "К результатам")
    assert "Поиск неполный" in message.text
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "Скачать")
    assert add.await_count == 1


@pytest.mark.parametrize(
    "failure", [requests.Timeout("SECRET"), requests.ConnectionError("SECRET"), []]
)
def test_failed_partial_retry_preserves_old_list_and_add_buttons(bot, monkeypatch, failure):
    message, ctx, add = run_search(bot, monkeypatch, [2, 1])

    def search(*args):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(bot, "jackett_search_sync", search)
    click(bot, message, ctx, "Повторить поиск")
    assert ctx.user_data["search"]["message"] == message.message_id
    assert "Поиск неполный" in message.text
    failure_message = message.replies[-1]
    assert "SECRET" not in failure_message.text
    if isinstance(failure, requests.Timeout):
        assert "не успел" in failure_message.text
    assert button(failure_message, "Повторить")
    click(bot, message, ctx, "1")
    click(bot, message, ctx, "Скачать")
    assert add.await_count == 1


def test_successful_partial_retry_replaces_old_session_and_uses_same_query(bot, monkeypatch):
    message, ctx, _ = run_search(bot, monkeypatch, [2, 1])
    old = button(message, "1")
    calls = []
    monkeypatch.setattr(
        bot,
        "jackett_search_sync",
        lambda query, limit: calls.append(query) or bot.jackett_response(payload([2, 2])),
    )
    click(bot, message, ctx, "Повторить поиск")
    assert calls == ["fixture query"]
    assert ctx.user_data["search"]["message"] != message.message_id
    assert "Поиск неполный" not in message.replies[-1].text
    asyncio.run(bot.on_pick(update(message, old), ctx))
    assert "устарел" in message.sent[-1]["text"]
