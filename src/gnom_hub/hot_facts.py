"""HOT fact CRUD + promote to WARM (extracted from Hub)."""

from __future__ import annotations

from typing import Any


class HotFactsMixin:
    """Mixin extracted from Hub — pure move."""

    def add_hot_fact(self, text: str) -> dict[str, Any]:
        ok = self.hot.add_fact(text)
        if ok:
            self.hot.save()
        return {
            "ok": ok,
            "facts": self.hot.all_facts()[-30:],
            "hot_count": len(self.hot.all_facts()),
        }

    def delete_hot_fact(
        self, *, text: str | None = None, index: int | None = None
    ) -> dict[str, Any]:
        removed = None
        if index is not None:
            removed = self.hot.remove_fact_at(int(index))
            if removed is None:
                raise FileNotFoundError("index out of range")
        elif text and text.strip():
            ok = self.hot.remove_fact(text.strip())
            if not ok:
                raise FileNotFoundError("fact not found")
            removed = text.strip()
        else:
            raise ValueError("text or index required")
        self.hot.save()
        return {
            "ok": True,
            "removed": removed,
            "facts": self.hot.all_facts()[-30:],
            "hot_count": len(self.hot.all_facts()),
        }

    def clear_hot_facts(self) -> dict[str, Any]:
        n = self.hot.clear_facts()
        self.hot.save()
        return {"ok": True, "cleared": n, "facts": [], "hot_count": 0}

    def promote_hot_fact(self, text: str) -> dict[str, Any]:
        """Copy a HOT fact into WARM (durable)."""
        t = " ".join(str(text).split()).strip()
        if not t:
            raise ValueError("text required")
        facts = self.hot.all_facts()
        if t not in facts:
            # allow promote by index via caller resolving text
            raise FileNotFoundError("HOT fact not found")
        added = self.warm.add_fact(t)
        return {
            "ok": True,
            "promoted": t,
            "warm_added": added,
            "facts": self.hot.all_facts()[-30:],
            "warm_facts": self.warm.all_facts()[-30:],
        }
