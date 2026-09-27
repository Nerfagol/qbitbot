import stat

import pytest

from qbitbot.preferences import LanguageService, PreferenceStore


def test_detection_and_override_survive_restart(tmp_path):
    path = tmp_path / "state" / "watches.preferences.sqlite3"
    store = PreferenceStore(path)
    service = LanguageService(store)
    assert service.for_user(101, "ru-RU") == "ru"
    assert service.for_user(202, "de") == "en"
    store.close()
    store = PreferenceStore(path)
    service = LanguageService(store)
    assert service.for_user(101) == "ru"
    service.set_for_user(101, "en")
    assert service.for_user(101, "ru") == "en"
    assert service.for_user(202) == "en"
    store.close()
    store = PreferenceStore(path)
    assert LanguageService(store).for_user(101) == "en"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    store.close()


def test_no_user_does_not_create_preference(tmp_path):
    store = PreferenceStore(tmp_path / "p.sqlite3")
    service = LanguageService(store)
    assert service.for_user(None, "ru") == "en"
    assert store.get(101) is None
    with pytest.raises(ValueError):
        service.set_for_user(101, "de")
    store.close()


def test_preferences_leave_watch_database_unchanged(tmp_path):
    watch = tmp_path / "watches.sqlite3"
    watch.write_bytes(b"original watch bytes")
    store = PreferenceStore(watch.with_suffix(".preferences.sqlite3"))
    LanguageService(store).set_for_user(101, "ru")
    store.close()
    assert watch.read_bytes() == b"original watch bytes"
