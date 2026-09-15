"""Direct worker intake, rerun, tool short-circuits."""

from __future__ import annotations

from gnom_hub.pipeline.constants import PipelineCancelled
from gnom_hub.pipeline.helpers import (
    _format_turns,
    _prefetch_worker_tools,
    _quality_check,
    _worker_direct_too_big,
)
from gnom_hub.pipeline.models import PipelineStage, PipelineState


class WorkerMixin:
    def worker_intake(self, user_text: str, *, worker_id: str) -> PipelineState:
        text = (user_text or "").strip()
        if not text:
            self._fail("Empty user text")
            return self._state
        self._state.send_target = worker_id
        self._state.user_text = text
        user = self._record_user(text, worker_id)
        self._ensure_flex_job()
        if _worker_direct_too_big(text):
            self.flex_desk.ask(
                agent_id="flex",
                text=(
                    "Dieser Auftrag braucht Planung durch den Coordinator. "
                    "Soll er dorthin übergeben werden?"
                ),
                component="yes_no",
                options=["Ja, an Coordinator", "Nein"],
                entry_type="entscheidung",
            )
            self._sync_flex_state()
            self._record_reply(
                agent=worker_id,
                text=(f"{worker_id}: Auftrag ist zu groß. Rückfrage in Box 1 — keine Ausführung."),
                in_reply_to=user["message_id"],
                source="live",
            )
            self._set_stage(PipelineStage.clarify)
            return self._state
        # Assignment is send_target only. Worker does not talk in Box 2.
        self._set_stage(PipelineStage.brainstorm)
        return self._state

    def _try_tool_drill_short_circuit(self, text: str) -> bool:
        """Run forced multi-tool scenario (Playwright / shell / GUI)."""
        from gnom_hub.tools.tool_scenarios import (
            is_tool_drill_task,
            run_forced_tool_scenario,
        )

        if self.tools is None or not is_tool_drill_task(text):
            return False
        # Own this turn — do not keep previous browser/landing user_text
        self._state.user_text = text
        self._state.mode = "execute"
        self._state.error = None
        self._state.pending_question = None
        self._state.brainstorm_turns = [
            {"role": "user", "text": text},
            {
                "role": "brainstorm",
                "text": "Tool-Drill erkannt — echte Tools, kein HTML-Team.",
            },
        ]
        self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)
        self._set_stage(PipelineStage.work)
        forced = run_forced_tool_scenario(self.tools, text, bus=self.bus)
        summary = str(forced.get("summary") or forced)
        wid = "worker1"
        worker = self._workers.get(wid) or next(iter(self._workers.values()), None)
        wname = worker.state.name if worker is not None else wid
        out = {
            "worker": wid,
            "name": wname,
            "index": 1,
            "task": f"Tool drill: {text[:200]}",
            "result": summary,
        }
        self._state.worker_outputs = [out]
        self._state.worker_results = [summary]
        self._state.distilled_requirements = [
            f"Ziel: {text}",
            "Tool-Pflicht: Playwright / Shell / GUI wirklich aufrufen",
            f"Szenario: {forced.get('scenario')}",
        ]
        # Persist compact tool log for snapshot / desk strip
        tlog: list[dict] = []
        for s in forced.get("steps") or []:
            if not isinstance(s, dict):
                continue
            res = s.get("result") if isinstance(s.get("result"), dict) else {}
            tlog.append(
                {
                    "tool": str(s.get("tool") or "?"),
                    "ok": bool((res or {}).get("ok", True)),
                    "mode": str(s.get("mode") or (res or {}).get("mode") or ""),
                    "agent": "tool_scenario",
                    "scenario": str(forced.get("scenario") or ""),
                }
            )
        self._state.tool_log = tlog
        tools_used = forced.get("tools_used") or [e["tool"] for e in tlog]
        dry_n = sum(1 for e in tlog if e.get("mode") == "dry-run")
        self._state.quality_notes = (
            f"Tool-drill {forced.get('scenario')}: {forced.get('tool_calls')} tool calls"
            f" · {', '.join(str(t) for t in tools_used[:12])}"
            + (f" · {dry_n}× dry-run (God-Mode?)" if dry_n else "")
        )
        self._state.resolved_plan_mode = "tool_drill"
        self._state.plan_html_score = 0
        self.bus.emit(
            "pipeline.worker",
            {
                "worker": wid,
                "index": 1,
                "result": summary,
                "task": out["task"],
                "tool": "tool_scenario_run",
            },
        )
        self.bus.emit(
            "pipeline.quality",
            {"notes": self._state.quality_notes, "workers": 1},
        )
        self._finish()
        return True

    def _try_browser_nav_short_circuit(self, text: str) -> bool:
        """
        If the task is pure live-browser navigation, open the URL via tools
        and finish as done (no clarify / HTML workers).
        """
        from gnom_hub.tools.agent_bridge import try_browser_nav_execute

        if self.tools is None:
            return False
        nav = try_browser_nav_execute(tools=self.tools, user_text=text, bus=self.bus)
        if nav is None:
            return False
        self._state.user_text = text
        self._state.mode = "execute"
        self._state.error = None
        self._state.pending_question = None
        self._state.brainstorm_turns = [
            {"role": "user", "text": text},
            {
                "role": "brainstorm",
                "text": "Live-Browser-Auftrag erkannt — öffne die URL mit Tools.",
            },
        ]
        self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)
        self._set_stage(PipelineStage.work)
        summary = str(nav.get("summary") or "")
        wid = "worker1"
        worker = self._workers.get(wid) or next(iter(self._workers.values()), None)
        wname = worker.state.name if worker is not None else wid
        out = {
            "worker": wid,
            "name": wname,
            "index": 1,
            "task": f"Live browser: {text[:200]}",
            "result": summary,
        }
        self._state.worker_outputs = [out]
        self._state.worker_results = [summary]
        self._state.distilled_requirements = [
            f"Ziel: {text}",
            "Live-Browser-Navigation (tool: browser_open)",
            f"URL: {nav.get('url') or '?'}",
        ]
        mode = "live" if nav.get("ok") else "error"
        tr = nav.get("tool_result") if isinstance(nav.get("tool_result"), dict) else {}
        if tr.get("dry_run"):
            mode = "dry-run"
        self._state.tool_log = [
            {
                "tool": "browser_open",
                "ok": bool(nav.get("ok")),
                "mode": mode,
                "agent": "orchestrator",
                "scenario": "browser_nav",
            }
        ]
        self._state.quality_notes = (
            f"Browser-Nav short-circuit: browser_open · mode={mode}"
            if nav.get("ok")
            else f"Browser-Nav failed: {nav.get('error') or 'unknown'}"
        )
        self._state.resolved_plan_mode = "browser_tools"
        self._state.plan_html_score = 0
        self.bus.emit(
            "pipeline.worker",
            {
                "worker": wid,
                "index": 1,
                "result": summary,
                "task": out["task"],
                "tool": "browser_open",
            },
        )
        self.bus.emit(
            "pipeline.quality",
            {"notes": self._state.quality_notes, "workers": 1},
        )
        if not nav.get("ok"):
            self._state.warnings = list(self._state.warnings or []) + ["browser_open_failed"]
        self._finish()
        return True

    def rerun_worker(self, worker_id: str) -> PipelineState:
        wid = (worker_id or "").strip().lower()
        if wid not in self._workers:
            self._fail(f"Unknown worker: {worker_id}")
            return self._state
        worker = self._workers[wid]
        if not worker.enabled:
            self._fail(f"{wid} is disabled")
            return self._state

        task = ""
        index = 1
        for out in self._state.worker_outputs or []:
            if str(out.get("worker") or "") == wid:
                task = str(out.get("task") or "")
                index = int(out.get("index") or index)
                break
        if not task:
            task = (self._state.user_text or "").strip() or "Continue previous assignment"
        if not (self._state.user_text or "").strip() and not (self._state.worker_outputs or []):
            self._fail("Nothing to re-run — execute first")
            return self._state

        try:
            self._state.error = None
            self._state.mode = "execute"
            self._set_stage(PipelineStage.work)
            text = self._state.user_text or task
            mem = self._state.memory_context or self.memory.recall(text)
            self._state.memory_context = mem
            self._state.tool_calls = list(self._state.tool_calls or [])
            tool_ctx = _prefetch_worker_tools(
                f"{text}\n{task}",
                bus=self.bus,
                tools=getattr(self, "tools", None),
                memory=self.memory_store,
                record=self._state.tool_calls,
            )
            if tool_ctx:
                mem = (mem or "").rstrip() + "\n\nTool prefetch (auto):\n" + tool_ctx
                self.bus.emit(
                    "pipeline.web_fetch",
                    {"chars": len(tool_ctx), "via": "worker_prefetch"},
                )
            result = worker.run(
                task,
                text,
                list(self._state.distilled_requirements),
                mem,
            )
            outputs = list(self._state.worker_outputs or [])
            found = False
            for i, out in enumerate(outputs):
                if str(out.get("worker") or "") == wid:
                    outputs[i] = {
                        "worker": wid,
                        "name": worker.state.name,
                        "index": out.get("index") or index,
                        "task": task,
                        "result": result,
                    }
                    found = True
                    break
            if not found:
                outputs.append(
                    {
                        "worker": wid,
                        "name": worker.state.name,
                        "index": len(outputs) + 1,
                        "task": task,
                        "result": result,
                    }
                )
            self._state.worker_outputs = outputs
            self._state.worker_results = [str(o.get("result") or "") for o in outputs]
            self._state.quality_notes = _quality_check(
                self._state.user_text,
                self._state.distilled_requirements,
                outputs,
            )
            self.bus.emit(
                "pipeline.worker",
                {
                    "worker": wid,
                    "index": index,
                    "result": result,
                    "task": task,
                    "rerun": True,
                },
            )
            self.bus.emit(
                "pipeline.quality",
                {"notes": self._state.quality_notes, "workers": len(outputs)},
            )
            self._check_cancel()
            if getattr(self._state, "flex_wait_remaining", None):
                return self._state
            self._finish()
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state
