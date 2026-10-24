"""Probe installation must work with Docker's read-only root filesystem policy."""

import subprocess
import sys


def test_fixture_transfer_writes_exact_bytes_through_exec_stdin(tmp_path):
    from integration.public_stack import install_fixture_source

    source = tmp_path / "public_probe.py"
    source.write_bytes(b"# synthetic fixture: '\"$()\\n\nprint('unchanged')\n")
    destination = tmp_path / "container-tmp-probe.py"
    calls = []

    def docker(*args, stdin=None):
        calls.append(args)
        assert args[:5] == ("exec", "-i", "owned-bot", "python", "-c")
        assert args[-1] == "/tmp/public_probe.py"
        # Execute the exact transfer program against a disposable local target.
        result = subprocess.run(
            [sys.executable, "-c", args[5], str(destination)], input=stdin, capture_output=True
        )
        assert result.returncode == 0, result.stderr
        return result.stdout

    install_fixture_source(docker, "owned-bot", source)
    assert destination.read_bytes() == source.read_bytes()
    assert len(calls) == 1 and not any("cp" in call for call in calls)
