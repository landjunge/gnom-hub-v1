"""WARM durable facts — backed by personal User/user.db."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.config.paths import project_root
from gnom_hub.db.sqlite_store import get_db


class WarmMemory:
    """
    Long-lived facts in User/user.db, survive HOT session reset.

    KISS: SQLite via GnomDatabase; de-dupe + garbage filter on write.
    """

    def __init__(self, root: Path | None = None, *, max_facts: int = 200) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.max_facts = max_facts
        self.db = get_db(self.root)
        # Compat paths (legacy tools / docs may still mention these)
        self.warm_dir = self.root / "data" / "warm"
        self.facts_path = self.warm_dir / "facts.jsonl"
        self.load()

    def load(self) -> None:
        """No-op load: SQLite is source of truth (migrated once on first open)."""
        self.db.warm_trim(self.max_facts)

    def save(self) -> None:
        """No-op: writes are immediate in SQLite."""
        self.db.warm_trim(self.max_facts)

    @staticmethod
    def _filter_facts(facts: list[str]) -> list[str]:
        from gnom_hub.agents.roles_helpers import _is_garbage_fact

        out: list[str] = []
        seen: set[str] = set()
        for f in facts:
            t = " ".join(str(f).split()).strip()
            if not t or _is_garbage_fact(t):
                continue
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out

    def add_fact(self, text: str) -> bool:
        t = " ".join(str(text).split()).strip()
        if not t:
            return False
        from gnom_hub.agents.roles_helpers import _is_garbage_fact

        if _is_garbage_fact(t):
            return False
        ok = self.db.warm_add(t, source="warm")
        if ok:
            self.db.warm_trim(self.max_facts)
            try:
                from gnom_hub.db.sqlite_store import sync_user_db_backup

                sync_user_db_backup(self.root)
            except Exception:  # noqa: BLE001
                pass
        return ok

    def recent_facts(self, limit: int = 12) -> list[str]:
        return self.db.warm_recent(limit)

    def all_facts(self) -> list[str]:
        return self.db.warm_all()

    def remove_fact(self, text: str) -> bool:
        t = " ".join(str(text).split()).strip()
        if not t:
            return False
        return self.db.warm_remove(t)

    def remove_at(self, index: int) -> str | None:
        return self.db.warm_remove_at(index)

    def clear(self) -> None:
        self.db.warm_clear()

    def pipeline_context(self, *, max_chars: int = 500) -> str:
        facts = self.recent_facts(8)
        if not facts:
            return ""
        lines = ["WARM facts (durable):"]
        for f in facts:
            lines.append(f"- {f[:120]}")
        text = "\n".join(lines)
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text
