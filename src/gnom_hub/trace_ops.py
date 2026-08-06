"""Light pipeline trace ring buffer (extracted from Hub)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class TraceOpsMixin:
    """Mixin extracted from Hub — pure move."""

    def _wire_trace(self) -> None:
        """Subscribe to pipeline events for light tracing (no heavy spans)."""

        def make_handler(event: str) -> Any:
            def _h(data: Any) -> None:
                self._append_trace(event, data)

            return _h

        for ev in (
            "pipeline.stage",
            "pipeline.brainstorm",
            "pipeline.distill",
            "pipeline.flex",
            "pipeline.coordinate",
            "pipeline.worker",
            "pipeline.quality",
            "pipeline.done",
            "pipeline.error",
            "pipeline.question",
            "pipeline.warning",
            "pipeline.brainstorm_ready",
        ):
            self.bus.on(ev, make_handler(ev))

    def _append_trace(self, event: str, data: Any) -> None:

        summary: Any = data
        if isinstance(data, dict):
            summary = {}
            for k, v in list(data.items())[:12]:
                if isinstance(v, str) and len(v) > 160:
                    summary[k] = v[:160] + "…"
                elif isinstance(v, list) and len(v) > 6:
                    summary[k] = f"[{len(v)} items]"
                else:
                    summary[k] = v
        self.trace.append(
            {
                "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "event": event,
                "data": summary,
            }
        )
        if len(self.trace) > 100:
            self.trace = self.trace[-100:]

    def clear_trace(self) -> dict[str, Any]:
        n = len(self.trace)
        self.trace = []
        return {"ok": True, "cleared": n, "count": 0, "trace": []}

    def export_trace(
        self,
        *,
        limit: int = 100,
        fmt: str = "json",
    ) -> dict[str, Any]:
        """Export light trace as JSON or Markdown (download helper)."""

        lim = max(1, min(100, int(limit)))
        events = list(self.trace[-lim:])
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fmt_l = (fmt or "json").strip().lower()
        if fmt_l in ("md", "markdown"):
            lines = [
                "# Gnom-Hub light trace",
                f"exported_at: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
                f"events: {len(events)}",
                "",
            ]
            for e in events:
                d = e.get("data")
                extra = ""
                if isinstance(d, dict):
                    bits = []
                    for k in ("stage", "worker", "error", "label", "id", "name"):
                        if d.get(k) is not None:
                            bits.append(f"{k}={d.get(k)}")
                    if not bits and d:
                        bits.append(str(list(d.keys())[:6]))
                    extra = " ".join(str(b) for b in bits)
                elif d is not None:
                    extra = str(d)[:120]
                lines.append(f"- `{e.get('ts') or ''}` **{e.get('event') or ''}** {extra}".rstrip())
            body = chr(10).join(lines) + chr(10)
            filename = f"gnom-hub-trace-{stamp}.md"
            return {
                "ok": True,
                "format": "markdown",
                "filename": filename,
                "content": body,
                "count": len(events),
            }
        import json as _json

        body = _json.dumps(
            {
                "format": "gnom-hub-trace",
                "format_version": 1,
                "app_version": "3.7.1",
                "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "count": len(events),
                "trace": events,
            },
            ensure_ascii=False,
            indent=2,
        ) + chr(10)
        filename = f"gnom-hub-trace-{stamp}.json"
        return {
            "ok": True,
            "format": "json",
            "filename": filename,
            "content": body,
            "count": len(events),
        }
