"""Disposable service credentials must not be persisted in fixture source files."""

import json

from integration.public_stack import fresh


def test_generated_service_credentials_stay_out_of_fixture_files(tmp_path):
    password = "fixture-generated-qbit-password"
    api_key = "fixture-generated-jackett-key"
    project = "qbitbot-public-test-0123456789ab"
    network = project + "_default"
    calls = []
    (tmp_path / "integration").mkdir()
    for name in ("public_probe.py", "fixtures.py"):
        (tmp_path / "integration" / name).write_text("# synthetic probe\n")

    def docker(*args, **kwargs):
        calls.append((args, kwargs))
        if "config" in args:
            only = project + "-only" in args
            return json.dumps(
                {
                    "services": {
                        name: {}
                        for name in (("bot",) if only else ("bot", "qbittorrent", "jackett"))
                    },
                    "networks": {
                        "default": {
                            "name": network,
                            **({"external": True} if only else {"internal": True}),
                        }
                    },
                    "volumes": {},
                }
            ).encode()
        if "ps" in args:
            return ("owned-" + args[-1]).encode()
        if args[:2] == ("logs", "owned-qbittorrent"):
            return ("temporary password is provided for this session: " + password).encode()
        if args[:3] == ("exec", "owned-jackett", "cat"):
            return json.dumps({"APIKey": api_key}).encode()
        if args[:4] == ("exec", "owned-bot", "python", "/tmp/public_probe.py"):
            return b'{"checks":[]}'
        return b""

    fresh(docker, tmp_path, project, project + ":candidate", [])
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert password.encode() not in path.read_bytes(), "password persisted in fixture file"
            assert api_key.encode() not in path.read_bytes(), "API key persisted in fixture file"
    assert (tmp_path / "bot.env").read_bytes() == b""
    assert (tmp_path / "bot.env").stat().st_mode & 0o777 == 0o600
    authenticated = [
        kwargs["environment"]
        for args, kwargs in calls
        if args[0] == "compose" and kwargs.get("environment")
    ]
    assert authenticated
    assert all(env["QBITBOT_TEST_QBIT_PASS"] == password for env in authenticated)
    assert all(env["QBITBOT_TEST_JACKETT_API_KEY"] == api_key for env in authenticated)
    # The Docker argv and fixture transfer stdin must never carry secret values.
    assert password not in repr([args for args, _ in calls])
    assert api_key not in repr([args for args, _ in calls])
