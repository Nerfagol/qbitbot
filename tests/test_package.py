"""Public module entry points must work without importing the bot accidentally."""

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_python(tmp_path, *args):
    # No personal configuration, token, or inherited Python path reaches the child.
    return subprocess.run(
        [sys.executable, *args],
        cwd=tmp_path,
        env={"PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_package_import_is_inert_and_catalogs_are_cwd_independent(tmp_path):
    (tmp_path / "bot.env").write_text("ALLOWED_USERS=invalid\n")
    result = run_python(
        tmp_path,
        "-c",
        "import sys, qbitbot; from qbitbot.i18n import tr; "
        "assert 'qbitbot.app' not in sys.modules; "
        "assert tr('search.query', 'en', query='x') == 'Search: x'; "
        "assert tr('search.query', 'ru', query='x') == 'Поиск: x'",
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("command", ["setup_check", "backup_state"])
def test_maintenance_help_needs_no_bot_configuration(tmp_path, command):
    result = run_python(tmp_path, "-m", "qbitbot.cli." + command, "--help")
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


def test_bot_entrypoint_rejects_missing_configuration_before_polling(tmp_path):
    result = run_python(tmp_path, "-m", "qbitbot")
    assert result.returncode != 0
    assert "ALLOWED_USERS:" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
