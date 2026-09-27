"""Small, synchronous SQLite transactions for durable monitoring subscriptions."""

import os
import json
import sqlite3
from pathlib import Path


class WatchStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Restrict permissions before SQLite writes chat/user identifiers.
        fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        path.chmod(0o600)
        self.db = sqlite3.connect(path, timeout=1)
        self.db.row_factory = sqlite3.Row
        try:
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError("Unsupported watch database schema")
            with self.db:
                self.db.execute("BEGIN IMMEDIATE")
                if version == 0:
                    self.db.execute("""CREATE TABLE watches (
                        chat_id INTEGER NOT NULL,
                        torrent_hash TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        message_id INTEGER,
                        status TEXT NOT NULL CHECK (status IN
                            ('active','pending','completed','missing','error','blocked','revoked')),
                        notice TEXT,
                        PRIMARY KEY (chat_id, torrent_hash)
                    )""")
                # Also exercise journal creation for an existing database.
                # Optional attachment metadata: old releases still read the unchanged
                # v1 watches/notice text and safely ignore this supplemental table.
                self.db.execute("""CREATE TABLE IF NOT EXISTS notice_markup (
                    chat_id INTEGER NOT NULL, torrent_hash TEXT NOT NULL,
                    markup TEXT NOT NULL, PRIMARY KEY(chat_id, torrent_hash))""")
                self.db.execute("PRAGMA user_version=1")
            # Detect invalid schemas at startup, not after accepting subscriptions.
            self.db.execute(
                "SELECT chat_id,torrent_hash,user_id,title,message_id,status,notice FROM watches"
            )
        except Exception:
            self.db.close()
            raise

    def subscribe(self, user_id, chat_id, torrent_hash, title):
        with self.db:
            self.db.execute(
                "DELETE FROM notice_markup WHERE chat_id=? AND torrent_hash=?",
                (chat_id, torrent_hash),
            )
            self.db.execute(
                """INSERT INTO watches (user_id,chat_id,torrent_hash,title,status)
                   VALUES (?,?,?,?,'active') ON CONFLICT(chat_id,torrent_hash)
                   DO UPDATE SET user_id=excluded.user_id,title=excluded.title,
                                 message_id=NULL,status='active',notice=NULL""",
                (user_id, chat_id, torrent_hash, title),
            )

    def get(self, chat_id, torrent_hash):
        row = self.db.execute(
            "SELECT * FROM watches WHERE chat_id=? AND torrent_hash=?", (chat_id, torrent_hash)
        ).fetchone()
        return dict(row) if row else None

    def unfinished(self):
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT * FROM watches WHERE status IN ('active','pending','error')"
            )
        ]

    def set_message(self, chat_id, torrent_hash, message_id):
        with self.db:
            self.db.execute(
                "UPDATE watches SET message_id=? WHERE chat_id=? AND torrent_hash=?",
                (message_id, chat_id, torrent_hash),
            )

    def set_status(self, chat_id, torrent_hash, status):
        with self.db:
            if status != "pending":
                self.db.execute(
                    "DELETE FROM notice_markup WHERE chat_id=? AND torrent_hash=?",
                    (chat_id, torrent_hash),
                )
            self.db.execute(
                "UPDATE watches SET status=? WHERE chat_id=? AND torrent_hash=?",
                (status, chat_id, torrent_hash),
            )

    def pending(self, chat_id, torrent_hash, text, markup=None):
        with self.db:
            self.db.execute(
                "UPDATE watches SET status='pending',notice=? WHERE chat_id=? AND torrent_hash=?",
                (text, chat_id, torrent_hash),
            )
            self.db.execute(
                "DELETE FROM notice_markup WHERE chat_id=? AND torrent_hash=?",
                (chat_id, torrent_hash),
            )
            if markup is not None:
                self.db.execute(
                    "INSERT INTO notice_markup VALUES (?, ?, ?)",
                    (
                        chat_id,
                        torrent_hash,
                        json.dumps(
                            {
                                "notice": text,
                                "user_id": self.get(chat_id, torrent_hash)["user_id"],
                                "markup": markup,
                            }
                        ),
                    ),
                )

    def pending_markup(self, chat_id, torrent_hash):
        row = self.db.execute(
            "SELECT n.markup, w.notice, w.user_id FROM notice_markup n JOIN watches w "
            "ON n.chat_id=w.chat_id AND n.torrent_hash=w.torrent_hash "
            "WHERE n.chat_id=? AND n.torrent_hash=?",
            (chat_id, torrent_hash),
        ).fetchone()
        if not row:
            return None
        saved = json.loads(row[0])
        if saved.get("notice") != row[1] or saved.get("user_id") != row[2]:
            return None  # A pre-feature release may have overwritten the notice after rollback.
        return saved.get("markup")

    def close(self):
        self.db.close()
