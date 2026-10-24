"""Online snapshots of bot-owned SQLite databases; never overwrite a destination."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time


def backup_databases(watch_path: Path, destination: Path) -> dict[str, str]:
    watch_path, destination = Path(watch_path), Path(destination)
    sources = {
        "watches.sqlite3": watch_path,
        "health.sqlite3": watch_path.with_suffix(".health.sqlite3"),
        "preferences.sqlite3": watch_path.with_suffix(".preferences.sqlite3"),
    }
    for source in sources.values():
        if source.is_symlink():
            raise ValueError("Database symlinks are not supported")
    if not watch_path.is_file():
        raise FileNotFoundError("Watch database is required")
    destination.mkdir(mode=0o700, exist_ok=False)
    result = {}
    try:
        for name, source in sources.items():
            if not source.exists():
                result[name] = "absent"
                continue
            target = destination / name
            target.touch(mode=0o600, exist_ok=False)
            deadline = time.monotonic() + 60

            def progress(status, remaining, total):
                if time.monotonic() > deadline:
                    raise TimeoutError("Database backup exceeded its deadline")

            reader = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
            writer = sqlite3.connect(target)
            try:
                reader.backup(writer, pages=256, progress=progress)
                if writer.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise sqlite3.DatabaseError("Backup integrity check failed")
            finally:
                reader.close()
                writer.close()
            result[name] = hashlib.sha256(target.read_bytes()).hexdigest()
            # Re-open the completed file, rather than trusting the live writer.
            check = sqlite3.connect(target.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                if check.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise sqlite3.DatabaseError("Reopened backup integrity check failed")
            finally:
                check.close()
        manifest = destination / "manifest.json"
        manifest.touch(mode=0o600, exist_ok=False)
        manifest.write_text(json.dumps(result, indent=2) + "\n")
        for name, digest in result.items():
            if (
                digest != "absent"
                and hashlib.sha256((destination / name).read_bytes()).hexdigest() != digest
            ):
                raise sqlite3.DatabaseError("Backup checksum verification failed")
        return result
    except BaseException:
        shutil.rmtree(destination)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watch-db", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = backup_databases(args.watch_db, args.destination)
    except (OSError, ValueError, sqlite3.Error) as error:
        print(
            "Backup failed: "
            + type(error).__name__
            + ". Check source access and use a new destination."
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
