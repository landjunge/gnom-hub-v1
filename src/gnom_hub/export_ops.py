"""Workspace zip + last-execute export capture (extracted from Hub)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ExportOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def export_workspace_zip(self, zone: str = "all") -> dict[str, Any]:
        path = self.workspace.export_zip(zone)
        self._append_trace(
            "workspace.export",
            {"zone": zone, "name": path.name, "bytes": path.stat().st_size},
        )
        return {
            "ok": True,
            "name": path.name,
            "path": str(path),
            "bytes": path.stat().st_size,
            "zone": zone,
        }

    def workspace_export_path(self, name: str) -> Path:
        """Safe path under data/workspace/exports for download."""
        safe = Path(name).name
        if not safe.startswith("gnom-hub-workspace-") or not safe.endswith(".zip"):
            raise ValueError("invalid workspace export name")
        export_dir = (self.root / "data" / "workspace" / "exports").resolve()
        path = (export_dir / safe).resolve()
        if not str(path).startswith(str(export_dir)) or not path.is_file():
            raise FileNotFoundError(safe)
        return path

    def _remember_execute_export(self) -> None:
        """Pin last successful Execute so export survives reset / new chat."""
        from datetime import datetime, timezone

        st = self.pipeline.state
        if st.stage.value != "done":
            return
        if not (st.worker_outputs or st.brainstorm_notes):
            return
        self._last_execute_export = {
            "stage": st.stage.value,
            "user_text": st.user_text or "",
            "brainstorm_notes": st.brainstorm_notes or "",
            "distilled_requirements": list(st.distilled_requirements or []),
            "flex_notes": st.flex_notes or "",
            "quality_notes": st.quality_notes or "",
            "worker_outputs": list(st.worker_outputs or []),
            "saved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }

    def build_export_last(self) -> dict[str, Any]:
        """Markdown export: live pipeline if it has workers, else pinned Execute."""
        st = self.pipeline.state
        pinned = getattr(self, "_last_execute_export", None)
        use_live = bool(st.worker_outputs) or (
            st.stage.value == "done" and (st.brainstorm_notes or "").strip()
        )
        if use_live:
            src = {
                "stage": st.stage.value,
                "user_text": st.user_text or "",
                "brainstorm_notes": st.brainstorm_notes or "",
                "distilled_requirements": list(st.distilled_requirements or []),
                "flex_notes": st.flex_notes or "",
                "quality_notes": st.quality_notes or "",
                "worker_outputs": list(st.worker_outputs or []),
                "source": "live",
            }
        elif isinstance(pinned, dict) and (
            pinned.get("worker_outputs") or pinned.get("brainstorm_notes")
        ):
            src = dict(pinned)
            src["source"] = "pinned"
        else:
            src = {
                "stage": st.stage.value,
                "user_text": st.user_text or "",
                "brainstorm_notes": st.brainstorm_notes or "",
                "distilled_requirements": list(st.distilled_requirements or []),
                "flex_notes": st.flex_notes or "",
                "quality_notes": st.quality_notes or "",
                "worker_outputs": list(st.worker_outputs or []),
                "source": "empty",
            }
        parts = [
            "# Gnom-Hub export",
            f"stage={src.get('stage')}",
            f"user={src.get('user_text')}",
            f"source={src.get('source')}",
            "",
            "## Brainstorm",
            str(src.get("brainstorm_notes") or "(none)"),
            "",
            "## Requirements",
            "\n".join(f"- {r}" for r in (src.get("distilled_requirements") or [])) or "(none)",
            "",
            "## Flex",
            str(src.get("flex_notes") or "(none)"),
            "",
            "## Quality",
            str(src.get("quality_notes") or "(none)"),
            "",
        ]
        for out in src.get("worker_outputs") or []:
            if not isinstance(out, dict):
                continue
            parts.append(f"## {out.get('name') or out.get('worker')}")
            parts.append(f"Task: {out.get('task') or ''}")
            parts.append(str(out.get("result") or ""))
            parts.append("")
        text = "\n".join(parts)
        return {
            "ok": True,
            "filename": "gnom-hub-export.md",
            "content": text,
            "chars": len(text),
            "source": src.get("source"),
            "saved_at": src.get("saved_at"),
        }

    def _capture_workspace_outputs(self) -> None:
        """Write worker results into temp workspace (plan: dual workspace)."""
        st = self.pipeline.state
        for out in st.worker_outputs or []:
            wid = str(out.get("worker") or "worker")
            body = str(out.get("result") or "").strip()
            if not body:
                continue
            # Prefer .html when content looks like HTML
            low = body.lower()
            ext = ".html" if ("<!doctype" in low or "<html" in low) else ".txt"
            name = f"{wid}_{st.stage.value}{ext}"
            try:
                self.workspace.write_text("temp", name, body)
            except Exception as exc:  # noqa: BLE001
                self._append_trace("workspace.write_error", {"name": name, "error": str(exc)})
        if st.brainstorm_notes:
            try:
                self.workspace.write_text(
                    "temp",
                    "brainstorm_latest.txt",
                    st.brainstorm_notes[:8000],
                )
            except Exception as exc:  # noqa: BLE001
                self._append_trace(
                    "workspace.write_error",
                    {"name": "brainstorm_latest.txt", "error": str(exc)},
                )
