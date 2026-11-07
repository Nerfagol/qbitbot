"""Exercise the startup helper without real services, credentials or network."""

import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/docker/jackett/startup.sh"


@pytest.fixture
def startup(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "ServerConfig.json").write_text(json.dumps({"APIKey": "synthetic-key"}))
    commands = tmp_path / "bin"
    commands.mkdir()
    calls = tmp_path / "calls"
    # The external HTTP boundary alone is replaced; jq, shell control flow,
    # private credential files and completion markers execute normally.
    curl = commands / "curl"
    curl.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['CALLS'], 'a') as f: f.write(json.dumps(args) + '\\n')\n"
        "if '--request' in args:\n"
        "    print('synthetic-key secret-response', file=sys.stderr)\n"
        "    print('204')\n"
        "    sys.exit(int(os.environ.get('POST_EXIT', '0')))\n"
        "if '--url-query' in args:\n"
        "    out = args[args.index('--output') + 1]\n"
        "    Path(out).write_text(os.environ.get('INDEXERS', '[]'))\n"
    )
    curl.chmod(0o755)
    env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"])
    env.update(CALLS=str(calls), JACKETT_WARMUP_ON_START="1")
    state = tmp_path / "run"

    def run(mode="warmup", **changes):
        assert SCRIPT.is_file(), "restart-only startup helper has not been implemented"
        return subprocess.run(
            ["sh", str(SCRIPT), mode, str(config), str(state)],
            env=env | changes,
            capture_output=True,
            text=True,
            timeout=5,
        )

    def requests():
        return (
            [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
        )

    return run, requests, state


def test_each_configured_tracker_once_and_no_second_run(startup):
    run, requests, state = startup
    indexers = json.dumps([{"id": "fixture-a"}, {"id": "fixture-b"}])
    assert run(INDEXERS=indexers).returncode == 0
    first = requests()
    assert len([r for r in first if "--request" in r]) == 2
    assert run(INDEXERS=indexers).returncode == 0
    assert requests() == first
    assert (state / "complete").is_file()
    assert not any("synthetic-key" in arg for r in first for arg in r)


@pytest.mark.parametrize("enabled", ["0", "false", ""])
def test_disabled_warmup_makes_no_api_requests(startup, enabled):
    run, requests, _ = startup
    assert run(JACKETT_WARMUP_ON_START=enabled).returncode == 0
    assert requests() == []


def test_empty_configuration_does_not_test_trackers(startup):
    run, requests, _ = startup
    assert run().returncode == 0
    assert not any("--request" in r for r in requests())


def test_failed_test_is_not_retried_or_leaked_and_health_can_continue(startup):
    run, requests, state = startup
    result = run(INDEXERS='[{"id":"fixture-a"}]', POST_EXIT="22")
    assert result.returncode == 0
    assert "synthetic-key" not in result.stdout + result.stderr
    assert "secret-response" not in result.stdout + result.stderr
    assert len([r for r in requests() if "--request" in r]) == 1
    assert (state / "complete").is_file()
    assert run("health").returncode == 0


def test_health_rejects_previous_boot_completion_without_http(startup):
    run, requests, state = startup
    state.mkdir()
    (state / "complete").write_text("previous-container-start\n")
    assert run("health").returncode != 0
    assert requests() == []


def test_malformed_indexer_ids_fail_closed_without_tracker_calls(startup):
    run, requests, _ = startup
    assert run(INDEXERS='[{"id":"../../untrusted"}]').returncode == 0
    assert not any("--request" in r for r in requests())


def test_total_budget_stops_remaining_trackers_without_background_work(startup, tmp_path):
    run, requests, state = startup
    clock = tmp_path / "bin/date"
    clock.write_text(
        "#!/bin/sh\n"
        'file="$CALLS-clock"\n'
        'value=$(cat "$file" 2>/dev/null || echo 0)\n'
        'echo "$((value + 60))" > "$file"\n'
        'echo "$value"\n'
    )
    clock.chmod(0o755)
    result = run(INDEXERS='[{"id":"fixture-a"},{"id":"fixture-b"}]')
    assert result.returncode == 0
    posts = [r for r in requests() if "--request" in r]
    assert len(posts) == 1
    assert int(posts[0][posts[0].index("--max-time") + 1]) <= 45
    assert not list(state.glob("private.*"))
