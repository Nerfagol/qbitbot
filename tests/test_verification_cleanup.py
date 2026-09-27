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
        return SimpleNamespace(returncode=0, stdout=b'{"qbitbot.verification":"owned"}', stderr=b"")

    errors = cleanup_resources(
        docker, ["other", "stuck"], ["data"], ["image"], "network", owner="owned"
    )
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


@pytest.mark.parametrize("kind", ["container", "volume", "image", "network"])
def test_creation_timeout_keeps_owned_resource_in_cleanup_registry(kind):
    import json
    from integration.run import create_tracked

    tracked, removed = [], []
    owner = "qbitbot-verify-0123456789"
    name = owner + "-" + kind

    def docker(*args, **kw):
        if args[0] == "create-fixture":
            raise subprocess.TimeoutExpired("docker", 1)
        if args[0] == "inspect":
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"qbitbot.verification": owner}).encode(),
                stderr=b"",
            )
        removed.append(args)
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    with pytest.raises(subprocess.TimeoutExpired):
        create_tracked(docker, tracked, name, "create-fixture")
    assert tracked == [name]
    groups = {key: tracked if key == kind else [] for key in ("container", "volume", "image")}
    errors = cleanup_resources(
        docker,
        groups["container"],
        groups["volume"],
        groups["image"],
        name if kind == "network" else None,
        owner=owner,
    )
    assert not errors and len(removed) == 1 and removed[0][-1] == name


def test_cleanup_never_removes_foreign_resource_after_uncertain_create():
    calls = []

    def docker(*args, **kw):
        calls.append(args)
        return SimpleNamespace(
            returncode=0, stdout=b'{"qbitbot.verification":"someone-else"}', stderr=b""
        )

    errors = cleanup_resources(docker, ["name"], [], [], None, owner="owned")
    assert errors
    assert all(call[0] == "inspect" for call in calls)
