"""External metadata may not escape the approved network/body boundaries."""

from types import SimpleNamespace
import socket

import pytest

from qbitbot import http_safety as http


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://user:password@example.org/",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/",
        "http://10.0.0.2/",
        "http://[::ffff:127.0.0.1]/",
        "http://example.org:0/",
        "http://example.org\\@localhost/",
        "http://example.org/\nsecret",
        "http://" + "a" * 254 + "/",
        "http://example.org/" + "x" * 8192,
    ],
)
def test_unsafe_url_is_rejected_without_network(url):
    with pytest.raises(http.UnsafeURL):
        http.validate_url(url)


def test_private_exception_is_only_the_configured_origin():
    trusted = "http://10.0.0.2:9117/api"
    assert http.validate_url("http://10.0.0.2:9117/torrent", trusted_url=trusted)
    for url in ["http://10.0.0.2:8080/", "https://10.0.0.2:9117/", "http://10.0.0.3:9117/"]:
        with pytest.raises(http.UnsafeURL):
            http.validate_url(url, trusted_url=trusted)


def records(*addresses):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 80)) for address in addresses]


class Socket:
    def __init__(self, *args):
        self.connected = None
        self.closed = False

    def settimeout(self, value):
        pass

    def setsockopt(self, *args):
        pass

    def connect(self, address):
        self.connected = address

    def close(self):
        self.closed = True


@pytest.mark.parametrize("addresses", [("10.0.0.2",), ("93.184.216.34", "127.0.0.1")])
def test_dns_private_and_mixed_answers_are_rejected_before_connect(monkeypatch, addresses):
    monkeypatch.setattr(http.socket, "getaddrinfo", lambda *a, **k: records(*addresses))
    monkeypatch.setattr(http.socket, "socket", lambda *a, **k: pytest.fail("must not connect"))
    with pytest.raises(http.UnsafeURL):
        http.open_socket("public.example", 80, 5, allow_private=False)


def test_connection_uses_validated_address_without_second_dns_lookup(monkeypatch):
    calls = []

    def resolve(*args, **kwargs):
        calls.append(args)
        return records("93.184.216.34") if len(calls) == 1 else records("127.0.0.1")

    sock = Socket()
    monkeypatch.setattr(http.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(http.socket, "socket", lambda *a, **k: sock)
    assert http.open_socket("public.example", 80, 5, allow_private=False) is sock
    assert sock.connected == ("93.184.216.34", 80)
    assert len(calls) == 1


def test_private_connection_is_allowed_for_explicitly_trusted_origin(monkeypatch):
    sock = Socket()
    monkeypatch.setattr(http.socket, "getaddrinfo", lambda *a, **k: records("10.0.0.2"))
    monkeypatch.setattr(http.socket, "socket", lambda *a, **k: sock)
    assert http.open_socket("jackett", 80, 5, allow_private=True) is sock


class Response:
    def __init__(self, status=200, headers=None, chunks=()):
        self.status_code = status
        self.headers = headers or {}
        self.chunks = chunks
        self.closed = False
        self.reads = 0

    def iter_content(self, **kwargs):
        self.reads += 1
        yield from self.chunks

    def close(self):
        self.closed = True


def rig(monkeypatch, responses):
    calls, clients = [], []

    class Client:
        trust_env = True

        def __init__(self):
            self.closed = False
            clients.append(self)

        def mount(self, *args):
            pass

        def request(self, method, url, **kwargs):
            assert not self.trust_env
            assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
            calls.append((method, url, kwargs))
            return responses.pop(0)

        def close(self):
            self.closed = True

    monkeypatch.setattr(http.requests, "Session", Client)
    return calls, clients


@pytest.mark.parametrize(
    "destination", ["http://127.0.0.1/", "http://169.254.169.254/", "file:///etc/passwd"]
)
def test_redirect_to_internal_or_non_http_destination_is_blocked(monkeypatch, destination):
    response = Response(302, {"location": destination})
    calls, clients = rig(monkeypatch, [response])
    with pytest.raises(http.UnsafeURL), http.open_response("GET", "https://example.org/file"):
        pytest.fail("unsafe response must not be yielded")
    assert len(calls) == 1
    assert response.closed and all(c.closed for c in clients)


def test_https_downgrade_is_rejected(monkeypatch):
    first = Response(302, {"location": "http://example.org/file"})
    rig(monkeypatch, [first])
    with pytest.raises(http.UnsafeURL), http.open_response("GET", "https://example.org/file"):
        pass
    assert first.closed


def test_service_redirect_must_remain_on_configured_origin(monkeypatch):
    first = Response(302, {"location": "https://elsewhere.example/caps"})
    rig(monkeypatch, [first])
    with (
        pytest.raises(http.UnsafeURL),
        http.open_response(
            "GET",
            "http://jackett:9117/api",
            trusted_url="http://jackett:9117/api",
            allow_external_redirects=False,
        ),
    ):
        pass
    assert first.closed


def test_public_redirect_is_followed_and_resources_always_close(monkeypatch):
    first = Response(302, {"location": "/next"})
    final = Response(chunks=[b"test"])
    calls, clients = rig(monkeypatch, [first, final])
    with http.open_response("GET", "https://example.org/start", params={"query": "test"}) as r:
        assert http.read_limited(r, 4) == b"test"
    assert calls[1][1] == "https://example.org/next"
    assert not calls[1][2].get("params")
    assert first.closed and final.closed and all(c.closed for c in clients)


@pytest.mark.parametrize("chunks", [[b"123", b"45"], [b"12345"]])
def test_decoded_body_limit_catches_chunked_or_compressed_payloads(chunks):
    with pytest.raises(http.ResponseTooLarge):
        http.read_limited(Response(chunks=chunks), 4)


def test_declared_excessive_length_is_rejected_before_reading():
    r = Response(headers={"content-length": "500"}, chunks=[b"x"])
    with pytest.raises(http.ResponseTooLarge):
        http.read_limited(r, 4)
    assert r.reads == 0


def test_response_closes_when_body_limit_is_exceeded(monkeypatch):
    r = Response(chunks=[b"oversized"])
    _, clients = rig(monkeypatch, [r])
    with (
        pytest.raises(http.ResponseTooLarge),
        http.open_response("GET", "https://example.org/") as r,
    ):
        http.read_limited(r, 4)
    assert r.closed and all(c.closed for c in clients)


def test_requests_does_not_buffer_redirect_body_before_policy_validation(monkeypatch):
    # Requests normally consumes a redirect body even with allow_redirects=False
    # when constructing Response.next. Use its real Session.send path here.
    response = http.requests.Response()
    response.status_code = 302
    response.headers["Location"] = "http://127.0.0.1/"
    response.url = "https://example.org/"
    response.raw = SimpleNamespace(
        read=lambda *a, **k: pytest.fail("redirect body must not be buffered"),
        close=lambda: None,
        release_conn=lambda: None,
    )
    adapter = SimpleNamespace(send=lambda *a, **k: response, close=lambda: None)
    monkeypatch.setattr(http.requests.Session, "get_adapter", lambda *a, **k: adapter)
    with pytest.raises(http.UnsafeURL), http.open_response("GET", response.url):
        pass


@pytest.mark.parametrize("address", ["64:ff9b::a9fe:a9fe", "64:ff9b::7f00:1", "64:ff9b:1::7f00:1"])
def test_nat64_does_not_turn_private_ipv4_into_an_allowed_destination(address):
    with pytest.raises(http.UnsafeURL):
        http.validate_url(f"http://[{address}]/")


@pytest.mark.parametrize("address", ["fec0::1", "ff02::1", "224.0.0.1"])
def test_site_local_and_multicast_literals_are_not_public_http_destinations(address):
    host = f"[{address}]" if ":" in address else address
    with pytest.raises(http.UnsafeURL):
        http.validate_url(f"http://{host}/")


@pytest.mark.parametrize("address", ["fec0::1", "ff02::1", "224.0.0.1"])
def test_site_local_and_multicast_dns_answers_are_rejected_before_connect(monkeypatch, address):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr = (address, 80, 0, 0) if family == socket.AF_INET6 else (address, 80)
    monkeypatch.setattr(
        http.socket, "getaddrinfo", lambda *a, **k: [(family, socket.SOCK_STREAM, 6, "", sockaddr)]
    )
    monkeypatch.setattr(http.socket, "socket", lambda *a, **k: pytest.fail("must not connect"))
    with pytest.raises(http.UnsafeURL):
        http.open_socket("public.example", 80, 5, allow_private=False)


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_real_requests_adapter_enforces_dns_boundary_before_socket_connect(monkeypatch, scheme):
    # Exercise Session -> HTTPAdapter -> custom urllib3 connection, not just the
    # resolver helper; dependency upgrades must not silently disconnect the guard.
    monkeypatch.setattr(http.socket, "getaddrinfo", lambda *a, **k: records("127.0.0.1"))
    monkeypatch.setattr(http.socket, "socket", lambda *a, **k: pytest.fail("must not connect"))
    with pytest.raises(http.UnsafeURL), http.open_response("GET", f"{scheme}://public.example/"):
        pass
