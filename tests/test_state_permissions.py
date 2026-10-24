"""Offline ownership migration must reject unsafe trees before changing them."""

import os
from pathlib import Path

import pytest


def migrate(path, monkeypatch):
    from qbitbot.cli.state_permissions import migrate_state

    calls = []
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        os, "chown", lambda path, uid, gid, **kw: calls.append((Path(path), uid, gid))
    )
    migrate_state(path)
    return calls


def test_migration_preserves_content_and_uses_only_fixed_bot_identity(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    snapshot = state / "snapshot"
    snapshot.mkdir()
    database = snapshot / "watches.sqlite3"
    database.write_bytes(b"synthetic database")
    calls = migrate(state, monkeypatch)
    assert {path for path, _, _ in calls} == {state, snapshot, database}
    assert all((uid, gid) == (1000, 1000) for _, uid, gid in calls)
    assert database.read_bytes() == b"synthetic database"
    assert database.stat().st_mode & 0o777 == 0o600
    assert state.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("unsafe", ["symlink", "hardlink", "fifo"])
def test_unsafe_tree_is_rejected_before_any_ownership_change(tmp_path, monkeypatch, unsafe):
    state = tmp_path / "state"
    state.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("untouched")
    (state / "ordinary").write_text("unchanged")
    target = state / "unsafe"
    if unsafe == "symlink":
        target.symlink_to(outside)
    elif unsafe == "hardlink":
        os.link(outside, target)
    else:
        os.mkfifo(target)
    with pytest.raises(ValueError, match="Unsafe"):
        migrate(state, monkeypatch)
    assert outside.read_text() == "untouched"
    assert (state / "ordinary").stat().st_mode & 0o777 == 0o644


def test_root_directory_and_unprivileged_migration_are_rejected(tmp_path, monkeypatch):
    from qbitbot.cli.state_permissions import migrate_state

    monkeypatch.setattr(os, "geteuid", lambda: 0)
    with pytest.raises(ValueError):
        migrate_state(Path("/"))
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    with pytest.raises(PermissionError):
        migrate_state(tmp_path)


def test_cli_requires_explicit_offline_acknowledgment():
    from qbitbot.cli.state_permissions import main

    with pytest.raises(SystemExit) as error:
        main([])
    assert error.value.code == 2
