"""
SQLite store — personal file: ~/…/user.db (never git-pushed).

Default path: ~/.local/share/gnom-hub/user.db
Override: GNOM_USER_DB=/absolute/or/~/path/user.db

Holds durable WARM facts, HOT session messages/facts, and simple KV.
Legacy data/warm + data/hot JSON is migrated once from the project tree.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gnom_hub.config.paths import project_root

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS warm_facts (
  id     INTEGER PRIMARY KEY AUTOINCREMENT,
  text   TEXT NOT NULL COLLATE NOCASE,
  source TEXT NOT NULL DEFAULT 'warm',
  ts     TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_warm_text ON warm_facts(text);

CREATE TABLE IF NOT EXISTS hot_messages (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  role    TEXT NOT NULL,
  content TEXT NOT NULL,
  ts      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hot_facts (
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  text TEXT NOT NULL,
  ts   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

_lock = threading.RLock()
_instances: dict[str, GnomDatabase] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_user_db_path() -> Path:
    """
    Personal DB in the user's home (never inside the git repo).

    Default: ~/.local/share/gnom-hub/user.db
    Override with env GNOM_USER_DB (or GNOM_DB_PATH).
    """
    raw = (os.getenv("GNOM_USER_DB") or os.getenv("GNOM_DB_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".local" / "share" / "gnom-hub" / "user.db").resolve()


def resolve_db_path(root: Path | None = None) -> Path:
    """
    Personal home user.db for the real hub; under {root}/data/user.db for
    tests/tmp roots so unit tests never touch your real DB.
    """
    env = (os.getenv("GNOM_USER_DB") or os.getenv("GNOM_DB_PATH") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    r = Path(root) if root is not None else project_root()
    try:
        if r.resolve() != project_root().resolve():
            return (r / "data" / "user.db").resolve()
    except OSError:
        return (r / "data" / "user.db").resolve()
    return default_user_db_path()


def get_db(root: Path | None = None) -> GnomDatabase:
    """Process-wide DB (keyed by db file path)."""
    r = Path(root) if root is not None else project_root()
    path = resolve_db_path(r)
    key = str(path)
    with _lock:
        if key not in _instances:
            _instances[key] = GnomDatabase(r, db_path=path)
        return _instances[key]


class GnomDatabase:
    """Your personal Gnom database (SQLite user.db in home)."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        db_path: Path | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else project_root()
        # Project data/ only for one-time migration from old JSONL files
        self.data_dir = self.root / "data"
        self.path = Path(db_path) if db_path is not None else default_user_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we use explicit BEGIN
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        with _lock:
            self._conn.executescript(_SCHEMA)
            self._migrate_legacy_once()

    def close(self) -> None:
        with _lock:
            self._conn.close()

    def _meta_get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def _meta_set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def _migrate_legacy_once(self) -> None:
        if self._meta_get("migrated_jsonl_v1") == "1":
            return
        # WARM JSONL
        warm_path = self.data_dir / "warm" / "facts.jsonl"
        if warm_path.is_file():
            for line in warm_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                text = line
                ts = _utc_now_iso()
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict) and obj.get("text"):
                        text = str(obj["text"]).strip()
                        ts = str(obj.get("ts") or ts)
                    elif isinstance(obj, str):
                        text = obj.strip()
                except json.JSONDecodeError:
                    pass
                if text:
                    self.warm_add(text, source="migrate", ts=ts)
        # HOT session.json
        session_path = self.data_dir / "hot" / "session.json"
        if session_path.is_file():
            try:
                data = json.loads(session_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            if not self.hot_message_count():
                for m in data.get("messages") or []:
                    if isinstance(m, dict):
                        self.hot_add_message(
                            str(m.get("role") or "?"),
                            str(m.get("content") or ""),
                            ts=str(m.get("ts") or _utc_now_iso()),
                        )
            if not self.hot_fact_count():
                for f in data.get("facts") or []:
                    if str(f).strip():
                        self.hot_add_fact(str(f).strip(), ts=_utc_now_iso())
            if data.get("updated_at"):
                self.kv_set("hot_updated_at", str(data["updated_at"]))
        self._meta_set("migrated_jsonl_v1", "1")
        self._meta_set("migrated_at", _utc_now_iso())

    # ── WARM ──────────────────────────────────────────────────────────

    def warm_all(self, *, limit: int | None = None) -> list[str]:
        with _lock:
            q = "SELECT text FROM warm_facts ORDER BY id ASC"
            if limit is not None:
                q += f" LIMIT {int(limit)}"
            rows = self._conn.execute(q).fetchall()
        return [str(r["text"]) for r in rows]

    def warm_recent(self, limit: int = 12) -> list[str]:
        with _lock:
            rows = self._conn.execute(
                "SELECT text FROM warm_facts ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return list(reversed([str(r["text"]) for r in rows]))

    def warm_count(self) -> int:
        with _lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM warm_facts").fetchone()
        return int(row["n"] if row else 0)

    def warm_add(self, text: str, *, source: str = "warm", ts: str | None = None) -> bool:
        t = " ".join(str(text).split()).strip()
        if not t:
            return False
        try:
            with _lock:
                self._conn.execute(
                    "INSERT INTO warm_facts(text, source, ts) VALUES (?, ?, ?)",
                    (t, source or "warm", ts or _utc_now_iso()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def warm_remove(self, text: str) -> bool:
        t = " ".join(str(text).split()).strip()
        if not t:
            return False
        with _lock:
            cur = self._conn.execute("DELETE FROM warm_facts WHERE text = ? COLLATE NOCASE", (t,))
        return cur.rowcount > 0

    def warm_remove_at(self, index: int) -> str | None:
        """1-based index in all_facts order."""
        facts = self.warm_all()
        if index < 1 or index > len(facts):
            return None
        text = facts[index - 1]
        self.warm_remove(text)
        return text

    def warm_clear(self) -> int:
        with _lock:
            n = self.warm_count()
            self._conn.execute("DELETE FROM warm_facts")
        return n

    def warm_trim(self, max_facts: int) -> None:
        n = self.warm_count()
        if n <= max_facts:
            return
        drop = n - max_facts
        with _lock:
            self._conn.execute(
                "DELETE FROM warm_facts WHERE id IN ("
                "SELECT id FROM warm_facts ORDER BY id ASC LIMIT ?)",
                (drop,),
            )

    # ── HOT ───────────────────────────────────────────────────────────

    def hot_messages(self) -> list[dict[str, str]]:
        with _lock:
            rows = self._conn.execute(
                "SELECT role, content FROM hot_messages ORDER BY id ASC"
            ).fetchall()
        return [{"role": str(r["role"]), "content": str(r["content"])} for r in rows]

    def hot_message_count(self) -> int:
        with _lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM hot_messages").fetchone()
        return int(row["n"] if row else 0)

    def hot_add_message(self, role: str, content: str, *, ts: str | None = None) -> None:
        with _lock:
            self._conn.execute(
                "INSERT INTO hot_messages(role, content, ts) VALUES (?, ?, ?)",
                (str(role or "?"), str(content or ""), ts or _utc_now_iso()),
            )
        self.kv_set("hot_updated_at", _utc_now_iso())

    def hot_facts(self) -> list[str]:
        with _lock:
            rows = self._conn.execute("SELECT text FROM hot_facts ORDER BY id ASC").fetchall()
        return [str(r["text"]) for r in rows]

    def hot_fact_count(self) -> int:
        with _lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM hot_facts").fetchone()
        return int(row["n"] if row else 0)

    def hot_add_fact(self, text: str, *, ts: str | None = None) -> bool:
        t = " ".join(str(text).split()).strip()
        if not t:
            return False
        low = t.lower()
        for existing in self.hot_facts():
            if existing.lower() == low:
                return False
        with _lock:
            self._conn.execute(
                "INSERT INTO hot_facts(text, ts) VALUES (?, ?)",
                (t, ts or _utc_now_iso()),
            )
        self.kv_set("hot_updated_at", _utc_now_iso())
        return True

    def hot_remove_fact(self, text: str) -> bool:
        t = " ".join(str(text).split()).strip()
        with _lock:
            cur = self._conn.execute("DELETE FROM hot_facts WHERE lower(text) = lower(?)", (t,))
        return cur.rowcount > 0

    def hot_remove_fact_at(self, index: int) -> str | None:
        facts = self.hot_facts()
        if index < 1 or index > len(facts):
            return None
        text = facts[index - 1]
        self.hot_remove_fact(text)
        return text

    def hot_clear_facts(self) -> int:
        n = self.hot_fact_count()
        with _lock:
            self._conn.execute("DELETE FROM hot_facts")
        return n

    def hot_clear_session(self) -> None:
        with _lock:
            self._conn.execute("DELETE FROM hot_messages")
            self._conn.execute("DELETE FROM hot_facts")
        self.kv_set("hot_updated_at", _utc_now_iso())

    def hot_set_facts(self, facts: list[str]) -> None:
        with _lock:
            self._conn.execute("DELETE FROM hot_facts")
            for f in facts:
                t = " ".join(str(f).split()).strip()
                if t:
                    self._conn.execute(
                        "INSERT INTO hot_facts(text, ts) VALUES (?, ?)",
                        (t, _utc_now_iso()),
                    )
        self.kv_set("hot_updated_at", _utc_now_iso())

    # ── KV ────────────────────────────────────────────────────────────

    def kv_get(self, key: str, default: str | None = None) -> str | None:
        with _lock:
            row = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def kv_set(self, key: str, value: str) -> None:
        with _lock:
            self._conn.execute(
                "INSERT INTO kv(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def kv_get_json(self, key: str, default: Any = None) -> Any:
        raw = self.kv_get(key)
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default

    def kv_set_json(self, key: str, value: Any) -> None:
        self.kv_set(key, json.dumps(value, ensure_ascii=False))

    def snapshot_info(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "warm_facts": self.warm_count(),
            "hot_messages": self.hot_message_count(),
            "hot_facts": self.hot_fact_count(),
            "migrated": self._meta_get("migrated_jsonl_v1") == "1",
        }
