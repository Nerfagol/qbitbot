"""Durable user language preferences, separate from download monitoring state."""

from pathlib import Path
import sqlite3

from i18n import Language, normalize_language


class PreferenceStore:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        path.chmod(0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS preferences (user_id INTEGER PRIMARY KEY, detected TEXT NOT NULL, override TEXT)"
        )
        self.db.commit()

    def get(self, user_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM preferences WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def remember(self, user_id: int, detected: Language) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO preferences(user_id, detected) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET detected=excluded.detected",
                (user_id, detected),
            )

    def set_override(self, user_id: int, language: Language) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO preferences VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET override=excluded.override",
                (user_id, language, language),
            )

    def overrides(self) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute("SELECT * FROM preferences WHERE override IS NOT NULL")
        ]

    def close(self) -> None:
        self.db.close()


class LanguageService:
    def __init__(self, store: PreferenceStore):
        self.store = store

    def for_user(self, user_id: int | None, telegram_code: str | None = None) -> Language:
        if user_id is None:
            return "en"
        row = self.store.get(user_id)
        if telegram_code is not None or row is None:
            self.store.remember(user_id, normalize_language(telegram_code))
            row = self.store.get(user_id)
        return normalize_language(row["override"] or row["detected"])

    def set_for_user(self, user_id: int, language: Language) -> None:
        if language not in ("en", "ru"):
            raise ValueError("Unsupported language")
        self.store.set_override(user_id, language)
