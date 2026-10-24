"""The runtime must use bounded reads at each external metadata boundary."""

from contextlib import contextmanager
import json

import pytest

from tests.test_search_availability import payload


class Response:
    def __init__(self, body):
        self.body = body
        self.headers = {}
        self.closed = False
        self.url = "http://jackett.invalid/file.torrent"

    def iter_content(self, **kwargs):
        yield self.body

    def raise_for_status(self):
        pass

    def close(self):
        self.closed = True


def transport(monkeypatch, module, body):
    response = Response(body)
    calls = []

    @contextmanager
    def open_response(method, url, **kwargs):
        calls.append((method, url, kwargs))
        try:
            yield response
        finally:
            response.close()

    monkeypatch.setattr(module, "open_response", open_response)
    return response, calls


@pytest.mark.parametrize("json_api", [True, False])
def test_search_body_is_bounded_and_closed(bot, monkeypatch, json_api):
    url = (
        "http://jackett.invalid/api/v2.0/indexers/all/results/torznab/api"
        if json_api
        else "http://jackett.invalid/custom"
    )
    monkeypatch.setattr(bot, "JACKETT_TORZNAB_URL", url)
    monkeypatch.setattr(bot, "MAX_SEARCH_BYTES", 4)
    response, calls = transport(monkeypatch, bot, b"oversized")
    with pytest.raises(ValueError):
        bot.jackett_search_sync("query")
    assert response.closed
    assert calls[0][2]["trusted_url"] == url
    assert calls[0][2]["allow_external_redirects"] is False


def test_json_search_uses_bounded_bytes_instead_of_unbounded_json_method(bot, monkeypatch):
    url = "http://jackett.invalid/api/v2.0/indexers/all/results/torznab/api"
    monkeypatch.setattr(bot, "JACKETT_TORZNAB_URL", url)
    response, _ = transport(monkeypatch, bot, json.dumps(payload()).encode())
    assert bot.jackett_search_sync("query").availability == "partial"
    assert response.closed


def test_capability_body_is_bounded(monkeypatch):
    from qbitbot import health

    monkeypatch.setattr(health, "MAX_CAPABILITIES_BYTES", 4)
    response, calls = transport(monkeypatch, health, b"oversized")
    with pytest.raises(ValueError):
        health.check_jackett("http://jackett.invalid/api", "test-key")
    assert response.closed
    assert calls[0][2]["allow_external_redirects"] is False


def test_magnet_resolution_does_not_follow_https_downgrade(bot, monkeypatch):
    response, calls = transport(monkeypatch, bot, b"")
    response.status_code = 302
    response.headers = {"location": "http://example.org/file"}
    with pytest.raises(ValueError):
        bot.resolve_http_redirect_to_magnet_sync("https://example.org/file")
    assert len(calls) == 1 and response.closed
