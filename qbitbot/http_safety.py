"""Bounded HTTP reads with origin exceptions and DNS-pinned connections.

Only the explicitly configured service origin may use private addresses. Proxies
and netrc are disabled; HTTPS keeps urllib3's normal SNI/certificate validation.
"""

from contextlib import contextmanager
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import idna
import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError

MAX_URL_BYTES = 8192
MAX_SEARCH_BYTES = 4 * 1024 * 1024
MAX_CAPABILITIES_BYTES = 256 * 1024
REDIRECTS = {301, 302, 303, 307, 308}


class UnsafeURL(ValueError):
    """A request would cross the permitted network boundary."""


class ResponseTooLarge(ValueError):
    """The decoded response exceeded the application limit."""


def _origin(url):
    try:
        if not isinstance(url, str) or len(url.encode("utf-8")) > MAX_URL_BYTES:
            raise ValueError
        if any(ord(c) <= 32 or ord(c) == 127 for c in url) or "\\" in url:
            raise ValueError
        parts = urlsplit(url)
        if (
            parts.scheme not in ("http", "https")
            or parts.username is not None
            or parts.password is not None
        ):
            raise ValueError
        host = parts.hostname
        if not host or len(host) > 253 or "%" in host:
            raise ValueError
        try:
            host = str(ipaddress.ip_address(host))
        except ValueError:
            host = idna.encode(host, uts46=True).decode("ascii").lower()
        port = parts.port if parts.port is not None else (443 if parts.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            raise ValueError
        return parts.scheme, host, port
    except (ValueError, TypeError, UnicodeError, idna.IDNAError):
        raise UnsafeURL("HTTP destination is not permitted") from None


def _public(address):
    ip = ipaddress.ip_address(address)
    if not ip.is_global or ip.is_multicast:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.is_site_local:
            return False
        if ip in ipaddress.IPv6Network("64:ff9b:1::/48"):
            return False
        if ip in ipaddress.IPv6Network("64:ff9b::/96"):
            return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF).is_global
        if ip.ipv4_mapped is not None and not ip.ipv4_mapped.is_global:
            return False
        if ip.sixtofour is not None and not ip.sixtofour.is_global:
            return False
        if ip.teredo is not None and not all(part.is_global for part in ip.teredo):
            return False
    return True


def validate_url(url, *, trusted_url=None):
    origin = _origin(url)
    trusted = _origin(trusted_url) if trusted_url is not None else None
    try:
        address = ipaddress.ip_address(origin[1])
    except ValueError:
        return origin  # DNS is checked at the actual connection, never separately.
    if origin != trusted and not _public(str(address)):
        raise UnsafeURL("HTTP destination is not permitted")
    return origin


def redirect_destination(current, location, *, trusted_url=None):
    origin = validate_url(current, trusted_url=trusted_url)
    destination = urljoin(current, location)
    next_origin = validate_url(destination, trusted_url=trusted_url)
    if origin[0] == "https" and next_origin[0] != "https":
        raise UnsafeURL("HTTP redirect is not permitted")
    return destination


def open_socket(host, port, timeout, *, allow_private, source_address=None, socket_options=()):
    """Resolve once, validate every answer, and connect to that exact sockaddr."""
    addresses = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    if not addresses or any(not _public(row[4][0]) for row in addresses) and not allow_private:
        raise UnsafeURL("HTTP destination is not permitted")
    for family, kind, protocol, _, address in addresses:
        sock = socket.socket(family, kind, protocol)
        try:
            sock.settimeout(timeout)
            for option in socket_options or ():
                sock.setsockopt(*option)
            if source_address:
                sock.bind(source_address)
            sock.connect(address)
            return sock
        except OSError:
            sock.close()
    raise OSError("HTTP connection unavailable")


def _adapter(allow_private):
    class PinnedConnection:
        def _new_conn(self):
            try:
                return open_socket(
                    self.host,
                    self.port,
                    self.timeout,
                    allow_private=allow_private,
                    source_address=self.source_address,
                    socket_options=self.socket_options,
                )
            except OSError:
                raise NewConnectionError(self, "HTTP connection unavailable") from None

    class HTTP(PinnedConnection, HTTPConnection):
        pass

    class HTTPS(PinnedConnection, HTTPSConnection):
        pass

    class HTTPPool(HTTPConnectionPool):
        ConnectionCls = HTTP

    class HTTPSPool(HTTPSConnectionPool):
        ConnectionCls = HTTPS

    adapter = HTTPAdapter(max_retries=0)
    # This mapping is per PoolManager; never change urllib3's global pool classes.
    adapter.poolmanager.pool_classes_by_scheme = {"http": HTTPPool, "https": HTTPSPool}
    return adapter


@contextmanager
def open_response(
    method,
    url,
    *,
    trusted_url=None,
    timeout=25,
    headers=None,
    params=None,
    follow_redirects=True,
    allow_external_redirects=True,
    max_redirects=10,
):
    """Own the session/response lifetime and guard each redirect independently."""
    initial_origin = validate_url(url, trusted_url=trusted_url)
    trusted_origin = _origin(trusted_url) if trusted_url is not None else None
    current = url
    for hop in range(max_redirects + 1):
        origin = validate_url(current, trusted_url=trusted_url)
        if not allow_external_redirects and origin != initial_origin:
            raise UnsafeURL("HTTP redirect is not permitted")
        client = requests.Session()
        client.trust_env = False
        # Requests otherwise eagerly buffers redirect bodies while constructing
        # Response.next even with allow_redirects=False. We own all redirects.
        client.resolve_redirects = lambda *args, **kwargs: iter(())
        adapter = _adapter(origin == trusted_origin)
        client.mount("http://", adapter)
        client.mount("https://", adapter)
        response = None
        try:
            response = client.request(
                method,
                current,
                params=params if hop == 0 else None,
                headers=headers,
                timeout=timeout,
                stream=True,
                allow_redirects=False,
            )
            location = response.headers.get("location")
            if follow_redirects and response.status_code in REDIRECTS and location:
                if hop == max_redirects:
                    raise UnsafeURL("Too many HTTP redirects")
                current = redirect_destination(current, location, trusted_url=trusted_url)
                continue
            yield response
            return
        finally:
            if response is not None:
                response.close()
            client.close()


def read_limited(response, max_bytes):
    """Count decoded bytes, including streamed/chunked/compressed responses."""
    if max_bytes <= 0:
        raise ValueError("A positive response limit is required")
    length = response.headers.get("content-length", "")
    if str(length).isdigit() and int(length) > max_bytes:
        raise ResponseTooLarge("HTTP response exceeds the permitted size")
    chunks, total = [], 0
    for chunk in response.iter_content(chunk_size=min(65536, max_bytes + 1)):
        total += len(chunk)
        if total > max_bytes:
            raise ResponseTooLarge("HTTP response exceeds the permitted size")
        chunks.append(chunk)
    return b"".join(chunks)
