"""start/execute and worker fan-out."""

from __future__ import annotations

from gnom_hub.flex_desk import parse_flex_ask
from gnom_hub.pipeline.constants import PipelineCancelled
from gnom_hub.pipeline.helpers import (
    _definition_of_done,
    _format_turns,
    _pick_execute_task,
    _prefetch_worker_tools,
    _quality_check,
    _validate_worker_draft,
)
from gnom_hub.pipeline.models import PipelineStage, PipelineState


class DispatchMixin:
    def _worker_ids_for_plan(self) -> list[str]:
        """Flag (send_target) is the assigned worker. HTML/default no longer always Worker 1."""
        pref = str(getattr(self._state, "send_target", "") or "").strip().lower()
        if pref in self._workers:
            agents = getattr(self, "agents", None) or getattr(self, "_agents", None)
            if agents is not None:
                try:
                    ag = agents.get(pref)
                    if not ag.enabled:
                        agents.toggle(pref)
                except (KeyError, ValueError, AttributeError):
                    pass
            else:
                st = getattr(self._workers[pref], "state", None)
                if st is not None and not getattr(st, "enabled", True):
                    st.enabled = True
        ids = [wid for wid, w in self._workers.items() if w.enabled]
        if pref in ids:
            return [pref] + [w for w in ids if w != pref]
        return ids

    def _offer_start_work(self, *, reason: str, workers: str = "") -> None:
        """Legacy no-op. Start is the Arbeit-starten button, never Box 1."""
        del reason, workers

    def _offer_judgment(self) -> None:
        """Box 1: key-missing first. Passt das? only after a real deliverable."""
        from gnom_hub.snapshot_ops import _deliverable_ok

        self._ensure_flex_job()
        if self._results_missing_key():
            self.flex_desk.ask(
                agent_id="flex",
                job_id=self.flex_desk.job_id,
                task_id="key_missing",
                component="yes_no",
                text=(
                    "Key fehlt. In System einen echten Schlüssel eintragen, dann Arbeit starten."
                ),
                options=["Verstanden"],
                entry_type="blockiert",
            )
        elif _deliverable_ok(self._state):
            self.flex_desk.offer_judgment()
        else:
            return
        self._sync_flex_state()
        vis = self.flex_desk.visible_question()
        self.bus.emit(
            "pipeline.flex_ask",
            {
                "reason": "judgment",
                "question_id": vis.question_id if vis is not None else None,
                "component": vis.component if vis is not None else "judgment",
            },
        )

    def _results_missing_key(self) -> bool:
        marks = (
            "kein deliverable",
            "llm/key",
            "deepseek_api_key",
            "kein nutzbarer llm",
        )
        blobs: list[str] = []
        for r in list(self._state.worker_results or []):
            blobs.append(str(r or "").lower())
        if not blobs:
            return False
        hits = sum(1 for b in blobs if any(m in b for m in marks))
        return hits >= max(1, (len(blobs) + 1) // 2)

    def start(self, user_text: str) -> PipelineState:
        text = user_text.strip()
        self._state = PipelineState(user_text=text, mode="full")
        self._clarified_once = False
        try:
            if not text:
                self._fail("Empty user text")
                return self._state

            self._stage_t0 = None
            self._stage_name = None
            self._check_cancel()
            # Live browser nav (full pipeline entry): tools first, skip HTML path
            if self._try_browser_nav_short_circuit(text):
                return self._state

            self._begin_stage_timing("memory")
            self.bus.emit("pipeline.stage", {"stage": "memory"})
            mem = self.memory.recall(text)
            self._state.memory_context = mem
            if mem:
                self.bus.emit("pipeline.memory_context", {"context": mem})
            self._close_stage_timing()

            self._check_cancel()
            if self.brainstorm.enabled:
                self._set_stage(PipelineStage.brainstorm)
                notes = self.brainstorm.run(text, mem, history=[])
                self._state.brainstorm_notes = notes
                self._state.brainstorm_turns = [
                    {"role": "user", "text": text},
                    {"role": "brainstorm", "text": notes},
                ]
                self.bus.emit("pipeline.brainstorm", {"notes": notes, "mode": "full"})

            self._check_cancel()
            self._set_stage(PipelineStage.distill)
            reqs, question = self.coordinator.distill(
                text,
                self._state.brainstorm_notes,
                mem,
                confirmed=bool(getattr(self._state, "confirmed_choices", None)),
            )
            self._state.distilled_requirements = reqs
            self.bus.emit("pipeline.distill", {"requirements": list(reqs)})

            self._check_cancel()
            if question is not None and not self._clarified_once:
                self._post_coordinator_clarify(question)
                return self._state

            self._check_cancel()
            self._run_flex_coord_workers()
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def execute(self) -> PipelineState:
        try:
            # #btn-execute consumes Box 1 start_work so a later Ja cannot Execute again.
            for q in self.flex_desk.open_questions():
                if q.component == "start_work":
                    q.status = "stale"
            self._sync_flex_state()
            text = (self._state.user_text or "").strip()
            if self._state.brainstorm_turns:
                text = _pick_execute_task(self._state.brainstorm_turns, fallback=text)
                self._state.user_text = text
            if not text:
                self._fail("Nothing to execute — brainstorm first")
                return self._state
            try:
                from gnom_hub.authority_emit import emit as _auth_emit

                _auth_emit(
                    "work.started",
                    actor="coordinator",
                    action="execute",
                    resource="pipeline:execute",
                )
            except Exception:  # noqa: BLE001
                pass

            notes = self._state.brainstorm_notes or _format_turns(self._state.brainstorm_turns)
            self._state.brainstorm_notes = notes
            self._state.mode = "execute"
            self._clarified_once = False
            self._state.error = None
            self._state.worker_results = []
            self._state.worker_outputs = []
            self._state.quality_notes = ""
            self._state.pending_question = None
            self._state.stage_timings = {}
            self._state.resolved_plan_mode = ""
            self._state.plan_html_score = None
            self._stage_t0 = None
            self._stage_name = None

            # Tool drill before pure browser (S7 mentions kleinanzeigen + screenshot)
            if self._try_tool_drill_short_circuit(text):
                return self._state
            # Live browser navigation: call tools now, skip HTML workers
            if self._try_browser_nav_short_circuit(text):
                return self._state

            self._begin_stage_timing("memory")
            mem = self._state.memory_context or self.memory.recall(text)
            self._state.memory_context = mem
            self._close_stage_timing()

            self._check_cancel()
            self._set_stage(PipelineStage.distill)
            reqs, question = self.coordinator.distill(
                text,
                notes,
                mem,
                confirmed=bool(getattr(self._state, "confirmed_choices", None)),
            )
            self._state.distilled_requirements = reqs
            self.bus.emit("pipeline.distill", {"requirements": list(reqs)})

            self._check_cancel()
            if question is not None and not self._clarified_once:
                self._post_coordinator_clarify(question)
                return self._state

            self._run_flex_coord_workers()
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def _run_flex_coord_workers(self) -> None:
        text = self._state.user_text
        mem = self._state.memory_context

        self._check_cancel()
        if self.flex.enabled:
            self._set_stage(PipelineStage.flex)
            from gnom_hub.memory.dedupe import already_covered
            from gnom_hub.pipeline.choices import is_binding_standing_rule

            for wish in self.flex.binding_wishes(mem or ""):
                if not is_binding_standing_rule(wish):
                    continue
                tag = f"Flex-wish: {wish}"
                if already_covered(tag, self._state.distilled_requirements, strategy="requirement"):
                    continue
                self._state.distilled_requirements.append(tag)
            self._state.flex_notes = ""
            self.bus.emit(
                "pipeline.flex",
                {
                    "notes": "",
                    "preset": "personal",
                    "skipped_llm": True,
                    "wishes": [
                        w
                        for w in self.flex.binding_wishes(mem or "")
                        if is_binding_standing_rule(w)
                    ],
                },
            )

        self._check_cancel()
        if not self.coordinator.enabled:
            self.bus.emit(
                "pipeline.coordinate",
                {"tasks": [], "skipped": True, "reason": "coordinator disabled"},
            )
            self._state.worker_results = []
            self._state.worker_outputs = []
            # Intentional skip path (tests): finish with explicit quality note (M8)
            self._state.quality_notes = (
                self._state.quality_notes or ""
            ).strip() or "Coordinator disabled — no workers ran."
            self._state.warnings = [*(self._state.warnings or []), "coordinator_disabled_skip"]
            self._finish()
            return

        self._set_stage(PipelineStage.coordinate)
        worker_ids = self._worker_ids_for_plan()
        tasks = self.coordinator.plan(
            text,
            self._state.distilled_requirements,
            worker_ids,
            plan_mode=getattr(self, "plan_mode", "default") or "default",
        )
        meta = getattr(self.coordinator, "last_plan_meta", None) or {}
        resolved = str(meta.get("plan_mode") or getattr(self, "plan_mode", "default") or "default")
        self._state.resolved_plan_mode = resolved
        html_score = meta.get("html_score")
        if html_score is not None:
            self._state.plan_html_score = int(html_score)
        self.bus.emit(
            "pipeline.coordinate",
            {
                "tasks": [{"worker": w, "task": t} for w, t in tasks],
                "plan_mode": resolved,
                "fast_path": bool(meta.get("fast_path")),
                "requested_mode": meta.get("requested_mode")
                or getattr(self, "plan_mode", "default"),
                "html_score": html_score,
            },
        )

        # All workers off or empty plan with no workers → soft success + note (tests)
        if not worker_ids:
            self._state.worker_results = []
            self._state.worker_outputs = []
            self._state.quality_notes = "No workers enabled — nothing to execute."
            self._state.warnings = [*(self._state.warnings or []), "no_workers_enabled"]
            self._finish()
            return

        # Coordinator returned no tasks despite enabled workers (M8)
        if not tasks:
            self._state.worker_results = []
            self._state.worker_outputs = []
            self._fail("Coordinator produced no worker tasks")
            return

        self._check_cancel()
        self._set_stage(PipelineStage.work)
        results: list[str] = []
        outputs: list[dict] = []
        # H4: clear then publish incrementally so cancel keeps partials
        self._state.worker_results = []
        self._state.worker_outputs = []
        pre_blob = f"{text}\n" + "\n".join(t for _, t in tasks)
        self._state.tool_calls = []
        tool_ctx = _prefetch_worker_tools(
            pre_blob,
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
        dod = _definition_of_done(text, self._state.distilled_requirements)
        for i, (wid, task) in enumerate(tasks, start=1):
            try:
                from gnom_hub.authority_emit import emit as _auth_emit

                _auth_emit(
                    "agent.invoked",
                    actor=str(wid),
                    action="work",
                    resource=f"worker:{wid}",
                )
            except Exception:  # noqa: BLE001
                pass
            self._check_cancel()
            worker = self._workers.get(wid)
            if worker is None or not worker.enabled:
                continue
            self._begin_stage_timing(wid)
            self.bus.emit("pipeline.stage", {"stage": wid})
            task_full = f"{task}\n\n{dod}".strip()
            result = worker.run(
                task_full,
                text,
                self._state.distilled_requirements,
                mem,
            )
            asked = parse_flex_ask(result)
            if asked:
                rest = [{"worker": w, "task": t} for w, t in tasks[i - 1 :]]
                self._pause_worker_flex_ask(wid, task, asked, rest)
                self.bus.emit(
                    "pipeline.flex_ask",
                    {"agent_id": wid, "task_id": asked["task_id"]},
                )
                return
            retries = 0
            max_retries = 2
            from gnom_hub.pipeline.dod_gate import format_retry_hint, should_retry

            while retries < max_retries:
                gate0 = _validate_worker_draft(
                    result,
                    user_text=text,
                    task=task,
                    requirements=self._state.distilled_requirements,
                    tool_calls=self._state.tool_calls,
                )
                # Auth / missing key: do not burn retries on the same dead key
                if "worker_error" in (gate0.get("issues") or []) or (
                    "FEHLER" in (result or "") and "Deliverable" in (result or "")
                ):
                    break
                need_retry, retry_why = should_retry(gate0, user_text=text, task=task)
                # Cap soft palette retry to a single attempt
                if retry_why == "prefetch_palette" and retries >= 1:
                    need_retry = False
                if not need_retry:
                    break
                retries += 1
                self.bus.emit(
                    "pipeline.quality_retry",
                    {
                        "worker": wid,
                        "reason": retry_why,
                        "attempt": retries,
                        "issues": gate0.get("issues") or [],
                        "score": gate0.get("score"),
                    },
                )
                self.bus.emit(
                    "pipeline.dod_gate",
                    {
                        "worker": wid,
                        "phase": "retry",
                        "attempt": retries,
                        "ok": gate0.get("ok"),
                        "issues": gate0.get("issues") or [],
                        "score": gate0.get("score"),
                    },
                )
                self._check_cancel()
                hint = format_retry_hint(gate0, attempt=retries)
                result = worker.run(
                    task_full + "\n\n" + hint,
                    text,
                    self._state.distilled_requirements,
                    mem,
                )
            gate = _validate_worker_draft(
                result,
                user_text=text,
                task=task,
                requirements=self._state.distilled_requirements,
                tool_calls=self._state.tool_calls,
            )
            self.bus.emit(
                "pipeline.dod_gate",
                {
                    "worker": wid,
                    "phase": "final",
                    "ok": gate.get("ok"),
                    "issues": gate.get("issues") or [],
                    "score": gate.get("score"),
                    "retryable": gate.get("retryable"),
                    "retries": retries,
                },
            )
            if retries:
                gate = dict(gate)
                gate["retries"] = retries
            results.append(result)
            outputs.append(
                {
                    "worker": wid,
                    "name": worker.state.name,
                    "index": i,
                    "task": task_full,
                    "result": result,
                    "validation": gate,
                }
            )
            # H4: publish partials after each worker (cancel keeps what ran)
            self._state.worker_results = list(results)
            self._state.worker_outputs = list(outputs)
            self.bus.emit(
                "pipeline.worker",
                {
                    "worker": wid,
                    "index": i,
                    "result": result,
                    "task": task,
                    "validation": gate,
                },
            )
        self._check_cancel()
        # M8: planned tasks but nothing ran (workers vanished mid-plan)
        if tasks and not outputs:
            self._fail("Planned worker tasks produced no output")
            return
        self._state.worker_results = results
        self._state.worker_outputs = outputs
        self._state.quality_notes = _quality_check(
            self._state.user_text,
            self._state.distilled_requirements,
            outputs,
        )
        # Empty body results: still done but warn (M8 soft)
        if outputs and all(not str(o.get("result") or "").strip() for o in outputs):
            warn = "All worker results were empty."
            self._state.quality_notes = ((self._state.quality_notes or "") + "\n" + warn).strip()
            self._state.warnings = [*(self._state.warnings or []), "empty_worker_results"]
        self._append_prefetch_why_notes()
        self.bus.emit(
            "pipeline.quality",
            {"notes": self._state.quality_notes, "workers": len(outputs)},
        )
        self._check_cancel()
        self._flex_nudge_and_fix(text, mem, dod)
        self._check_cancel()
        self._offer_nudge_questions()
        self._finish()
