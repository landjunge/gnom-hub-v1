"""
V1 Orchestrator — real agent roles.

Default UX: brainstorm_turn (dialogue only).
Explicit execute: distill → flex → coordinator → workers → memory.
start() still runs full pipeline (tests / Telegram /do).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from gnom_hub.agents.manager import AgentManager
from gnom_hub.agents.models import AgentId
from gnom_hub.agents.roles import (
    BrainstormAgent,
    CoordinatorAgent,
    FlexAgent,
    MemoryAgent,
    WorkerAgent,
)
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.models import PipelineStage, PipelineState


class PipelineCancelled(Exception):
    """Raised when cooperative soft-cancel aborts a pipeline mid-run."""


class Orchestrator:
    def __init__(
        self,
        bus: EventBus,
        llm_manager: Any | None = None,
        agent_manager: AgentManager | None = None,
        memory: Any | None = None,
    ) -> None:
        self.bus = bus
        self.llm = llm_manager
        self.agents = agent_manager or AgentManager(bus)
        self.memory_store = memory
        self._state = PipelineState()
        self._clarified_once = False
        self.cancel_check: Callable[[], bool] | None = None
        self.plan_mode: str = "default"
        self.tools: Any | None = None  # ToolRegistry from Hub (optional)
        self._stage_t0: float | None = None
        self._stage_name: str | None = None
        self._build_roles()

    def _check_cancel(self) -> None:
        fn = self.cancel_check
        if callable(fn) and fn():
            self._abort_cancelled()
            raise PipelineCancelled("cancelled by user")

    def _abort_cancelled(self) -> None:
        """
        Soft-cancel: leave pipeline re-executable (H1).
        Keep brainstorm notes; do not mark error or call memory store (H7).
        """
        self._close_stage_timing()
        had_notes = bool((self._state.brainstorm_notes or "").strip())
        self._state.error = None
        # Mid-run stages (distill/flex/work) blocked can_execute — restore brainstorm
        if had_notes:
            self._state.stage = PipelineStage.brainstorm
            self._state.mode = "brainstorm"
        else:
            self._state.stage = PipelineStage.idle
        self.bus.emit(
            "pipeline.cancelled",
            {
                "restored_stage": self._state.stage.value,
                "can_execute": had_notes,
            },
        )

    def _close_stage_timing(self) -> None:
        if self._stage_t0 is None or not self._stage_name:
            self._stage_t0 = None
            self._stage_name = None
            return
        ms = round((time.perf_counter() - self._stage_t0) * 1000.0, 1)
        name = self._stage_name
        prev = float(self._state.stage_timings.get(name, 0.0) or 0.0)
        self._state.stage_timings[name] = round(prev + ms, 1) if prev else ms
        self.bus.emit("pipeline.stage_timing", {"stage": name, "ms": ms})
        self._stage_t0 = None
        self._stage_name = None

    def _begin_stage_timing(self, name: str) -> None:
        self._close_stage_timing()
        self._stage_t0 = time.perf_counter()
        self._stage_name = name

    def _build_roles(self) -> None:
        get = self.agents.get
        self.brainstorm = BrainstormAgent(get(AgentId.BRAINSTORM), self.bus, self.llm)
        self.flex = FlexAgent(get(AgentId.FLEX), self.bus, self.llm)
        self.coordinator = CoordinatorAgent(get(AgentId.COORDINATOR), self.bus, self.llm)
        self.worker1 = WorkerAgent(get(AgentId.WORKER1), self.bus, self.llm)
        self.worker2 = WorkerAgent(get(AgentId.WORKER2), self.bus, self.llm)
        self.worker3 = WorkerAgent(get(AgentId.WORKER3), self.bus, self.llm)
        self.worker4 = WorkerAgent(get(AgentId.WORKER4), self.bus, self.llm)
        self.memory = MemoryAgent(get(AgentId.MEMORY), self.bus, self.llm, memory=self.memory_store)
        self._workers = {
            "worker1": self.worker1,
            "worker2": self.worker2,
            "worker3": self.worker3,
            "worker4": self.worker4,
        }

    @property
    def state(self) -> PipelineState:
        return self._state

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
            reqs, question = self.coordinator.distill(text, self._state.brainstorm_notes, mem)
            self._state.distilled_requirements = reqs
            self.bus.emit("pipeline.distill", {"requirements": list(reqs)})

            self._check_cancel()
            if question is not None and not self._clarified_once:
                self._state.pending_question = question
                self._set_stage(PipelineStage.clarify)
                self.bus.emit(
                    "pipeline.question",
                    {
                        "id": question.id,
                        "text": question.text,
                        "options": list(question.options),
                    },
                )
                return self._state

            self._check_cancel()
            self._run_flex_coord_workers()
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def brainstorm_turn(self, user_text: str) -> PipelineState:
        text = user_text.strip()
        try:
            if not text:
                self._fail("Empty user text")
                return self._state

            continuing = (
                self._state.mode == "brainstorm"
                and self._state.stage == PipelineStage.brainstorm
                and bool(self._state.brainstorm_turns)
                and not _is_topic_switch(self._state.brainstorm_turns, text)
            )
            _exec_only = text.lower().strip(" !.。") in {
                "execute",
                "ausführen",
                "ausfuehren",
                "run it",
                "run execute",
                "flex execute",
                "jetzt ausführen",
                "jetzt ausfuehren",
                "pipeline starten",
                "starte execute",
                "start execute",
            }
            if not continuing:
                prev_turns = list(self._state.brainstorm_turns or [])
                prev_notes = self._state.brainstorm_notes or ""
                prev_task = (self._state.user_text or "").strip()
                self._state = PipelineState(user_text=text, mode="brainstorm")
                if _exec_only and prev_turns and prev_task:
                    self._state.brainstorm_turns = prev_turns
                    self._state.brainstorm_notes = prev_notes
                    self._state.user_text = prev_task
                    self._state.mode = "brainstorm"
            else:
                self._state.mode = "brainstorm"
                self._state.error = None
                self._state.worker_results = []
                self._state.worker_outputs = []
                self._state.distilled_requirements = []
                self._state.flex_notes = ""
                self._state.pending_question = None
                if not _exec_only:
                    self._state.user_text = text

            self._clarified_once = False

            self._check_cancel()
            self.bus.emit("pipeline.stage", {"stage": "memory"})
            topic = self._state.user_text or text
            mem = self.memory.recall(topic)
            self._state.memory_context = mem
            if mem:
                self.bus.emit("pipeline.memory_context", {"context": mem})

            history = list(self._state.brainstorm_turns)
            self._state.brainstorm_turns.append({"role": "user", "text": text})

            self._check_cancel()
            if not self.brainstorm.enabled:
                notes = "(Brainstorm agent is off — enable it to collect ideas.)"
            else:
                self._set_stage(PipelineStage.brainstorm)
                notes = self.brainstorm.run(text, mem, history=history)

            self._state.brainstorm_turns.append({"role": "brainstorm", "text": notes})
            self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)

            flex_exec: dict | None = None
            if self.flex.enabled:
                absorbed: list[str] = []
                try:
                    absorbed = list(self.flex.absorb(text, mem) or [])
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "flex_absorb", "error": str(exc)},
                    )
                try:
                    flex_exec = self.flex.maybe_request_execute(
                        text,
                        self._state.brainstorm_turns,
                        mem,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "flex_execute", "error": str(exc)},
                    )
                    flex_exec = None
                flex_line: str | None = None
                if flex_exec and flex_exec.get("message"):
                    flex_line = str(flex_exec["message"])
                else:
                    try:
                        flex_line = self.flex.brainstorm_contribute(
                            text,
                            notes,
                            mem,
                            absorbed=absorbed,
                        )
                    except Exception as exc:  # noqa: BLE001
                        self.bus.emit(
                            "pipeline.warning",
                            {"stage": "flex_chat", "error": str(exc)},
                        )
                        flex_line = None
                if flex_line:
                    self._state.brainstorm_turns.append({"role": "flex", "text": flex_line})
                    self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)
            if not _exec_only:
                self._state.user_text = text

            self._set_stage(PipelineStage.brainstorm)
            self.bus.emit(
                "pipeline.brainstorm",
                {
                    "notes": notes,
                    "turns": list(self._state.brainstorm_turns),
                    "mode": "brainstorm",
                },
            )
            self.bus.emit(
                "pipeline.brainstorm_ready",
                {
                    "can_execute": bool(self._state.brainstorm_notes.strip()),
                    "turns": len(self._state.brainstorm_turns),
                },
            )
            should_exec = False
            exec_reason = "context"
            if self.flex.enabled:
                if flex_exec and flex_exec.get("execute"):
                    should_exec = True
                    exec_reason = f"flex:{flex_exec.get('reason') or 'request'}"
            elif _wants_auto_execute(text, self._state.brainstorm_turns):
                should_exec = True
                exec_reason = "context"
            if should_exec and self._state.brainstorm_notes.strip():
                self._check_cancel()
                self.bus.emit(
                    "pipeline.auto_execute",
                    {"reason": exec_reason, "text": text[:120]},
                )
                return self.execute()
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def execute(self) -> PipelineState:
        try:
            text = (self._state.user_text or "").strip()
            if self._state.brainstorm_turns:
                text = _pick_execute_task(self._state.brainstorm_turns, fallback=text)
                self._state.user_text = text
            if not text:
                self._fail("Nothing to execute — brainstorm first")
                return self._state

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
            self._stage_t0 = None
            self._stage_name = None

            self._begin_stage_timing("memory")
            mem = self._state.memory_context or self.memory.recall(text)
            self._state.memory_context = mem
            self._close_stage_timing()

            self._check_cancel()
            self._set_stage(PipelineStage.distill)
            reqs, question = self.coordinator.distill(text, notes, mem)
            self._state.distilled_requirements = reqs
            self.bus.emit("pipeline.distill", {"requirements": list(reqs)})

            self._check_cancel()
            if question is not None and not self._clarified_once:
                self._state.pending_question = question
                self._set_stage(PipelineStage.clarify)
                self.bus.emit(
                    "pipeline.question",
                    {
                        "id": question.id,
                        "text": question.text,
                        "options": list(question.options),
                    },
                )
                return self._state

            self._run_flex_coord_workers()
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def answer_clarify(self, option: str) -> PipelineState:
        """
        Apply clarify answer then run workers.

        H2: keep ``pending_question`` until work reaches a terminal success
        (done). On cancel/error the question stays so the user can re-answer.
        """
        if self._state.stage != PipelineStage.clarify or self._state.pending_question is None:
            raise ValueError("No pending clarification question")
        answer = option.strip()
        q = self._state.pending_question
        clarify_line = f"User clarified ({q.id}): {answer}"
        if clarify_line not in self._state.distilled_requirements:
            self._state.distilled_requirements.append(clarify_line)
        # Prevent re-asking on a later distill, but do not drop the question yet
        self._clarified_once = True
        try:
            self._run_flex_coord_workers()
        except PipelineCancelled:
            # Soft-cancel may restore brainstorm — put user back on clarify if needed
            self._state.pending_question = q
            if self._state.stage != PipelineStage.done:
                self._state.stage = PipelineStage.clarify
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
            self._state.pending_question = q
            self._state.stage = PipelineStage.clarify
            return self._state

        if self._state.stage == PipelineStage.done:
            self._state.pending_question = None
        elif self._state.stage == PipelineStage.error:
            self._state.pending_question = q
            self._state.stage = PipelineStage.clarify
        else:
            # Cancel restored brainstorm / mid-stage abort — keep question
            self._state.pending_question = q
        return self._state

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
            tool_ctx = _prefetch_worker_tools(
                f"{text}\n{task}",
                bus=self.bus,
                tools=getattr(self, "tools", None),
                memory=self.memory_store,
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
            self._finish()
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def _run_flex_coord_workers(self) -> None:
        text = self._state.user_text
        mem = self._state.memory_context
        reqs = list(self._state.distilled_requirements)

        self._check_cancel()
        if self.flex.enabled:
            self._set_stage(PipelineStage.flex)
            from gnom_hub.memory.dedupe import already_covered

            for wish in self.flex.binding_wishes(mem or ""):
                tag = f"Flex-wish: {wish}"
                if already_covered(tag, self._state.distilled_requirements, strategy="requirement"):
                    continue
                self._state.distilled_requirements.append(tag)
            reqs = list(self._state.distilled_requirements)
            notes = self.flex.run(text, reqs, mem)
            self._state.flex_notes = notes
            self.bus.emit(
                "pipeline.flex",
                {
                    "notes": notes,
                    "preset": "personal",
                    "wishes": self.flex.binding_wishes(mem or ""),
                },
            )
            if notes:
                lines = [ln.strip() for ln in notes.strip().splitlines() if ln.strip()]
                first = ""
                for s in lines:
                    s2 = s.lstrip("-•* ")
                    if len(s2) >= 12 and not s2.endswith(":"):
                        first = s2[:160]
                        break
                if not first and lines:
                    first = lines[0][:160]
                if first:
                    line = f"Flex/personal: {first}"
                    if line not in self._state.distilled_requirements:
                        self._state.distilled_requirements.append(line)

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
            self._state.warnings = list(self._state.warnings or []) + ["coordinator_disabled_skip"]
            self._finish()
            return

        self._set_stage(PipelineStage.coordinate)
        worker_ids = [wid for wid, w in self._workers.items() if w.enabled]
        tasks = self.coordinator.plan(
            text,
            self._state.distilled_requirements,
            worker_ids,
            plan_mode=getattr(self, "plan_mode", "default") or "default",
        )
        meta = getattr(self.coordinator, "last_plan_meta", None) or {}
        resolved = str(meta.get("plan_mode") or getattr(self, "plan_mode", "default") or "default")
        self._state.resolved_plan_mode = resolved
        self.bus.emit(
            "pipeline.coordinate",
            {
                "tasks": [{"worker": w, "task": t} for w, t in tasks],
                "plan_mode": resolved,
                "fast_path": bool(meta.get("fast_path")),
                "requested_mode": meta.get("requested_mode")
                or getattr(self, "plan_mode", "default"),
            },
        )

        # All workers off or empty plan with no workers → soft success + note (tests)
        if not worker_ids:
            self._state.worker_results = []
            self._state.worker_outputs = []
            self._state.quality_notes = "No workers enabled — nothing to execute."
            self._state.warnings = list(self._state.warnings or []) + ["no_workers_enabled"]
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
        tool_ctx = _prefetch_worker_tools(
            pre_blob,
            bus=self.bus,
            tools=getattr(self, "tools", None),
            memory=self.memory_store,
        )
        if tool_ctx:
            mem = (mem or "").rstrip() + "\n\nTool prefetch (auto):\n" + tool_ctx
            self.bus.emit(
                "pipeline.web_fetch",
                {"chars": len(tool_ctx), "via": "worker_prefetch"},
            )
        dod = _definition_of_done(text, self._state.distilled_requirements)
        for i, (wid, task) in enumerate(tasks, start=1):
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
            retries = 0
            max_retries = 2
            while retries < max_retries:
                gate0 = _validate_worker_draft(result, user_text=text, task=task)
                # Auth / missing key: do not burn retries on the same dead key
                if "worker_error" in (gate0.get("issues") or []) or (
                    "FEHLER" in (result or "") and "Deliverable" in (result or "")
                ):
                    break
                need_retry = False
                retry_why = ""
                if _wants_html_artifact(text, task) and not _html_complete(result):
                    need_retry, retry_why = True, "incomplete_html"
                elif "missing_required_interaction" in (gate0.get("issues") or []):
                    need_retry, retry_why = True, "missing_interaction"
                elif not gate0.get("ok", True) and _wants_html_artifact(text, task):
                    need_retry, retry_why = True, "gate_fail"
                if not need_retry:
                    break
                retries += 1
                self.bus.emit(
                    "pipeline.quality_retry",
                    {"worker": wid, "reason": retry_why, "attempt": retries},
                )
                self._check_cancel()
                if retries == 1:
                    hint = (
                        "RETRY (mandatory): ONE complete HTML file "
                        "<!DOCTYPE html>…</html>. "
                        "PRIORITY: structure + working JS interactions FIRST, "
                        "minimal CSS only. Empty/error states only after functions. "
                        "Must include at least one onclick= or addEventListener. "
                        "Never truncate mid-CSS. Finish with </html>."
                    )
                else:
                    hint = (
                        "RETRY 2 — SCOPE REDUCTION (mandatory):\n"
                        "Deliver a SMALLER but COMPLETE HTML page.\n"
                        "- Drop decorative CSS (only tiny layout)\n"
                        "- Keep: shell + 1–3 core interactions + empty state\n"
                        "- MUST end with </html>; no open tags\n"
                        "- No long style blocks; functions first\n"
                        f"Previous gate issues: {', '.join(gate0.get('issues') or [])}"
                    )
                result = worker.run(
                    task_full + "\n\n" + hint,
                    text,
                    self._state.distilled_requirements,
                    mem,
                )
            gate = _validate_worker_draft(result, user_text=text, task=task)
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
            self._state.warnings = list(self._state.warnings or []) + ["empty_worker_results"]
        self.bus.emit(
            "pipeline.quality",
            {"notes": self._state.quality_notes, "workers": len(outputs)},
        )
        self._check_cancel()
        self._flex_nudge_and_fix(text, mem, dod)
        self._check_cancel()
        self._finish()

    def _flex_nudge_and_fix(self, text: str, mem: str, dod: str) -> None:
        if not self.flex.enabled:
            self._state.agent_nudges = []
            return
        outputs = list(self._state.worker_outputs or [])
        try:
            nudges = self.flex.nudge_gaps(
                text,
                list(self._state.distilled_requirements),
                outputs,
                self._state.quality_notes or "",
                mem,
            )
        except Exception as exc:  # noqa: BLE001
            self.bus.emit(
                "pipeline.warning",
                {"stage": "flex_nudge", "error": str(exc)},
            )
            nudges = []
        self._state.agent_nudges = list(nudges or [])
        if not nudges:
            return
        lines = [
            self._state.quality_notes or "",
            "",
            "Flex → Agenten (bevor du es wiederholen musst):",
        ]
        for n in nudges:
            aid = str(n.get("agent") or "")
            msg = str(n.get("message") or "").strip()
            if not aid or not msg:
                continue
            lines.append(f"• {aid}: {msg}")
            self.bus.emit(
                "pipeline.agent_nudge",
                {"agent": aid, "message": msg, "reason": n.get("reason")},
            )
            worker = self._workers.get(aid)
            if worker is None or not worker.enabled:
                continue
            task = text
            for o in outputs:
                if str(o.get("worker") or "") == aid:
                    task = str(o.get("task") or text)
                    break
            self._check_cancel()
            self.bus.emit("pipeline.stage", {"stage": aid})
            fixed = worker.run(
                f"{task}\n\n{dod}\n\n"
                f"=== FLEX CORRECTION (mandatory — user should not have to repeat this) ===\n"
                f"{msg}\n"
                f"=== END CORRECTION ===",
                text,
                list(self._state.distilled_requirements),
                mem,
            )
            for o in outputs:
                if str(o.get("worker") or "") == aid:
                    o["result"] = fixed
                    o["validation"] = _validate_worker_draft(fixed, user_text=text, task=task)
                    o["flex_nudge"] = msg
                    break
            self.bus.emit(
                "pipeline.worker",
                {
                    "worker": aid,
                    "result": fixed,
                    "task": task,
                    "flex_nudge": msg,
                    "rerun": True,
                },
            )
        self._state.worker_outputs = outputs
        self._state.worker_results = [str(o.get("result") or "") for o in outputs]
        self._state.quality_notes = "\n".join(lines).strip()
        self._state.quality_notes = (
            _quality_check(
                self._state.user_text,
                self._state.distilled_requirements,
                outputs,
            )
            + "\n\n"
            + "\n".join(lines[2:])
        ).strip()
        self.bus.emit(
            "pipeline.quality",
            {
                "notes": self._state.quality_notes,
                "workers": len(outputs),
                "nudges": list(self._state.agent_nudges),
            },
        )

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
            },
        )
        self.bus.emit(
            "pipeline.timings",
            {
                "stages": dict(self._state.stage_timings),
                "total_ms": total_ms,
                "plan_mode": self._state.resolved_plan_mode
                or getattr(self, "plan_mode", "default"),
            },
        )

    def _set_stage(self, stage: PipelineStage) -> None:
        self._close_stage_timing()
        self._state.stage = stage
        self.bus.emit("pipeline.stage", {"stage": stage.value})
        if stage in (
            PipelineStage.done,
            PipelineStage.error,
            PipelineStage.idle,
            PipelineStage.clarify,
        ):
            return
        self._stage_t0 = time.perf_counter()
        self._stage_name = stage.value

    def _fail(self, message: str) -> None:
        self._close_stage_timing()
        self._state.stage = PipelineStage.error
        self._state.error = message
        self.bus.emit("pipeline.stage", {"stage": PipelineStage.error.value})
        self.bus.emit(
            "pipeline.error",
            {
                "error": message,
                "stage_timings": dict(self._state.stage_timings),
            },
        )


def _wants_auto_execute(text: str, turns: list[dict] | None = None) -> bool:
    from gnom_hub.agents.plan_fast_path import _wants_one_html_page

    t = (text or "").strip()
    if not t:
        return False
    low = t.lower().strip(" !.。")

    users = [
        str(x.get("text") or "").strip()
        for x in (turns or [])
        if x.get("role") == "user" and str(x.get("text") or "").strip()
    ]
    go_words = {
        "go",
        "los",
        "ok",
        "okay",
        "ja",
        "jap",
        "jo",
        "yes",
        "yep",
        "sure",
        "machs",
        "mach das",
        "mach es",
        "mach",
        "execute",
        "do it",
        "ja mach",
        "ja bitte",
        "bitte",
        "jetzt",
        "bau es",
        "bau das",
        "umsetzen",
        "setz um",
        "plan erstellen",
        "erstell den plan",
        "erstelle den plan",
        "mach den plan",
        "ja erstell",
        "ja erstellen",
        "los gehts",
        "los geht's",
        "do the plan",
        "create the plan",
        "run it",
        "tu es",
    }
    if len(users) >= 2 and (low in go_words or low.startswith(("ja ", "ok "))):
        return True

    if len(t) < 6:
        return False

    diagnose = (
        "wo hakt",
        "wo es hakt",
        "wo ist der fehler",
        "was ist mit",
        "warum",
        "erklär",
        "analys",
        "prüfe die pipeline",
        "only brainstorm",
        "nur brainstorm",
        "nur ideen",
        "ideen zu",
        "soll ich",
    )
    buildish = (
        "baue",
        "build",
        "html",
        "landing",
        "seite",
        "page",
        "implement",
        "erstelle",
        "mach mir",
        "todo",
    )
    if any(d in low for d in diagnose) and not any(b in low for b in buildish):
        return False
    if low.endswith("?") and not any(b in low for b in buildish):
        return False

    if _wants_one_html_page(t):
        return True
    triggers = (
        "baue ",
        "baue eine",
        "baue mir",
        "build a",
        "build me",
        "erstelle ",
        "create a",
        "implement ",
        "mach mir",
        "mach eine",
        "schreibe ",
        "schreib eine",
        "single-file",
        "single file",
        "landingpage",
        "landing page",
        "website",
        "todo app",
        "ausführen",
        "setz um",
        "umsetzen",
        "deliver",
        "fertig machen",
        "plan erstellen",
        "erstell den plan",
    )
    return any(k in low for k in triggers)


def _pick_execute_task(turns: list[dict], fallback: str = "") -> str:
    from gnom_hub.agents.plan_fast_path import _wants_one_html_page

    users = [
        str(t.get("text") or "").strip()
        for t in turns
        if t.get("role") == "user" and str(t.get("text") or "").strip()
    ]
    if not users:
        return (fallback or "").strip()
    for u in reversed(users):
        if _wants_one_html_page(u) or len(u) >= 48:
            return u
    return users[-1]


def _format_turns(turns: list[dict]) -> str:
    lines: list[str] = []
    for t in turns:
        role = str(t.get("role") or "")
        text = str(t.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            lines.append(f"You: {text}")
        elif role == "flex":
            lines.append(f"Flex:\n{text}")
        elif role == "brainstorm":
            lines.append(f"Brainstorm:\n{text}")
        else:
            lines.append(f"{role}:\n{text}")
        lines.append("")
    return "\n".join(lines).strip()


def _is_topic_switch(turns: list[dict], new_text: str) -> bool:
    new = (new_text or "").strip()
    if len(new) < 48:
        return False
    prior_users = [
        str(t.get("text") or "").strip()
        for t in turns
        if t.get("role") == "user" and str(t.get("text") or "").strip()
    ]
    if not prior_users:
        return False
    first = prior_users[0].lower()
    new_l = new.lower()
    a = {w for w in first.split() if len(w) > 2}
    b = {w for w in new_l.split() if len(w) > 2}
    if not a:
        return True
    overlap = len(a & b) / max(len(a), 1)
    if len(new) >= 80 and overlap < 0.28:
        return True
    deliverable = (
        "html",
        "landing",
        "website",
        "webpage",
        "web page",
        "build ",
        "create ",
        "make ",
        "implement ",
        "seite",
    )
    return (
        any(k in new_l for k in deliverable)
        and not any(k in first for k in deliverable)
        and overlap < 0.4
    )


def _prefetch_urls(blob: str, *, limit: int = 3) -> str:
    """Backward-compatible URL-only prefetch (tests may call this)."""
    return _prefetch_worker_tools(blob, max_urls=limit, max_tool_calls=limit)


def _prefetch_worker_tools(
    blob: str,
    *,
    bus: Any = None,
    tools: Any = None,
    memory: Any = None,
    max_urls: int = 3,
    max_tool_calls: int = 5,
) -> str:
    from gnom_hub.tools.worker_prefetch import prefetch_for_workers

    return prefetch_for_workers(
        blob,
        bus=bus,
        tools=tools,
        memory=memory,
        max_urls=max_urls,
        max_tool_calls=max_tool_calls,
    )


def _definition_of_done(user_text: str, requirements: list[str]) -> str:
    from gnom_hub.agents.roles_helpers import _is_flex_meta_requirement
    from gnom_hub.memory.dedupe import dedupe_texts

    raw = [str(r) for r in (requirements or []) if r and not _is_flex_meta_requirement(str(r))]
    reqs = dedupe_texts(raw, strategy="requirement", limit=6)
    lines = [
        "=== DEFINITION OF DONE (mandatory) ===",
        "DONE means functional complete — not 'draft exists' or 'pretty CSS only'.",
        (
            "ORDER: (1) structure (2) core functions/interactions "
            "(3) error/empty states (4) CSS last (~30% max)."
        ),
        "If HTML/page/landing/UI is required:",
        "  [ ] Single complete document: <!DOCTYPE html> … </html>",
        "  [ ] No mid-file truncation; close all tags/braces",
        "  [ ] At least one working interaction (onclick / addEventListener / form)",
        "  [ ] Empty/error states only AFTER core functions, never instead of them",
        "  [ ] Prefer minimal CSS over incomplete JS",
        "If code is required: runnable/readable end-to-end, not stubs-only.",
        "If budget is tight: drop decoration, keep structure + functions + </html>.",
    ]
    if reqs:
        lines.append("Requirements (MUSS):")
        lines.extend(f"  [ ] {r}" for r in reqs)
        wish_lines = [
            r for r in reqs if str(r).lower().startswith(("flex-wish:", "user:", "wish:"))
        ]
        if wish_lines:
            lines.append("STANDING WISHES — ABSOLUTE (no pushback, implement fully):")
            lines.extend(f"  [!] {r}" for r in wish_lines)
    if (user_text or "").strip():
        lines.append(f"User task: {(user_text or '').strip()[:400]}")
    lines.append("=== END DoD ===")
    return "\n".join(lines)


def _wants_html_artifact(user_text: str, task: str = "") -> bool:
    from gnom_hub.agents.plan_fast_path import _wants_one_html_page

    return _wants_one_html_page(f"{user_text or ''} {task or ''}")


def _html_complete(body: str) -> bool:
    """
    True when body looks like a finished single-file HTML document.

    M11: a lone ``</html>`` mid-stream (truncated doc) must not pass.
    """
    import re

    s = (body or "").strip()
    if not s:
        return False
    if "```" in s:
        m = re.search(r"```(?:html)?\s*([\s\S]*?)```", s, re.IGNORECASE)
        if m:
            s = m.group(1).strip()
    low = s.lower()
    if "<!doctype" not in low and "<html" not in low:
        return False
    # Prefer last closing tag; reject if significant junk after it
    close_idx = low.rfind("</html>")
    if close_idx < 0:
        return False
    after = low[close_idx + len("</html>") :].strip()
    # Allow only whitespace / trivial trailing commentary after </html>
    if (
        after
        and not re.fullmatch(r"(<!--.*?-->|\s)*", after, flags=re.DOTALL)
        and (len(after) > 40 or "<" in after)
    ):
        return False
    # Closing tag must not appear too early relative to document size
    # (very short docs that fully close are still OK)
    if close_idx < max(40, int(len(low) * 0.35)) and len(low) > 120 and close_idx < len(low) * 0.5:
        return False
    if low.rstrip().endswith(("...", "…", "<!--", "<style", "<script", "{", "(")):
        return False
    # Unclosed style/script often means truncation before </html> was faked
    if low.count("<script") > low.count("</script>"):
        return False
    if low.count("<style") > low.count("</style>"):
        return False
    open_tags = low.count("<")
    close_tags = low.count(">")
    return not (open_tags > 5 and close_tags < open_tags * 0.85)


def _has_interaction(body: str) -> bool:
    low = (body or "").lower()
    keys = (
        "onclick=",
        "onchange=",
        "onsubmit=",
        "addEventListener",
        "addeventlistener",
        "oninput=",
        "ontoggle=",
    )
    return any(k.lower() in low for k in keys)


def _css_heavy_without_js(body: str) -> bool:
    low = (body or "").lower()
    style_n = low.count("<style") + low.count("stylesheet")
    css_blocks = low.count("{")
    js = low.count("<script") + low.count("function ") + low.count("=>")
    interact = _has_interaction(body)
    return bool(
        style_n + (1 if css_blocks > 15 else 0) >= 1 and css_blocks > 20 and not interact and js < 2
    )


def _validate_worker_draft(body: str, *, user_text: str = "", task: str = "") -> dict:
    s = (body or "").strip()
    issues: list[str] = []
    ok = True
    if len(s) < 40:
        ok = False
        issues.append("too_short")
    if "FEHLER" in s and "Deliverable" in s:
        ok = False
        issues.append("worker_error")
    if (s.startswith("Stub") or "Stub —" in s) and "FEHLER" not in s:
        ok = False
        issues.append("stub")
    if _wants_html_artifact(user_text, task):
        if not _html_complete(s):
            ok = False
            issues.append("incomplete_html")
        if "</html>" not in s.lower():
            issues.append("missing_html_close")
        if _html_complete(s) and not _has_interaction(s):
            issues.append("no_interaction")
            blob = f"{user_text} {task}".lower()
            if any(
                k in blob
                for k in (
                    "interact",
                    "click",
                    "demo",
                    "nav",
                    "todo",
                    "filter",
                    "state",
                    "klick",
                    "dom",
                )
            ):
                ok = False
                issues.append("missing_required_interaction")
        if _css_heavy_without_js(s):
            issues.append("css_before_functions")
    if s.rstrip().endswith(("...", "…")) and len(s) > 80:
        ok = False
        issues.append("truncated_ellipsis")
    return {
        "ok": ok,
        "issues": issues,
        "chars": len(s),
        "html_complete": (
            _html_complete(s) if ("<html" in s.lower() or "<!doctype" in s.lower()) else None
        ),
        "has_interaction": _has_interaction(s),
    }


def _quality_check(
    user_text: str,
    requirements: list[str],
    outputs: list[dict],
) -> str:
    if not outputs:
        return "Quality: no worker outputs."
    lines: list[str] = ["Quality check (gates + DoD):"]
    task_low = (user_text or "").lower()
    fail_n = 0
    for out in outputs:
        name = str(out.get("name") or out.get("worker") or "worker")
        body = str(out.get("result") or "").strip()
        gate = out.get("validation") or _validate_worker_draft(
            body, user_text=user_text, task=str(out.get("task") or "")
        )
        score = 0
        notes: list[str] = list(gate.get("issues") or [])
        if len(body) >= 120:
            score += 2
        elif len(body) >= 40:
            score += 1
            if "short" not in notes:
                notes.append("short")
        else:
            if "too_short" not in notes:
                notes.append("too short")
        if body.startswith("Stub") or "Stub —" in body:
            if "stub" not in notes:
                notes.append("stub output")
        else:
            score += 1
        low = body.lower()
        if "<!doctype" in low or "<html" in low:
            score += 1
            notes.append("html doc")
            if _html_complete(body):
                score += 1
                notes.append("html complete")
            else:
                notes.append("html incomplete")
        tokens = [w for w in task_low.replace(",", " ").split() if len(w) > 4][:8]
        hits = sum(1 for w in tokens if w in low)
        if hits >= 2:
            score += 1
        elif tokens:
            notes.append("weak task match")
        req_hits = 0
        for r in requirements[:5]:
            words = [w for w in r.lower().split() if len(w) > 5][:3]
            if any(w in low for w in words):
                req_hits += 1
        if req_hits:
            score += 1
        if not gate.get("ok", True):
            fail_n += 1
            grade = "fail" if score < 4 else "weak"
        else:
            grade = "ok" if score >= 4 else ("weak" if score >= 2 else "poor")
        extra = f" ({', '.join(notes)})" if notes else ""
        lines.append(f"• {name}: {grade} score={score}/7{extra}")
    if fail_n:
        lines.append(
            f"Gates: {fail_n}/{len(outputs)} draft(s) failed validation "
            "(incomplete HTML, truncation, or stub)."
        )
    else:
        lines.append("Gates: all drafts passed basic validation.")
    return "\n".join(lines)


Pipeline = Orchestrator
