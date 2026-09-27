"""Import the real module without production environment, files, or networking."""

import importlib.util
import socket
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "tg_torrent_bot.py"


class NetworkForbidden(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise NetworkForbidden("Tests must replace external I/O; network is disabled")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)


@pytest.fixture
def bot(monkeypatch, tmp_path, no_network):
    # The module loads bot.env at import time. Never import from the project cwd.
    monkeypatch.chdir(tmp_path)
    import os

    for name in list(os.environ):
        monkeypatch.delenv(name)
    for name, value in {
        "BOT_TOKEN": "123456:TEST_ONLY_NOT_A_REAL_TOKEN",
        "ALLOWED_USERS": "101,202",
        "QBIT_URL": "http://qbit.invalid",
        "QBIT_USER": "test-user",
        "QBIT_PASS": "test-password",
        "JACKETT_TORZNAB_URL": "http://jackett.invalid/api",
        "JACKETT_API_KEY": "test-key",
        "PTB_USE_AIOHTTP": "0",
    }.items():
        monkeypatch.setenv(name, value)
    # External sync boundaries are fakes; run them inline so the suite does not
    # depend on cross-thread event-loop wakeups in restricted sandboxes.
    import asyncio

    async def inline_thread(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", inline_thread)
    spec = importlib.util.spec_from_file_location("bot_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
