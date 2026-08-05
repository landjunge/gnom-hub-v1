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
            )
            if not continuing:
                self._state = PipelineState(user_text=text, mode="brainstorm")
            else:
                self._state.mode = "brainstorm"
                self._state.error = None
                self._state.worker_results = []
                self._state.worker_outputs = []
                self._state.distilled_requirements = []
                self._state.flex_notes = ""
                self._state.pending_question = None

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
            if not history:
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
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def execute(self) -> PipelineState:
        """Distill + run workers from accumulated brainstorm."""
        try:
            text = (self._state.user_text or "").strip()
            if not text and self._state.brainstorm_turns:
                for t in self._state.brainstorm_turns:
                    if t.get("role") == "user" and str(t.get("text") or "").strip():
                        text = str(t["text"]).strip()
                        self._state.user_text = text
                        break
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
                first = notes.strip().splitlines()[0][:160]
                preset = self.flex.state.preset or "security"
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
        tasks = self.coordinator.plan(text, self._state.distilled_requirements, worker_ids)
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
            task_full = f"{task}\n\n{dod}".strip()
            result = worker.run(
                task_full,
                text,
                self._state.distilled_requirements,
                mem,
            )
            # Soft retry: incomplete HTML or interactive task without handlers
            gate0 = _validate_worker_draft(result, user_text=text, task=task)
            need_retry = False
            retry_why = ""
            if _wants_html_artifact(text, task) and not _html_complete(result):
                need_retry, retry_why = True, "incomplete_html"
            elif "missing_required_interaction" in (gate0.get("issues") or []):
                need_retry, retry_why = True, "missing_interaction"
            if need_retry:
                self.bus.emit(
                    "pipeline.quality_retry",
                    {"worker": wid, "reason": retry_why},
                )
                self._check_cancel()
                hint = (
                    "RETRY (mandatory): ONE complete HTML file "
                    "<!DOCTYPE html>…</html>. "
                    "PRIORITY: structure + working JS interactions FIRST, "
                    "minimal CSS only. Empty/error states only after functions. "
                    "Must include at least one onclick= or addEventListener. "
                    "Never truncate mid-CSS. Finish with </html>."
                )
                result = worker.run(
                    task_full + "\n\n" + hint,
                    text,
                    self._state.distilled_requirements,
                    mem,
                )
            gate = _validate_worker_draft(result, user_text=text, task=task)
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
        self._finish()

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
    blob = f"{user_text or ''} {task or ''}".lower()
    keys = (
        "html",
        "landing",
        "webpage",
        "web page",
        "css",
        "frontend",
        "seite",
        "website",
        "ui page",
        "single file",
    )
    return any(k in blob for k in keys)


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
