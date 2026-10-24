"""Explicit offline migration of a bot state volume to UID/GID 1000.

Stop all readers/writers and back up state first. This command is never part of
container startup and changes ownership/permissions only, never database content.
"""

import argparse
import os
from pathlib import Path
import stat


def migrate_state(directory: Path) -> int:
    if os.geteuid() != 0:
        raise PermissionError("Offline migration requires root in a maintenance container")
    directory = Path(directory)
    if not directory.is_absolute() or directory == Path("/"):
        raise ValueError("Unsafe state directory")
    root_info = directory.lstat()
    if not stat.S_ISDIR(root_info.st_mode):
        raise ValueError("Unsafe state directory")
    entries = [(directory, root_info)]

    # Validate the entire offline tree before changing anything. Never follow
    # symlinks, cross filesystem boundaries or change shared hardlinked files.
    def fail_walk(error):
        raise error

    for parent, dirs, files in os.walk(directory, followlinks=False, onerror=fail_walk):
        for name in dirs + files:
            path = Path(parent) / name
            info = path.lstat()
            if (
                info.st_dev != root_info.st_dev
                or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode))
                or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
                or os.path.ismount(path)
            ):
                raise ValueError("Unsafe entry in state directory")
            entries.append((path, info))
    for path, info in reversed(entries):
        os.chmod(path, 0o700 if stat.S_ISDIR(info.st_mode) else 0o600, follow_symlinks=False)
        os.chown(path, 1000, 1000, follow_symlinks=False)
    return len(entries)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        required=True,
        action="store_true",
        help="Confirm all state readers/writers are stopped and a backup exists",
    )
    args = parser.parse_args(argv)
    if args.offline:
        try:
            count = migrate_state(Path("/state"))
        except (OSError, ValueError):
            parser.exit(1, "State migration failed; verify the offline volume and permissions.\n")
        print(f"Migrated {count} state entries to UID/GID 1000; content unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
