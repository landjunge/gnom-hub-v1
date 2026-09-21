"""Finish, memory notes, quality close-out."""

from __future__ import annotations

from gnom_hub.memory.secrets import filter_secrets, looks_like_secret
from gnom_hub.pipeline.models import PipelineStage
from gnom_hub.snapshot_ops import _body_is_error, _deliverable_ok, _wants_html
from gnom_hub.threaddesk_ops import write_handoff


class PersistMixin:
    def _offer_memory_keep(self, facts: list[str]) -> None:
        """Box 1: Behalten writes WARM. Verwerfen does not. Never Execute."""
        clean = filter_secrets([f for f in facts if str(f).strip()])[:3]
        if not clean:
            self._state.memory_proposals = []
            return
        self._state.memory_proposals = clean
        self._ensure_flex_job()
        bullets = "\n".join(f"• {f}" for f in clean)
        text = (
            f"Memory schlägt vor, das dauerhaft zu behalten:\n{bullets}\nSoll genau das nach WARM?"
        )
        self.flex_desk.ask(
            agent_id="memory",
            text=text,
            component="memory_keep",
            options=["Behalten", "Verwerfen"],
            assignment_id="MEM1",
            entry_type="freigabe",
            task_id="memory_keep",
        )
        self._sync_flex_state()
        self.bus.emit("pipeline.memory_propose", {"facts": clean})

    def apply_memory_keep(self, keep: bool) -> None:
        facts = list(self._state.memory_proposals or [])
        self._state.memory_proposals = []
        if not keep:
            self.bus.emit("pipeline.memory_rejected", {"facts": facts})
            self._sync_flex_state()
            return
        store = self.memory_store
        warm = getattr(store, "warm", None)
        hot = getattr(store, "hot", None)
        vectors = getattr(store, "vectors", None)
        kept: list[str] = []
        for fact in facts:
            if looks_like_secret(fact):
                continue
            if warm is not None:
                warm.add_fact(fact)
            if hot is not None:
                hot.add_fact(fact)
            if vectors is not None:
                vectors.add(fact, meta={"source": "memory_keep"})
            kept.append(fact)
        if hot is not None and hasattr(hot, "save"):
            hot.save()
        self.bus.emit("pipeline.memory_kept", {"facts": kept})
        self._sync_flex_state()
        if kept:
            self._offer_td_handoff(kept)

    def _offer_td_handoff(self, facts: list[str]) -> None:
        """Box 1: Übergeben writes handoff.json. Never a TD database, never Execute."""
        clean = filter_secrets(facts)[:3]
        if not clean:
            self._state.td_handoff_facts = []
            return
        self._state.td_handoff_facts = clean
        self._ensure_flex_job()
        bullets = "\n".join(f"• {f}" for f in clean)
        text = (
            "An ThreadDesk übergeben?\n"
            f"{bullets}\n"
            "Nur ein Paket (handoff.json). ThreadDesk startet keine Arbeit."
        )
        self.flex_desk.ask(
            agent_id="memory",
            text=text,
            component="td_handoff",
            options=["Übergeben", "Nicht übergeben"],
            assignment_id="TD1",
            entry_type="freigabe",
            task_id="td_handoff",
        )
        self._sync_flex_state()
        self.bus.emit("pipeline.td_handoff_offer", {"facts": clean})

    def _offer_td_replace(self, existing_title: str) -> None:
        self._ensure_flex_job()
        title = (existing_title or "bestehendes Paket").strip() or "bestehendes Paket"
        text = (
            f"ThreadDesk hat schon ein Paket ({title}). "
            "Ersetzen oder bestehendes behalten? Kein stilles Überschreiben."
        )
        self.flex_desk.ask(
            agent_id="memory",
            text=text,
            component="td_replace",
            options=["Ersetzen", "Bestehendes behalten"],
            assignment_id="TD2",
            entry_type="freigabe",
            task_id="td_replace",
        )
        self._sync_flex_state()
        self.bus.emit("pipeline.td_handoff_conflict", {"existing_title": title})

    def apply_td_handoff(self, accept: bool, *, overwrite: bool = False) -> dict:
        facts = list(self._state.td_handoff_facts or [])
        if not accept:
            self._state.td_handoff_facts = []
            self.bus.emit("pipeline.td_handoff_rejected", {"facts": facts})
            self._sync_flex_state()
            return {"ok": True, "wrote": False, "ran": False}
        run_id = str(getattr(self._state, "flex_job_id", "") or "")
        out = write_handoff(facts, run_id=run_id, overwrite=overwrite)
        if not out.get("ok") and out.get("error") == "conflict":
            self._offer_td_replace(str(out.get("existing_title") or ""))
            return out
        if out.get("ok"):
            self._state.td_handoff_facts = []
            self.bus.emit("pipeline.td_handoff_written", {"path": out.get("path"), "ran": False})
        self._sync_flex_state()
        return out

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

    def _html_bodies(self) -> list[str]:
        bodies: list[str] = []
        for o in self._state.worker_outputs or []:
            if isinstance(o, dict):
                bodies.append(str(o.get("result") or o.get("body") or ""))
        if not bodies:
            bodies = [str(x) for x in (self._state.worker_results or [])]
        return bodies

    def _apply_delivery_status(self) -> None:
        """GELIEFERT only for a complete, browser-checked page when HTML is required."""
        from gnom_hub.pipeline.html_browser_check import (
            all_browser_skipped,
            any_browser_ok,
            attach_browser_checks,
            note_incomplete_page,
        )

        outputs = list(self._state.worker_outputs or [])
        any_ok = any(
            isinstance(o, dict) and (o.get("validation") or {}).get("ok") is True for o in outputs
        )
        wants = _wants_html(self._state)
        if wants:
            attach_browser_checks(self._state)
        ok_deliv = bool(_deliverable_ok(self._state))
        bodies = self._html_bodies()
        provider_fail = bool(bodies) and all(
            _body_is_error(b) or not (b or "").strip() for b in bodies
        )
        self._state.error = None
        if wants and not ok_deliv:
            if provider_fail or not any((b or "").strip() for b in bodies):
                self._state.result_status = "FEHLER"
            else:
                self._state.result_status = "NACHBESSERUNG"
                note_incomplete_page(self._state)
            return
        if wants and ok_deliv and any_ok and any_browser_ok(self._state):
            self._state.result_status = "GELIEFERT"
            return
        if (
            wants
            and ok_deliv
            and not any_browser_ok(self._state)
            and not all_browser_skipped(self._state)
        ):
            # Playwright ran and rejected the page.
            self._state.result_status = "NACHBESSERUNG"
            note_incomplete_page(self._state)
            return
        if ok_deliv and any_ok and not wants:
            self._state.result_status = "GELIEFERT"
            return
        if ok_deliv:
            self._state.result_status = "UNGEPRÜFT"
            return
        self._state.result_status = "FEHLER"

    def _finish(self) -> None:
        # Last chance: never store memory / mark done after soft-cancel (H7)
        self._check_cancel()
        self._close_stage_timing()
        facts = self.memory.store(
            user_text=self._state.user_text,
            requirements=list(self._state.distilled_requirements),
            brainstorm=self._state.brainstorm_notes,
            flex_notes=self._state.flex_notes,
            results=list(self._state.worker_results),
        )
        self._offer_memory_keep(list(facts or []))
        # Stage stays done (pipeline finished). Honesty lives in result_status.
        self._apply_delivery_status()
        # Key-missing still asked. "Passt das?" only after a real deliverable.
        self._offer_judgment()
        try:
            from gnom_hub.authority_emit import emit as _auth_emit

            _auth_emit(
                "work.finished",
                actor="coordinator",
                action="execute",
                resource="pipeline:execute",
                result_ref=str(self._state.result_status or ""),
                decision="ALLOW" if self._state.result_status == "GELIEFERT" else None,
            )
        except Exception:  # noqa: BLE001
            pass
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
