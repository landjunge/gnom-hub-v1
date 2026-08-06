"""
V1 Orchestrator — real agent roles.

Default UX: brainstorm_turn (dialogue only).
Explicit execute: distill → flex → coordinator → workers → memory.
start() still runs full pipeline (tests / Telegram /do).
"""

from __future__ import annotations

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
        # Optional: hub sets this to job.get("cancel") during async runs
        self.cancel_check: Callable[[], bool] | None = None
        # Team/workflow plan strategy (default | full_page_html | plan_qa | diagnosis)
        self.plan_mode: str = "default"
        self._build_roles()

    def _check_cancel(self) -> None:
        """Abort between stages/workers if soft-cancel was requested."""
        fn = self.cancel_check
        if callable(fn) and fn():
            self.bus.emit("pipeline.cancelled", {"stage": self._state.stage.value})
            raise PipelineCancelled("cancelled by user")

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
        """Full pipeline in one go (compat for tests / Telegram /do)."""
        text = user_text.strip()
        self._state = PipelineState(user_text=text, mode="full")
        self._clarified_once = False
        try:
            if not text:
                self._fail("Empty user text")
                return self._state

            self.bus.emit("pipeline.stage", {"stage": "memory"})
            mem = self.memory.recall(text)
            self._state.memory_context = mem
            if mem:
                self.bus.emit("pipeline.memory_context", {"context": mem})

            if self.brainstorm.enabled:
                self._set_stage(PipelineStage.brainstorm)
                notes = self.brainstorm.run(text, mem, history=[])
                self._state.brainstorm_notes = notes
                self._state.brainstorm_turns = [
                    {"role": "user", "text": text},
                    {"role": "brainstorm", "text": notes},
                ]
                self.bus.emit("pipeline.brainstorm", {"notes": notes, "mode": "full"})

            self._set_stage(PipelineStage.distill)
            reqs, question = self.coordinator.distill(text, self._state.brainstorm_notes, mem)
            self._state.distilled_requirements = reqs
            self.bus.emit("pipeline.distill", {"requirements": list(reqs)})

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
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def brainstorm_turn(self, user_text: str) -> PipelineState:
        """One dialogue turn — does NOT distill or run workers."""
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
            # Explicit Execute after a finished run: keep last task so Flex can re-trigger
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
                    # Restore task context; do not append a fake user task line yet
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
                # Latest user message is the task of record (not a bare Execute token)
                if not _exec_only:
                    self._state.user_text = text

            self._clarified_once = False

            self.bus.emit("pipeline.stage", {"stage": "memory"})
            topic = self._state.user_text or text
            mem = self.memory.recall(topic)
            self._state.memory_context = mem
            if mem:
                self.bus.emit("pipeline.memory_context", {"context": mem})

            history = list(self._state.brainstorm_turns)
            self._state.brainstorm_turns.append({"role": "user", "text": text})

            if not self.brainstorm.enabled:
                notes = "(Brainstorm agent is off — enable it to collect ideas.)"
            else:
                self._set_stage(PipelineStage.brainstorm)
                notes = self.brainstorm.run(text, mem, history=history)

            self._state.brainstorm_turns.append({"role": "brainstorm", "text": notes})
            self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)

            # Flex: absorb wishes + may request Execute (user Stellvertreter)
            flex_exec: dict | None = None
            if self.flex.enabled:
                try:
                    self.flex.absorb(text, mem)
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
                if flex_exec and flex_exec.get("message"):
                    self._state.brainstorm_turns.append(
                        {"role": "flex", "text": str(flex_exec["message"])}
                    )
                    self._state.brainstorm_notes = _format_turns(self._state.brainstorm_turns)
            # Pin task to latest real message — bare Execute keeps prior task
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
            # Flex owns Execute trigger when enabled; else legacy context heuristic
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
                self.bus.emit(
                    "pipeline.auto_execute",
                    {"reason": exec_reason, "text": text[:120]},
                )
                return self.execute()
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def execute(self) -> PipelineState:
        """Distill + run workers from accumulated brainstorm."""
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
            # Clear sticky error / stale worker output from a previous failed run
            self._state.error = None
            self._state.worker_results = []
            self._state.worker_outputs = []
            self._state.quality_notes = ""
            self._state.pending_question = None

            mem = self._state.memory_context or self.memory.recall(text)
            self._state.memory_context = mem

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
            # Soft-cancel: leave partial state; hub marks job cancelled
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def answer_clarify(self, option: str) -> PipelineState:
        if self._state.stage != PipelineStage.clarify or self._state.pending_question is None:
            raise ValueError("No pending clarification question")
        answer = option.strip()
        q = self._state.pending_question
        self._state.distilled_requirements.append(f"User clarified ({q.id}): {answer}")
        self._state.pending_question = None
        self._clarified_once = True
        try:
            self._run_flex_coord_workers()
        except PipelineCancelled:
            return self._state
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def rerun_worker(self, worker_id: str) -> PipelineState:
        """Re-run a single worker using its last task (or user text fallback)."""
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
            web_ctx = _prefetch_urls(f"{text}\n{task}")
            if web_ctx:
                mem = (mem or "").rstrip() + "\n\nWeb fetch (auto):\n" + web_ctx
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
            self._finish()
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
            notes = self.flex.run(text, reqs, mem)
            self._state.flex_notes = notes
            self.bus.emit(
                "pipeline.flex",
                {"notes": notes, "preset": self.flex.state.preset},
            )
            if notes:
                # Prefer a "Was ich über dich weiß" line for workers
                first = ""
                for ln in notes.strip().splitlines():
                    s = ln.strip().lstrip("-•* ")
                    if len(s) >= 12 and not s.endswith(":"):
                        first = s[:160]
                        break
                if not first:
                    first = notes.strip().splitlines()[0][:160]
                preset = self.flex.state.preset or "personal"
                self._state.distilled_requirements.append(f"Flex/{preset}: {first}")

        self._check_cancel()
        if not self.coordinator.enabled:
            self.bus.emit(
                "pipeline.coordinate",
                {"tasks": [], "skipped": True, "reason": "coordinator disabled"},
            )
            self._state.worker_results = []
            self._state.worker_outputs = []
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
        self.bus.emit(
            "pipeline.coordinate",
            {"tasks": [{"worker": w, "task": t} for w, t in tasks]},
        )

        self._check_cancel()
        self._set_stage(PipelineStage.work)
        results: list[str] = []
        outputs: list[dict] = []
        # Pre-fetch public URLs from user task + assignments (plan: internet lite)
        web_ctx = _prefetch_urls(f"{text}\n" + "\n".join(t for _, t in tasks))
        if web_ctx:
            mem = (mem or "").rstrip() + "\n\nWeb fetch (auto):\n" + web_ctx
            self.bus.emit("pipeline.web_fetch", {"chars": len(web_ctx)})
        dod = _definition_of_done(text, self._state.distilled_requirements)
        for i, (wid, task) in enumerate(tasks, start=1):
            self._check_cancel()
            worker = self._workers.get(wid)
            if worker is None or not worker.enabled:
                continue
            # UI pulse: only this worker (stage id = worker1…worker4)
            self.bus.emit("pipeline.stage", {"stage": wid})
            task_full = f"{task}\n\n{dod}".strip()
            result = worker.run(
                task_full,
                text,
                self._state.distilled_requirements,
                mem,
            )
            # Soft retries: incomplete HTML / missing interaction / still failing gates
            retries = 0
            max_retries = 2
            while retries < max_retries:
                gate0 = _validate_worker_draft(result, user_text=text, task=task)
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
                    # Scope reduction — finish a smaller but COMPLETE file
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
        self._state.worker_results = results
        self._state.worker_outputs = outputs
        self._state.quality_notes = _quality_check(
            self._state.user_text,
            self._state.distilled_requirements,
            outputs,
        )
        self.bus.emit(
            "pipeline.quality",
            {"notes": self._state.quality_notes, "workers": len(outputs)},
        )
        # Flex: tell the responsible agent what is still missing — before the user nags
        self._flex_nudge_and_fix(text, mem, dod)
        self._finish()

    def _flex_nudge_and_fix(self, text: str, mem: str, dod: str) -> None:
        """Proactive gap-fix: Flex routes fixes to the right agent once."""
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
            # Find original task for this worker
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
            # Patch output list
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
        # Re-score after fixes
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
        self.memory.store(
            user_text=self._state.user_text,
            requirements=list(self._state.distilled_requirements),
            brainstorm=self._state.brainstorm_notes,
            flex_notes=self._state.flex_notes,
            results=list(self._state.worker_results),
        )
        self._state.error = None  # success must not keep a prior sticky error
        self._set_stage(PipelineStage.done)
        self.bus.emit(
            "pipeline.done",
            {
                "requirements": list(self._state.distilled_requirements),
                "results": list(self._state.worker_results),
                "flex_notes": self._state.flex_notes,
                "quality_notes": self._state.quality_notes,
            },
        )

    def _set_stage(self, stage: PipelineStage) -> None:
        self._state.stage = stage
        self.bus.emit("pipeline.stage", {"stage": stage.value})

    def _fail(self, message: str) -> None:
        self._state.stage = PipelineStage.error
        self._state.error = message
        self.bus.emit("pipeline.stage", {"stage": PipelineStage.error.value})
        self.bus.emit("pipeline.error", {"error": message})


def _wants_auto_execute(text: str, turns: list[dict] | None = None) -> bool:
    """
    True when the user already said “do it / build it” — either as a clear
    build order in one shot, or as a short yes after brainstorm asked.
    """
    from gnom_hub.agents.roles_ext import _wants_one_html_page

    t = (text or "").strip()
    if not t:
        return False
    low = t.lower().strip(" !.。")

    users = [
        str(x.get("text") or "").strip()
        for x in (turns or [])
        if x.get("role") == "user" and str(x.get("text") or "").strip()
    ]
    # Affirmative after brainstorm offered “soll ich umsetzen?”
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

    # Pure questions / diagnosis without a deliverable → brainstorm only
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
        "soll ich",  # meta — don't treat as build
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
    # Open questions without clear build verb → let brainstorm ask first
    if low.endswith("?") and not any(b in low for b in buildish):
        return False

    # Hard build order → run without waiting for a second click
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
    """Pick the real task from brainstorm turns, not a short chat reply."""
    from gnom_hub.agents.roles_ext import _wants_one_html_page

    users = [
        str(t.get("text") or "").strip()
        for t in turns
        if t.get("role") == "user" and str(t.get("text") or "").strip()
    ]
    if not users:
        return (fallback or "").strip()
    # Prefer last user line that looks like a build/page task
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
        else:
            lines.append(f"Brainstorm:\n{text}")
        lines.append("")
    return "\n".join(lines).strip()


def _is_topic_switch(turns: list[dict], new_text: str) -> bool:
    """
    True when the new message looks like a different task than prior user turns.
    Avoids carrying 'was ist mit tts' into a full landing-page execute.
    Short follow-ups (clarifications) keep the dialogue open.
    """
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
    # Compare against the first task in the dialogue
    first = prior_users[0].lower()
    new_l = new.lower()
    a = {w for w in first.split() if len(w) > 2}
    b = {w for w in new_l.split() if len(w) > 2}
    if not a:
        return True
    overlap = len(a & b) / max(len(a), 1)
    # Long new instruction with little lexical overlap → new task
    if len(new) >= 80 and overlap < 0.28:
        return True
    # Explicit deliverable keywords only in the new message
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
    """Fetch up to N public URLs found in text; empty string if none/fail."""
    import re

    from gnom_hub.tools.web_fetch import web_fetch

    urls = re.findall(r"https?://[^\s\]\)\"'<>]+", blob or "")
    seen: set[str] = set()
    chunks: list[str] = []
    for u in urls:
        u = u.rstrip(".,;:)")
        if u in seen:
            continue
        seen.add(u)
        if len(seen) > limit:
            break
        res = web_fetch(u, max_chars=2500)
        if res.get("ok"):
            chunks.append(f"URL: {res.get('url')}\n{res.get('text', '')[:2500]}")
        else:
            chunks.append(f"URL: {u}\n(fetch failed: {res.get('error')})")
    return "\n---\n".join(chunks)


def _definition_of_done(user_text: str, requirements: list[str]) -> str:
    """Binding DoD block appended to every worker task."""
    reqs = [r for r in (requirements or []) if r and not str(r).startswith("Flex/")][:6]
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
    if (user_text or "").strip():
        lines.append(f"User task: {(user_text or '').strip()[:400]}")
    lines.append("=== END DoD ===")
    return "\n".join(lines)


def _wants_html_artifact(user_text: str, task: str = "") -> bool:
    from gnom_hub.agents.roles_ext import _wants_one_html_page

    return _wants_one_html_page(f"{user_text or ''} {task or ''}")


def _html_complete(body: str) -> bool:
    """Syntactic completeness gate for HTML drafts."""
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
    if "</html>" not in low:
        return False
    if low.rstrip().endswith(("...", "…", "<!--", "<style", "<script", "{", "(")):
        return False
    open_tags = low.count("<")
    close_tags = low.count(">")
    return not (open_tags > 5 and close_tags < open_tags * 0.85)


def _has_interaction(body: str) -> bool:
    """Heuristic: at least one client-side interaction hook."""
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
    """True if lots of CSS but almost no interaction/JS — priority inverted."""
    low = (body or "").lower()
    style_n = low.count("<style") + low.count("stylesheet")
    css_blocks = low.count("{")
    js = low.count("<script") + low.count("function ") + low.count("=>")
    interact = _has_interaction(body)
    return bool(
        style_n + (1 if css_blocks > 15 else 0) >= 1 and css_blocks > 20 and not interact and js < 2
    )


def _validate_worker_draft(body: str, *, user_text: str = "", task: str = "") -> dict:
    """Per-draft validation gate (P0)."""
    s = (body or "").strip()
    issues: list[str] = []
    ok = True
    if len(s) < 40:
        ok = False
        issues.append("too_short")
    if s.startswith("Stub") or "Stub —" in s:
        ok = False
        issues.append("stub")
    if _wants_html_artifact(user_text, task):
        if not _html_complete(s):
            ok = False
            issues.append("incomplete_html")
        if "</html>" not in s.lower():
            issues.append("missing_html_close")
        # Soft preference: interactive UIs should not be CSS-only shells
        if _html_complete(s) and not _has_interaction(s):
            issues.append("no_interaction")
            # do not hard-fail pure static pages unless task asks interactive
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
    """Quality check of worker results — heuristic gates + DoD."""
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
