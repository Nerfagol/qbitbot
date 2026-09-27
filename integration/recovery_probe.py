"""State assertions run in newly created, network-isolated release containers."""

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys

sys.path.insert(0, "/app")
from watch_store import WatchStore  # noqa: E402

WATCH = Path("/state/watches.sqlite3")
KEY = (101, "c" * 40)
NOTICE = "Скачивание завершено:\nGenerated recovery fixture"
MARKUP = {"inline_keyboard": [[{"text": "Загрузки", "callback_data": "nav:downloads"}]]}


def check():
    store = WatchStore(WATCH)
    row = store.get(*KEY)
    assert row["status"] == "pending" and row["notice"] == NOTICE
    assert store.pending_markup(*KEY) == MARKUP
    assert store.db.execute("PRAGMA user_version").fetchone()[0] == 1
    store.close()
    with sqlite3.connect(WATCH.with_suffix(".health.sqlite3")) as conn:
        assert conn.execute("SELECT count(*) FROM cards WHERE user_id=101").fetchone()[0] == 1


def main(mode):
    if mode == "seed":
        from preferences import LanguageService, PreferenceStore

        service = LanguageService(PreferenceStore(WATCH.with_suffix(".preferences.sqlite3")))
        service.set_for_user(101, "ru")
        service.store.close()
        store = WatchStore(WATCH)
        store.subscribe(101, KEY[0], KEY[1], "Generated recovery fixture")
        store.pending(*KEY, NOTICE, MARKUP)
        store.close()
    elif mode == "restore":
        source = Path("/source/snapshot")
        manifest = json.loads((source / "manifest.json").read_text())
        for name, digest in manifest.items():
            assert digest != "absent"
            original = source / name
            assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
            target = WATCH if name == "watches.sqlite3" else WATCH.with_suffix("." + name)
            assert not target.exists()
            shutil.copyfile(original, target)
            target.chmod(0o600)
        check()
    elif mode == "old":
        # Intentionally imports only the original public watch reader.
        check()
    else:
        from preferences import LanguageService, PreferenceStore

        check()
        service = LanguageService(PreferenceStore(WATCH.with_suffix(".preferences.sqlite3")))
        assert service.for_user(101) == "ru"
        service.store.close()
    print(json.dumps({"checks": [mode + " state verified"]}))


if __name__ == "__main__":
    main(sys.argv[1])
