"""Finish, memory notes, quality close-out."""

from __future__ import annotations

from gnom_hub.pipeline.models import PipelineStage


class PersistMixin:
    def _append_prefetch_why_notes(self) -> None:
        try:
            whys: list[str] = []
            seen_w: set[str] = set()
            for tc in self._state.tool_calls or []:
                if not isinstance(tc, dict):
                    continue
                r = str(tc.get("reason") or "").strip()
                if not r or r in seen_w:
                    continue
                seen_w.add(r)
                name = str(tc.get("name") or tc.get("tool") or "?")
                whys.append(f"{name}: {r}")
            if not whys:
                return
            line = "Prefetch why: " + "; ".join(whys[:8])
            qn = (self._state.quality_notes or "").strip()
            if line not in qn:
                self._state.quality_notes = (qn + "\n" + line).strip() if qn else line
        except Exception:  # noqa: BLE001
            pass

    def _finish(self) -> None:
        # Last chance: never store memory / mark done after soft-cancel (H7)
        self._check_cancel()
        self._close_stage_timing()
        self.memory.store(
            user_text=self._state.user_text,
            requirements=list(self._state.distilled_requirements),
            brainstorm=self._state.brainstorm_notes,
            flex_notes=self._state.flex_notes,
            results=list(self._state.worker_results),
        )
        self._state.error = None
        outputs = list(self._state.worker_outputs or [])
        any_ok = any(
            isinstance(o, dict) and (o.get("validation") or {}).get("ok") is True for o in outputs
        )
        if self._state.worker_results and any_ok:
            self._state.result_status = "GELIEFERT"
        elif self._state.worker_results:
            self._state.result_status = "UNGEPRÜFT"
        else:
            self._state.result_status = "FEHLER"
        self._set_stage(PipelineStage.done)
        total_ms = round(sum(self._state.stage_timings.values()), 1)
        self.bus.emit(
            "pipeline.done",
            {
                "requirements": list(self._state.distilled_requirements),
                "results": list(self._state.worker_results),
                "flex_notes": self._state.flex_notes,
                "quality_notes": self._state.quality_notes,
                "stage_timings": dict(self._state.stage_timings),
                "total_ms": total_ms,
                "plan_mode": self._state.resolved_plan_mode
                or getattr(self, "plan_mode", "default"),
                "html_score": getattr(self._state, "plan_html_score", None),
            },
        )
        self.bus.emit(
            "pipeline.timings",
            {
                "stages": dict(self._state.stage_timings),
                "total_ms": total_ms,
                "plan_mode": self._state.resolved_plan_mode
                or getattr(self, "plan_mode", "default"),
                "html_score": getattr(self._state, "plan_html_score", None),
            },
        )
