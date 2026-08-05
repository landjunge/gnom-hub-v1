"""COLD archive: immutable snapshots of HOT sessions + simple index."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gnom_hub.config.paths import project_root
from gnom_hub.memory.atomic import atomic_write_text


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class ColdArchive:
    """
    data/cold/
      index.jsonl
      sessions/<id>/session.json
      sessions/<id>/mermaid_canvas.mmd (optional)
      sessions/<id>/meta.json
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.cold_dir = self.root / "data" / "cold"
        self.sessions_dir = self.cold_dir / "sessions"
        self.index_path = self.cold_dir / "index.jsonl"
        self.cold_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def archive_hot(
        self,
        *,
        session: dict[str, Any],
        canvas_mmd: str = "",
        label: str = "",
    ) -> dict[str, Any]:
        sid = _utc_stamp()
        dest = self.sessions_dir / sid
        dest.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            dest / "session.json",
            json.dumps(session, ensure_ascii=False, indent=2) + "\n",
        )
        if canvas_mmd.strip():
            atomic_write_text(dest / "mermaid_canvas.mmd", canvas_mmd)
        meta = {
            "id": sid,
            "label": label or f"archive-{sid}",
            "messages": len(session.get("messages") or []),
            "facts": len(session.get("facts") or []),
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        atomic_write_text(dest / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        self._append_index(meta)
        return meta

    def list_archives(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.index_path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows[-limit:][::-1]

    def get(self, archive_id: str) -> dict[str, Any] | None:
        safe = Path(archive_id).name
        dest = self.sessions_dir / safe
        if not dest.is_dir():
            return None
        meta_p = dest / "meta.json"
        sess_p = dest / "session.json"
        meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.is_file() else {"id": safe}
        session = json.loads(sess_p.read_text(encoding="utf-8")) if sess_p.is_file() else {}
        canvas = ""
        canvas_p = dest / "mermaid_canvas.mmd"
        if canvas_p.is_file():
            canvas = canvas_p.read_text(encoding="utf-8")
        return {"meta": meta, "session": session, "canvas": canvas}

    def delete(self, archive_id: str) -> bool:
        safe = Path(archive_id).name
        dest = self.sessions_dir / safe
        if not dest.is_dir():
            return False
        shutil.rmtree(dest)
        # rewrite index without this id
        kept = [r for r in self.list_archives(10_000) if r.get("id") != safe]
        body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in reversed(kept))
        atomic_write_text(self.index_path, body)
        return True

    def _append_index(self, meta: dict[str, Any]) -> None:
        self.cold_dir.mkdir(parents=True, exist_ok=True)
        with self.index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
