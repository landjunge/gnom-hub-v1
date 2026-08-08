"""
SQLite — live DB only at {GNOM_WS or sibling WS}/User/user.db

No home path, no hub/User copies.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gnom_hub.config.paths import project_root, user_dir

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
CREATE INDEX IF NOT EXISTS idx_warm_source_id ON warm_facts(source, id);

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
CREATE UNIQUE INDEX IF NOT EXISTS idx_hot_facts_text ON hot_facts(text);

CREATE TABLE IF NOT EXISTS kv (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

_lock = threading.RLock()
_instances: dict[str, GnomDatabase] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_user_db_path(root: Path | None = None) -> Path:
    raw = (os.getenv("GNOM_USER_DB") or os.getenv("GNOM_DB_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (user_dir(root) / "user.db").resolve()


def resolve_db_path(root: Path | None = None) -> Path:
    return default_user_db_path(root if root is not None else project_root())


def sync_user_db_backup(root: Path | None = None) -> Path | None:
    from gnom_hub.config.user_workspace import backup_user_db

    return backup_user_db(root)


def get_db(root: Path | None = None) -> GnomDatabase:
    r = Path(root) if root is not None else project_root()
    path = resolve_db_path(r)
    key = str(path)
    with _lock:
        if key not in _instances:
            _instances[key] = GnomDatabase(r, db_path=path)
        return _instances[key]


class GnomDatabase:
    """Personal SQLite at {WS}/User/user.db."""

    def __init__(
        self,
        root: Path | None = None,
        *,
        db_path: Path | None = None,
    ) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.data_dir = self.root / "data"
        self.path = Path(db_path) if db_path is not None else default_user_db_path(self.root)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we use explicit BEGIN
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        # Storage-friendly defaults for a local single-user hub DB
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=MEMORY")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA cache_size=-8000")  # ~8 MiB page cache
        self._conn.execute("PRAGMA mmap_size=67108864")  # 64 MiB mmap
        with _lock:
            self._conn.executescript(_SCHEMA)
            self._migrate_legacy_once()
            self._ensure_indexes()

    def close(self) -> None:
        """Close connection and drop cache entry (M10)."""
        with _lock:
            key = str(self.path.resolve()) if self.path else str(self.path)
            try:
                self._conn.close()
            finally:
                # Remove only our instance (avoid clobbering a reopened path)
                if _instances.get(key) is self:
                    _instances.pop(key, None)
                # Also try un-resolved key variants used at get_db time
                for k, inst in list(_instances.items()):
                    if inst is self:
                        _instances.pop(k, None)

    def _meta_get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def _meta_set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def _ensure_indexes(self) -> None:
        """Idempotent indexes for trim/dupe paths (older DBs predate schema string)."""
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_warm_source_id ON warm_facts(source, id)"
        )
        try:
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_hot_facts_text ON hot_facts(text)"
            )
        except sqlite3.OperationalError:
            # Pre-existing duplicate HOT facts — keep oldest row per text
            self._conn.execute(
                "DELETE FROM hot_facts WHERE id NOT IN ("
                "  SELECT MIN(id) FROM hot_facts GROUP BY text"
                ")"
            )
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_hot_facts_text ON hot_facts(text)"
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

    def warm_clear(self, *, keep_flex: bool = False) -> int:
        """Clear WARM facts. keep_flex=True preserves source='flex' (Flex wishes)."""
        with _lock:
            if keep_flex:
                cur = self._conn.execute(
                    "DELETE FROM warm_facts WHERE IFNULL(source, 'warm') != 'flex'"
                )
                return int(cur.rowcount or 0)
            n = self.warm_count()
            self._conn.execute("DELETE FROM warm_facts")
            return n

    def warm_count_source(self, source: str) -> int:
        with _lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM warm_facts WHERE source = ?",
                (source,),
            ).fetchone()
        return int(row["n"] if row else 0)

    def warm_trim(
        self,
        max_facts: int,
        *,
        flex_reserve: int = 40,
    ) -> dict[str, int]:
        """Drop oldest facts until at most max_facts remain.

        Policy (protect-first):
        1) delete oldest non-flex (source != 'flex') first
        2) only then oldest flex, but never below flex_reserve flex rows
           (may leave count > max_facts if only flex remains)
        """
        stats = {
            "before": 0,
            "after": 0,
            "dropped_non_flex": 0,
            "dropped_flex": 0,
            "flex_left": 0,
        }
        n = self.warm_count()
        stats["before"] = n
        if n <= max_facts:
            stats["after"] = n
            stats["flex_left"] = self.warm_count_source("flex")
            return stats

        drop = n - max_facts
        with _lock:
            # Phase 1: non-flex first (oldest id)
            cur = self._conn.execute(
                "DELETE FROM warm_facts WHERE id IN ("
                "  SELECT id FROM warm_facts"
                "  WHERE IFNULL(source, 'warm') != 'flex'"
                "  ORDER BY id ASC"
                "  LIMIT ?"
                ")",
                (drop,),
            )
            dropped_nf = int(cur.rowcount or 0)
            stats["dropped_non_flex"] = dropped_nf
            still = drop - dropped_nf

            if still > 0:
                flex_n = int(
                    self._conn.execute(
                        "SELECT COUNT(*) AS n FROM warm_facts WHERE source = 'flex'"
                    ).fetchone()["n"]
                )
                can_drop_flex = max(0, flex_n - max(0, int(flex_reserve)))
                still = min(still, can_drop_flex)
                if still > 0:
                    cur2 = self._conn.execute(
                        "DELETE FROM warm_facts WHERE id IN ("
                        "  SELECT id FROM warm_facts WHERE source = 'flex'"
                        "  ORDER BY id ASC"
                        "  LIMIT ?"
                        ")",
                        (still,),
                    )
                    stats["dropped_flex"] = int(cur2.rowcount or 0)

        stats["after"] = self.warm_count()
        stats["flex_left"] = self.warm_count_source("flex")
        return stats

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
        try:
            with _lock:
                self._conn.execute(
                    "INSERT INTO hot_facts(text, ts) VALUES (?, ?)",
                    (t, ts or _utc_now_iso()),
                )
        except sqlite3.IntegrityError:
            return False
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
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute("DELETE FROM hot_messages")
                self._conn.execute("DELETE FROM hot_facts")
                self._conn.execute(
                    "INSERT INTO kv(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    ("hot_updated_at", _utc_now_iso()),
                )
                self._conn.execute("COMMIT")
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    def hot_set_facts(self, facts: list[str]) -> None:
        """Replace HOT facts in one transaction."""
        ts = _utc_now_iso()
        with _lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute("DELETE FROM hot_facts")
                seen: set[str] = set()
                for f in facts:
                    t = " ".join(str(f).split()).strip()
                    if not t:
                        continue
                    key = t.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        self._conn.execute(
                            "INSERT INTO hot_facts(text, ts) VALUES (?, ?)",
                            (t, ts),
                        )
                    except sqlite3.IntegrityError:
                        continue
                self._conn.execute(
                    "INSERT INTO kv(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    ("hot_updated_at", ts),
                )
                self._conn.execute("COMMIT")
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    def hot_replace_session(
        self,
        messages: list[dict[str, Any]],
        facts: list[str],
        *,
        updated_at: str | None = None,
    ) -> None:
        """
        Atomic HOT clear + rebuild (C2).

        clear-then-insert without a transaction left empty HOT if the process
        died mid-save; one IMMEDIATE transaction keeps the previous session
        until commit succeeds.
        """
        ts = updated_at or _utc_now_iso()
        with _lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                self._conn.execute("DELETE FROM hot_messages")
                self._conn.execute("DELETE FROM hot_facts")
                for m in messages or []:
                    if not isinstance(m, dict):
                        continue
                    self._conn.execute(
                        "INSERT INTO hot_messages(role, content, ts) VALUES (?, ?, ?)",
                        (
                            str(m.get("role") or "?"),
                            str(m.get("content") or ""),
                            str(m.get("ts") or ts),
                        ),
                    )
                seen: set[str] = set()
                for f in facts or []:
                    t = " ".join(str(f).split()).strip()
                    if not t:
                        continue
                    key = t.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        self._conn.execute(
                            "INSERT INTO hot_facts(text, ts) VALUES (?, ?)",
                            (t, ts),
                        )
                    except sqlite3.IntegrityError:
                        continue
                self._conn.execute(
                    "INSERT INTO kv(key, value) VALUES(?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    ("hot_updated_at", ts),
                )
                self._conn.execute("COMMIT")
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    def export_consistent_copy(self, dest: Path) -> Path:
        """
        Online backup API → single consistent file (WAL-safe, H11).
        Prefer this over shutil.copy2 of user.db (+ missing WAL).
        """
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        with _lock:
            # Ensure WAL frames are visible to backup API
            try:
                self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except sqlite3.Error:
                pass
            dst = sqlite3.connect(str(dest))
            try:
                self._conn.backup(dst)
                dst.commit()
            finally:
                dst.close()
        return dest

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

    def hot_trim_messages(self, max_messages: int) -> int:
        """Keep newest max_messages; delete oldest. Returns rows deleted."""
        if max_messages < 0:
            return 0
        n = self.hot_message_count()
        if n <= max_messages:
            return 0
        drop = n - max_messages
        with _lock:
            cur = self._conn.execute(
                "DELETE FROM hot_messages WHERE id IN ("
                "  SELECT id FROM hot_messages ORDER BY id ASC LIMIT ?"
                ")",
                (drop,),
            )
            deleted = int(cur.rowcount or 0)
        if deleted:
            self.kv_set("hot_updated_at", _utc_now_iso())
        return deleted

    def hot_trim_facts(self, max_facts: int) -> int:
        """Keep newest max_facts; delete oldest. Returns rows deleted."""
        if max_facts < 0:
            return 0
        n = self.hot_fact_count()
        if n <= max_facts:
            return 0
        drop = n - max_facts
        with _lock:
            cur = self._conn.execute(
                "DELETE FROM hot_facts WHERE id IN ("
                "  SELECT id FROM hot_facts ORDER BY id ASC LIMIT ?"
                ")",
                (drop,),
            )
            deleted = int(cur.rowcount or 0)
        if deleted:
            self.kv_set("hot_updated_at", _utc_now_iso())
        return deleted

    def maintain(self, *, vacuum: bool = False) -> dict[str, Any]:
        """Light maintenance: analyze + optional VACUUM. Safe to call after heavy clears."""
        info: dict[str, Any] = {"analyze": False, "vacuum": False, "page_count": 0, "freelist": 0}
        with _lock:
            self._conn.execute("PRAGMA optimize")
            self._conn.execute("ANALYZE")
            info["analyze"] = True
            page = self._conn.execute("PRAGMA page_count").fetchone()
            free = self._conn.execute("PRAGMA freelist_count").fetchone()
            info["page_count"] = int(page[0] if page else 0)
            info["freelist"] = int(free[0] if free else 0)
            # Auto-vacuum when freelist is large relative to DB
            if vacuum or (info["freelist"] >= 64 and info["freelist"] * 4 >= info["page_count"]):
                self._conn.execute("VACUUM")
                info["vacuum"] = True
                page = self._conn.execute("PRAGMA page_count").fetchone()
                free = self._conn.execute("PRAGMA freelist_count").fetchone()
                info["page_count"] = int(page[0] if page else 0)
                info["freelist"] = int(free[0] if free else 0)
        info["bytes"] = self.path.stat().st_size if self.path.is_file() else 0
        return info

    def snapshot_info(self) -> dict[str, Any]:
        bytes_ = self.path.stat().st_size if self.path.is_file() else 0
        return {
            "path": str(self.path),
            "warm_facts": self.warm_count(),
            "warm_flex": self.warm_count_source("flex"),
            "hot_messages": self.hot_message_count(),
            "hot_facts": self.hot_fact_count(),
            "bytes": bytes_,
            "migrated": self._meta_get("migrated_jsonl_v1") == "1",
        }
