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
        "if '--url-query' in args:\n"
        "    print('synthetic-key secret-response', file=sys.stderr)\n"
        "    out = args[args.index('--output') + 1]\n"
        "    Path(out).write_text(os.environ.get('RESPONSE', '{\"Indexers\":[],\"Results\":[]}'))\n"
        "    sys.exit(int(os.environ.get('SEARCH_EXIT', '0')))\n"
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


def test_api_key_search_runs_once_without_dashboard_login(startup):
    run, requests, state = startup
    assert run().returncode == 0
    first = requests()
    assert len(first) == 1
    assert first[0][-1] == "http://127.0.0.1:9117/api/v2.0/indexers/all/results"
    assert "query=" in first[0]
    assert "--request" not in first[0]
    assert run().returncode == 0
    assert requests() == first
    assert (state / "complete").is_file()
    assert not any("synthetic-key" in arg for r in first for arg in r)
    assert not list(state.glob("private.*"))


@pytest.mark.parametrize("enabled", ["0", "false", ""])
def test_disabled_warmup_makes_no_api_requests(startup, enabled):
    run, requests, _ = startup
    assert run(JACKETT_WARMUP_ON_START=enabled).returncode == 0
    assert requests() == []


def test_empty_configuration_reports_zero_sources(startup):
    run, requests, _ = startup
    result = run()
    assert result.returncode == 0
    assert "0 sources reported" in result.stdout
    assert len(requests()) == 1


def test_failed_search_is_not_retried_or_leaked_and_health_can_continue(startup):
    run, requests, state = startup
    result = run(SEARCH_EXIT="22")
    assert result.returncode == 0
    assert "synthetic-key" not in result.stdout + result.stderr
    assert "secret-response" not in result.stdout + result.stderr
    assert len(requests()) == 1
    assert (state / "complete").is_file()
    assert run("health").returncode == 0


def test_health_rejects_previous_boot_completion_without_http(startup):
    run, requests, state = startup
    state.mkdir()
    (state / "complete").write_text("previous-container-start\n")
    assert run("health").returncode != 0
    assert requests() == []


def test_login_redirect_or_invalid_response_is_not_followed_or_retried(startup):
    run, requests, _ = startup
    result = run(RESPONSE="<html>login</html>")
    assert result.returncode == 0
    assert "failed" in result.stdout
    assert len(requests()) == 1
    assert "--location" not in requests()[0]
    assert "-L" not in requests()[0]


def test_search_has_bounded_timeout_and_no_retry_option(startup):
    run, requests, _ = startup
    assert run().returncode == 0
    request = requests()[0]
    assert 0 < int(request[request.index("--max-time") + 1]) <= 120
    assert "--retry" not in request
