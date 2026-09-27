import subprocess
from types import SimpleNamespace

import pytest

from integration.run import cleanup_resources, run_ephemeral


def test_cleanup_continues_after_one_docker_timeout():
    attempted = []

    def docker(*args, **kwargs):
        attempted.append(args)
        if args == ("rm", "-f", "stuck"):
            raise subprocess.TimeoutExpired("docker", 120)
        return SimpleNamespace(returncode=0)

    errors = cleanup_resources(docker, ["other", "stuck"], ["data"], ["image"], "network")
    assert len(errors) == 1 and "stuck" in errors[0]
    assert ("rm", "-f", "other") in attempted
    assert ("volume", "rm", "data") in attempted
    assert ("network", "rm", "network") in attempted
    assert ("image", "rm", "image") in attempted


def test_helper_is_tracked_if_attached_cli_times_out():
    tracked = []

    def docker(*args, **kwargs):
        if args[0] in ("run", "start"):
            raise subprocess.TimeoutExpired("docker", 120)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    with pytest.raises(subprocess.TimeoutExpired):
        run_ephemeral(docker, tracked, "owned-helper", "--network", "none", "image")
    assert tracked == ["owned-helper"]
