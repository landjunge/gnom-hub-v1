"""Workspace zip + last-execute export + keep-to-personal-WS."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _extract_html_document(raw: str) -> str | None:
    """Pull a real HTML document from worker text (same spirit as UI)."""
    s = str(raw or "")
    fence = re.search(r"```html\s*([\s\S]*?)```", s, re.IGNORECASE)
    if fence and fence.group(1):
        body = fence.group(1).strip()
        if re.search(r"<!DOCTYPE\s+html|<html[\s>]", body, re.IGNORECASE):
            return body
    m = re.search(r"(<!DOCTYPE\s+html[\s\S]*?</html>)", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"(<html[\s\S]*?</html>)", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    t = s.strip()
    if t.startswith("<") and re.search(r"<!DOCTYPE\s+html|<html[\s>]", t, re.IGNORECASE):
        return t
    return None


class ExportOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def keep_result_to_personal_ws(
        self,
        content: str | None = None,
        *,
        name: str | None = None,
        worker: str | None = None,
    ) -> dict[str, Any]:
        """
        Copy ONE chosen HTML result into personal WS selected/.

        Hub temp may be cleared anytime; this is the durable copy for you.
        """
        raw = str(content or "").strip()
        if not raw and worker:
            for out in self.pipeline.state.worker_outputs or []:
                if not isinstance(out, dict):
                    continue
                if str(out.get("worker") or "") == worker or str(out.get("name") or "") == worker:
                    raw = str(out.get("result") or "").strip()
                    if not name:
                        name = f"{out.get('worker') or 'worker'}.html"
                    break
        if not raw:
            # fall back to first worker with HTML
            for out in self.pipeline.state.worker_outputs or []:
                if not isinstance(out, dict):
                    continue
                cand = _extract_html_document(str(out.get("result") or ""))
                if cand:
                    raw = cand
                    if not name:
                        name = f"{out.get('worker') or 'worker'}.html"
                    break
            if not raw:
                raise ValueError("no HTML result to keep")
        html = _extract_html_document(raw) or (
            raw if raw.lstrip().lower().startswith(("<!doctype", "<html", "<")) else None
        )
        if not html:
            raise ValueError("not HTML — only HTML is kept in personal WS selected/")
        fname = name or (f"{worker}.html" if worker else "page.html")
        path = self.workspace.keep_html_content(html, fname)
        self._append_trace(
            "workspace.keep",
            {"name": path.name, "bytes": path.stat().st_size, "path": str(path)},
        )
        return {
            "ok": True,
            "name": path.name,
            "path": str(path),
            "bytes": path.stat().st_size,
            "personal_ws": str(path.parent.parent),
            "selected_dir": str(path.parent),
            "workspace": self.workspace.snapshot(),
        }

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
