"""Check configured service access without starting a Telegram poller."""

import argparse
import os
import re
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from settings import Settings, SettingsError, load_env, read_settings


@dataclass(frozen=True)
class CheckResult:
    service: str
    ok: bool
    message_key: str


class AuthenticationError(Exception):
    pass


def _qbit(settings):
    client = requests.Session()
    try:
        response = client.post(
            settings.qbit_url + "/api/v2/auth/login",
            data={"username": settings.qbit_user, "password": settings.qbit_pass},
            timeout=(5, 10),
        )
        response.raise_for_status()
        if response.text.strip() != "Ok.":
            raise AuthenticationError
        response = client.get(settings.qbit_url + "/api/v2/app/version", timeout=(5, 10))
        response.raise_for_status()
        if not re.fullmatch(r"v?\d+\.\d+(?:\.[\w.-]+)?", response.text.strip()):
            raise ValueError
    finally:
        client.close()


def _jackett(settings):
    parts = urlsplit(settings.jackett_url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in ("apikey", "q", "t")]
    response = requests.get(
        urlunsplit(parts._replace(query=urlencode(query), fragment="")),
        params={"apikey": settings.jackett_key, "t": "caps"},
        timeout=(5, 10),
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    if root.tag == "error" and root.get("code") in ("100", "101", "102"):
        raise AuthenticationError
    if root.tag != "caps" or root.find("searching") is None:
        raise ValueError


def _remote_check(service, function):
    for attempt in range(3):
        try:
            function()
            return CheckResult(service, True, "setup.ok")
        except AuthenticationError:
            return CheckResult(service, False, "setup.auth")
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code in (401, 403):
                return CheckResult(service, False, "setup.auth")
            key = "setup.unavailable"
        except requests.Timeout:
            key = "setup.timeout"
        except requests.RequestException:
            key = "setup.unavailable"
        except (ValueError, ET.ParseError):
            return CheckResult(service, False, "setup.response")
        if attempt < 2:
            time.sleep(2)
    return CheckResult(service, False, key)


def run_checks(settings: Settings) -> list[CheckResult]:
    results = [
        _remote_check("qBittorrent", lambda: _qbit(settings)),
        _remote_check("Jackett", lambda: _jackett(settings)),
    ]
    try:
        directory = settings.watch_db_path.parent
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=directory) as probe:
            probe.write(b"state permission probe")
            probe.flush()
        results.append(CheckResult("state", True, "setup.ok"))
    except OSError:
        results.append(CheckResult("state", False, "setup.storage"))
    return results


MESSAGES = {
    "setup.ok": "Ready.",
    "setup.auth": "Authentication failed. Check the configured credentials.",
    "setup.timeout": "Timed out after bounded retries. Check service availability.",
    "setup.unavailable": "Service unavailable. Check its address and network access.",
    "setup.response": "Unexpected service response. Check the API address.",
    "setup.storage": "Cannot write state. Check the state directory permissions.",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        load_env()
        settings = read_settings(os.environ)
    except SettingsError as error:
        print(str(error))
        return 1
    results = run_checks(settings)
    for result in results:
        print(f"{result.service}: {MESSAGES[result.message_key]}")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
