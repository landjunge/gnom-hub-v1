"""COLD archive restore/delete (extracted from Hub)."""

from __future__ import annotations

from typing import Any

from gnom_hub.memory.atomic import atomic_write_text


class ColdOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def archive_cold(self, label: str = "") -> dict[str, Any]:
        meta = self.cold.archive_hot(
            session=dict(self.hot.session),
            canvas_mmd=self.hot.canvas.to_mermaid(),
            label=label,
        )
        return {"ok": True, "archive": meta}

    def restore_cold(
        self,
        archive_id: str,
        *,
        archive_current: bool = True,
    ) -> dict[str, Any]:
        """Restore a COLD archive into HOT (optionally archive current HOT first)."""
        data = self.cold.get(archive_id)
        if not data:
            raise FileNotFoundError(archive_id)
        archived = None
        if archive_current:
            sess = self.hot.session or {}
            if sess.get("messages") or sess.get("facts"):
                archived = self.archive_cold(label="pre-restore").get("archive")
        session = data.get("session") if isinstance(data.get("session"), dict) else {}
        self.hot.session = {
            "messages": list(session.get("messages") or []),
            "facts": list(session.get("facts") or []),
            "updated_at": session.get("updated_at") or "",
        }
        canvas = str(data.get("canvas") or "")
        if canvas.strip():
            self.hot.canvas_path.parent.mkdir(parents=True, exist_ok=True)
            nl = chr(10)
            if not canvas.endswith(nl):
                canvas = canvas + nl
            atomic_write_text(self.hot.canvas_path, canvas)
            self.hot.canvas.load(self.hot.canvas_path)
        else:
            self.hot.canvas.clear()
        self.hot.save()
        meta = data.get("meta") or {"id": archive_id}
        self._append_trace(
            "cold.restore",
            {"id": meta.get("id") or archive_id, "label": meta.get("label")},
        )
        snap = self.snapshot()
        snap["ok"] = True
        snap["restored"] = meta
        if archived:
            snap["archived_previous"] = archived
        return snap

    def delete_cold(self, archive_id: str) -> dict[str, Any]:
        ok = self.cold.delete(archive_id)
        if not ok:
            raise FileNotFoundError(archive_id)
        self._append_trace("cold.delete", {"id": archive_id})
        return {
            "ok": True,
            "deleted": archive_id,
            "archives": self.cold.list_archives()[:30],
        }
