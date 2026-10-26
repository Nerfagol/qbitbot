"""Owned browser-test failures stay diagnosable, private and cleaned up."""

from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from integration import flaresolverr


@pytest.mark.parametrize("logs_timeout", [False, True])
def test_exited_solver_reports_safe_diagnostics_and_cleans_every_fixture(
    monkeypatch, capsys, logs_timeout
):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == "openssl":
            for option in ("-out", "-keyout"):
                Path(command[command.index(option) + 1]).write_text("synthetic fixture certificate")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        args = command[1:]
        if args[0] == "exec":
            if "8080" in args[-1]:
                return SimpleNamespace(returncode=0, stdout="200", stderr="")
            if "8191" in args[-1]:
                return SimpleNamespace(returncode=1, stdout="", stderr="refused")
        if args[0] == "inspect":
            text = (
                "false"
                if ".Running" in args[2]
                else '{"Status":"exited","ExitCode":1,"OOMKilled":false}'
            )
            return SimpleNamespace(returncode=0, stdout=text, stderr="")
        if args[0] == "logs":
            if logs_timeout:
                raise subprocess.TimeoutExpired(command, 15)
            return SimpleNamespace(
                returncode=0,
                stdout="browser failed at http://private.invalid/path?apikey=synthetic",
                stderr="",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(sys, "argv", ["solver-smoke", "--image", "synthetic-image"])
    monkeypatch.setattr(flaresolverr.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="exited during startup"):
        flaresolverr.main()
    output = capsys.readouterr().out
    assert "Fixture state:" in output
    assert "private.invalid" not in output and "apikey=" not in output
    assert ("TimeoutExpired" if logs_timeout else "[redacted URL]") in output
    removals = [cmd for cmd in calls if cmd[1:4] == ["rm", "-f", "-v"]]
    assert len(removals) == 2 and len({cmd[-1] for cmd in removals}) == 2
    assert any(cmd[1:3] == ["network", "rm"] for cmd in calls)
