"""Online backup correctness and non-destructive destination handling."""

import hashlib
import json
import sqlite3

import pytest

from backup_state import backup_databases


def database(path, value):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE data(value TEXT)")
    conn.execute("INSERT INTO data VALUES (?)", (value,))
    conn.commit()
    return conn


def test_committed_wal_and_three_databases_are_verified_without_changing_source(tmp_path):
    watch = tmp_path / "custom.sqlite3"
    paths = [watch, watch.with_suffix(".health.sqlite3"), watch.with_suffix(".preferences.sqlite3")]
    connections = [database(path, str(i)) for i, path in enumerate(paths)]
    originals = {path: path.read_bytes() for path in paths}
    try:
        result = backup_databases(watch, tmp_path / "snapshot")
        for index, name in enumerate(("watches.sqlite3", "health.sqlite3", "preferences.sqlite3")):
            output = tmp_path / "snapshot" / name
            with sqlite3.connect(output) as conn:
                assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
                assert conn.execute("SELECT value FROM data").fetchone() == (str(index),)
            assert result[name] == hashlib.sha256(output.read_bytes()).hexdigest()
            assert output.stat().st_mode & 0o777 == 0o600
        assert (tmp_path / "snapshot").stat().st_mode & 0o777 == 0o700
        manifest = tmp_path / "snapshot" / "manifest.json"
        assert json.loads(manifest.read_text()) == result
        assert manifest.stat().st_mode & 0o777 == 0o600
        assert all(path.read_bytes() == originals[path] for path in paths)
    finally:
        for conn in connections:
            conn.close()


def test_existing_destination_is_never_overwritten(tmp_path):
    source = tmp_path / "watches.sqlite3"
    conn = database(source, "safe")
    target = tmp_path / "existing"
    target.mkdir()
    sentinel = target / "keep"
    sentinel.write_bytes(b"unchanged")
    with pytest.raises(FileExistsError):
        backup_databases(source, target)
    assert sentinel.read_bytes() == b"unchanged"
    conn.close()


def test_optional_absence_is_explicit_and_missing_watch_is_rejected(tmp_path):
    source = tmp_path / "watches.sqlite3"
    with pytest.raises(FileNotFoundError):
        backup_databases(source, tmp_path / "missing")
    conn = database(source, "test")
    result = backup_databases(source, tmp_path / "snapshot")
    assert result["health.sqlite3"] == result["preferences.sqlite3"] == "absent"
    conn.close()


def test_corruption_or_symlink_is_rejected_without_success_manifest(tmp_path):
    source = tmp_path / "broken.sqlite3"
    source.write_bytes(b"not sqlite")
    with pytest.raises(sqlite3.DatabaseError):
        backup_databases(source, tmp_path / "snapshot")
    assert not (tmp_path / "snapshot" / "manifest.json").exists()
    link = tmp_path / "link.sqlite3"
    link.symlink_to(source)
    with pytest.raises(ValueError):
        backup_databases(link, tmp_path / "link-backup")
