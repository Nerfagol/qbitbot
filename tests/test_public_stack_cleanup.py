"""The public installer rehearsal can remove only its own disposable resources."""

import json
import subprocess

import pytest

from integration.public_stack import cleanup_project, validate_isolation

PROJECT = "qbitbot-public-test-0123456789ab"


def test_cleanup_discovers_resources_after_partial_start_or_timeout():
    calls = []

    def docker(*args, **kw):
        calls.append(args)
        if args[:2] == ("ps", "-aq"):
            return b"owned-container\nowned-container\n"
        if args[:2] == ("volume", "ls"):
            return b"owned-volume\n"
        if args[:2] == ("network", "ls"):
            return b"owned-network\n"
        if args[0] == "inspect":
            return json.dumps({"com.docker.compose.project": PROJECT}).encode()
        return b""

    cleanup_project(docker, PROJECT)
    deletes = [c for c in calls if c[0] == "rm" or c[:2] in [("volume", "rm"), ("network", "rm")]]
    assert deletes == [
        ("rm", "-f", "owned-container"),
        ("volume", "rm", "owned-volume"),
        ("network", "rm", "owned-network"),
    ]
    assert not any("prune" in c for c in calls)


def test_cleanup_rejects_foreign_resource_and_reports_teardown_failure():
    def docker(*args, **kw):
        if args[:2] == ("ps", "-aq"):
            return b"foreign\n"
        if args[0] == "inspect":
            return b'{"com.docker.compose.project":"personal"}'
        if "rm" in args:
            pytest.fail("Never delete a mismatched resource")
        return b""

    with pytest.raises(RuntimeError, match="cleanup"):
        cleanup_project(docker, PROJECT)


def test_cleanup_failure_is_not_success():
    def docker(*args, **kw):
        if args[:2] == ("ps", "-aq"):
            raise subprocess.TimeoutExpired("docker", 1)
        return b""

    with pytest.raises(RuntimeError, match="cleanup"):
        cleanup_project(docker, PROJECT)


@pytest.mark.parametrize("change", ["port", "bind", "external", "host", "socket"])
def test_isolation_rejects_host_or_external_access(change):
    cfg = {
        "services": {"bot": {"networks": {"default": None}, "volumes": []}},
        "networks": {"default": {"internal": True}},
        "volumes": {},
    }
    service = cfg["services"]["bot"]
    if change == "port":
        service["ports"] = [{"published": "8080"}]
    if change in ("bind", "socket"):
        service["volumes"] = [{"type": "bind", "source": "/var/run/docker.sock", "target": "/x"}]
    if change == "external":
        cfg["networks"]["default"] = {"external": True}
    if change == "host":
        service["network_mode"] = "host"
    with pytest.raises(ValueError):
        validate_isolation(cfg)


def test_create_timeout_still_cleans_both_recorded_projects(monkeypatch, capsys):
    from integration import public_stack

    cleaned = []
    monkeypatch.setattr(public_stack, "export_checkout", lambda root: None)

    def timeout(*args):
        raise subprocess.TimeoutExpired("compose up", 1)

    monkeypatch.setattr(public_stack, "fresh", timeout)
    monkeypatch.setattr(
        public_stack, "cleanup_project", lambda docker, project: cleaned.append(project)
    )
    monkeypatch.setattr(
        public_stack.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, b"", b"")
    )
    assert public_stack.main(["--scenario", "fresh"]) == 1
    assert len(cleaned) == 2 and cleaned[0] == cleaned[1] + "-only"
    assert "TimeoutExpired" in capsys.readouterr().out
