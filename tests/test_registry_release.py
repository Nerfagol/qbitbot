"""Exercise release trust boundaries without GitHub or registry access."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


@pytest.fixture
def release():
    path = ROOT / "integration/registry_release.py"
    assert path.exists(), "registry release gate has not been implemented"
    spec = importlib.util.spec_from_file_location("registry_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.4.0"\n')
    (tmp_path / "CHANGELOG.md").write_text("## 0.4.0 — 2026-11-07\n\nReviewed changes.\n")
    return tmp_path


def runs():
    return [
        {
            "path": ".github/workflows/" + name + ".yml",
            "head_sha": SHA,
            "head_branch": "main",
            "event": "push",
            "status": "completed",
            "conclusion": "success",
            "id": i + 1,
        }
        for i, name in enumerate(("check", "containers", "security", "codeql"))
    ]


def test_release_metadata_keeps_version_source_and_registry_names_aligned(release, source):
    result = release.metadata(source, "v0.4.0", SHA, "Nerfagol/qbitbot")
    assert result["version"] == "0.4.0"
    assert result["prefix"] == "ghcr.io/nerfagol/qbitbot"
    assert result["revision"] == SHA


@pytest.mark.parametrize("tag", ["main", "v0.3.0", "v0.4.0-rc1", "v0.4.0\nINJECT=1"])
def test_invalid_or_mismatched_release_is_rejected(release, source, tag):
    with pytest.raises(ValueError):
        release.metadata(source, tag, SHA, "Nerfagol/qbitbot")


def test_release_requires_dated_changelog(release, source):
    (source / "CHANGELOG.md").write_text("## Unreleased\n")
    with pytest.raises(ValueError):
        release.metadata(source, "v0.4.0", SHA, "Nerfagol/qbitbot")


def test_a_branch_named_like_a_version_cannot_publish(release, source):
    with pytest.raises(ValueError):
        release.metadata(source, "v0.4.0", SHA, "Nerfagol/qbitbot", ref_type="branch")


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_registry_api_errors_cannot_be_mistaken_for_missing_packages(release, monkeypatch, status):
    from types import SimpleNamespace

    monkeypatch.setattr(
        release.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr=f"error (HTTP {status})"),
    )
    with pytest.raises(RuntimeError):
        release.api("users/fixture/packages/container/fixture/versions", missing_ok=True)


def test_only_exact_main_push_successes_open_the_gate(release):
    assert release.checks_passed(runs(), SHA)
    for key, value in (("head_sha", "b" * 40), ("event", "pull_request"), ("head_branch", "other")):
        records = runs()
        records[0][key] = value
        assert not release.checks_passed(records, SHA)


def test_newer_failed_or_pending_run_cannot_reuse_old_success(release):
    records = runs()
    latest = dict(records[0], id=99, status="in_progress", conclusion=None)
    assert not release.checks_passed(records + [latest], SHA)
    latest.update(status="completed", conclusion="failure")
    with pytest.raises(ValueError):
        release.checks_passed(records + [latest], SHA)


def test_existing_version_tag_is_never_overwritten(release):
    versions = [{"metadata": {"container": {"tags": ["0.4.0", "sha-" + SHA]}}}]
    with pytest.raises(ValueError):
        release.check_available(versions, "0.4.0")
    release.check_available(versions, "0.4.1")


def test_one_repository_uses_distinct_component_version_and_source_tags(release):
    expected = {
        "bot": ("0.4.0", "sha-" + SHA),
        "qbittorrent": ("qbittorrent-0.4.0", "qbittorrent-sha-" + SHA),
        "jackett": ("jackett-0.4.0", "jackett-sha-" + SHA),
        "flaresolverr": ("flaresolverr-0.4.0", "flaresolverr-sha-" + SHA),
    }
    assert {c: release.component_tags(c, "0.4.0", SHA) for c in expected} == expected
    assert len({tag for tags in expected.values() for tag in tags}) == 8


@pytest.mark.parametrize("tag", ["jackett-0.4.0", "flaresolverr-sha-" + SHA])
def test_companion_tag_collision_blocks_a_single_package_release(release, tag):
    versions = [{"metadata": {"container": {"tags": [tag]}}}]
    with pytest.raises(ValueError):
        release.check_release_available(versions, "0.4.0", SHA)
