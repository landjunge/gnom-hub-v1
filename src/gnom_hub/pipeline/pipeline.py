"""Chat → Brainstorm → Distill → Flex → Coordinator → Worker(s) pipeline."""

from __future__ import annotations

import re
from typing import Any

from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline.models import DistillQuestion, PipelineStage, PipelineState

_FLEX_PROMPTS = {
    "security": (
        "You are a security reviewer. List short risks and constraints for the plan. Max 5 bullets."
    ),
    "researcher": (
        "You are a researcher. List missing facts and questions to investigate. Max 5 bullets."
    ),
    "neutral": ("You are a neutral reviewer. List trade-offs and open decisions. Max 5 bullets."),
}


class Pipeline:
    """
    Synchronous pipeline driven by EventBus.

    Without a live LLM key, stages use deterministic stubs.
    Disabled agents are skipped (Memory always on via memory_hint).
    """

    def __init__(
        self,
        bus: EventBus,
        llm_manager: Any | None = None,
        agent_manager: Any | None = None,
    ) -> None:
        self._bus = bus
        self._llm = llm_manager
        self._agents = agent_manager
        self._state = PipelineState()
        self._clarified_once = False

    @property
    def state(self) -> PipelineState:
        return self._state

    def start(self, user_text: str) -> PipelineState:
        """Begin a new run from chat text. Resets prior state."""
        self._state = PipelineState(user_text=user_text.strip())
        self._clarified_once = False
        try:
            self._run_from_brainstorm()
        except Exception as exc:  # noqa: BLE001 — surface as pipeline.error
            self._fail(str(exc))
        return self._state

    def answer_clarify(self, option: str) -> PipelineState:
        """Continue after Box-1 style clarify answer."""
        if self._state.stage != PipelineStage.clarify or self._state.pending_question is None:
            raise ValueError("No pending clarification question")

        answer = option.strip()
        q = self._state.pending_question
        self._state.distilled_requirements.append(f"Clarified ({q.id}): {answer}")
        self._state.pending_question = None
        self._clarified_once = True

        try:
            self._run_flex_then_work()
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    # ── internal stages ──────────────────────────────────────────────

    def _run_from_brainstorm(self) -> None:
        text = self._state.user_text
        if not text:
            self._fail("Empty user text")
            return

        if self._agent_enabled("brainstorm"):
            self._set_stage(PipelineStage.brainstorm)
            notes = self._stub_brainstorm(text) if self._use_stubs() else self._llm_brainstorm(text)
            self._state.brainstorm_notes = notes
            self._bus.emit("pipeline.brainstorm", {"notes": notes})

        self._set_stage(PipelineStage.distill)
        requirements, question = (
            self._stub_distill(text) if self._use_stubs() else self._llm_distill(text)
        )
        self._state.distilled_requirements = requirements
        self._bus.emit("pipeline.distill", {"requirements": list(requirements)})

        if question is not None and not self._clarified_once:
            self._state.pending_question = question
            self._set_stage(PipelineStage.clarify)
            self._bus.emit(
                "pipeline.question",
                {
                    "id": question.id,
                    "text": question.text,
                    "options": list(question.options),
                },
            )
            return

        self._run_flex_then_work()

    def _run_flex_then_work(self) -> None:
        if self._agent_enabled("flex"):
            self._set_stage(PipelineStage.flex)
            notes = self._stub_flex() if self._use_stubs() else self._llm_flex()
            self._state.flex_notes = notes
            self._bus.emit(
                "pipeline.flex",
                {"notes": notes, "preset": self._flex_preset()},
            )
            # Surface flex review as a soft requirement for workers
            if notes:
                self._state.distilled_requirements.append(f"Flex({self._flex_preset()}): {notes}")

        self._run_coordinate_and_work()

    def _run_coordinate_and_work(self) -> None:
        if not self._agent_enabled("coordinator"):
            self._bus.emit(
                "pipeline.coordinate",
                {"tasks": [], "skipped": True, "reason": "coordinator disabled"},
            )
            self._state.worker_results = []
            self._finish_with_memory([])
            return

        self._set_stage(PipelineStage.coordinate)
        tasks = self._stub_coordinate()
        self._bus.emit(
            "pipeline.coordinate",
            {"tasks": [{"worker": w, "task": t} for w, t in tasks]},
        )

        self._set_stage(PipelineStage.work)
        results: list[str] = []
        for i, (worker_id, task) in enumerate(tasks, start=1):
            if self._use_stubs():
                result = self._stub_worker(i, task)
            else:
                result = self._llm_worker(worker_id, task)
            results.append(result)
            self._bus.emit(
                "pipeline.worker",
                {"worker": worker_id, "index": i, "result": result, "task": task},
            )
        self._state.worker_results = results
        self._finish_with_memory(results)

    def _finish_with_memory(self, results: list[str]) -> None:
        self._bus.emit(
            "pipeline.memory_hint",
            {
                "user_text": self._state.user_text,
                "requirements": list(self._state.distilled_requirements),
                "results": list(results),
                "brainstorm_notes": self._state.brainstorm_notes,
                "flex_notes": self._state.flex_notes,
            },
        )
        self._set_stage(PipelineStage.done)
        self._bus.emit(
            "pipeline.done",
            {
                "requirements": list(self._state.distilled_requirements),
                "results": list(results),
                "flex_notes": self._state.flex_notes,
            },
        )

    # ── stubs ────────────────────────────────────────────────────────

    def _stub_brainstorm(self, text: str) -> str:
        base = f"Ideas for: {text}"
        if self._state.brainstorm_notes:
            return self._state.brainstorm_notes + "\n" + base
        return base

    def _stub_distill(self, text: str) -> tuple[list[str], DistillQuestion | None]:
        notes = self._state.brainstorm_notes
        requirements = [f"Fulfill: {text}"]
        if notes:
            requirements.append("Consider brainstorm notes")
        question: DistillQuestion | None = None
        if self._needs_clarify(text) and not self._clarified_once:
            question = DistillQuestion(
                id="q1",
                text="Is this request fully clear, or should we refine it?",
            )
        return requirements, question

    def _stub_flex(self) -> str:
        preset = self._flex_preset()
        reqs = "; ".join(self._state.distilled_requirements[:3]) or self._state.user_text
        if preset == "security":
            return f"[security] Review risks for: {reqs}"
        if preset == "researcher":
            return f"[researcher] Gaps to check: {reqs}"
        return f"[neutral] Trade-offs for: {reqs}"

    def _stub_coordinate(self) -> list[tuple[str, str]]:
        workers = self._enabled_worker_ids()
        reqs = self._state.distilled_requirements
        if not workers:
            return []
        tasks: list[tuple[str, str]] = []
        for i, wid in enumerate(workers[:2]):
            if reqs:
                task = reqs[i] if i < len(reqs) else reqs[0]
            else:
                task = self._state.user_text
            tasks.append((wid, task))
        return tasks

    @staticmethod
    def _stub_worker(n: int, task: str) -> str:
        return f"Worker {n} done: {task}"

    # ── LLM hooks ────────────────────────────────────────────────────

    def _agent_llm_kwargs(self, agent_id: str) -> dict[str, str]:
        out: dict[str, str] = {"agent": agent_id}
        if self._agents is None:
            return out
        try:
            agent = self._agents.get(agent_id)
        except (KeyError, ValueError):
            return out
        model = getattr(agent, "model", None)
        key = getattr(agent, "api_key", None)
        if model:
            out["model"] = str(model)
        if key:
            out["api_key"] = str(key)
        return out

    def _llm_brainstorm(self, text: str) -> str:
        from gnom_hub.llm.types import LLMMessage

        result = self._llm.chat(
            [
                LLMMessage(
                    role="system",
                    content="Brainstorm freely. Short bullet ideas only.",
                ),
                LLMMessage(role="user", content=text),
            ],
            **self._agent_llm_kwargs("brainstorm"),
        )
        return result.content

    def _llm_distill(self, text: str) -> tuple[list[str], DistillQuestion | None]:
        from gnom_hub.llm.types import LLMMessage

        context = text
        if self._state.brainstorm_notes:
            context = f"{text}\n\nBrainstorm notes:\n{self._state.brainstorm_notes}"
        result = self._llm.chat(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "Distill the user request into clear requirements. "
                        "Reply with one requirement per line, plain text."
                    ),
                ),
                LLMMessage(role="user", content=context),
            ],
            **self._agent_llm_kwargs("coordinator"),
        )
        lines = [ln.strip("-• \t") for ln in result.content.splitlines() if ln.strip()]
        requirements = lines or [f"Fulfill: {text}"]
        question: DistillQuestion | None = None
        if self._needs_clarify(text) and not self._clarified_once:
            question = DistillQuestion(
                id="q1",
                text="Is this request fully clear, or should we refine it?",
            )
        return requirements, question

    def _llm_flex(self) -> str:
        from gnom_hub.llm.types import LLMMessage

        preset = self._flex_preset()
        system = _FLEX_PROMPTS.get(preset, _FLEX_PROMPTS["neutral"])
        body = "\n".join(self._state.distilled_requirements) or self._state.user_text
        result = self._llm.chat(
            [
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=body),
            ],
            **self._agent_llm_kwargs("flex"),
        )
        return result.content

    def _llm_worker(self, worker_id: str, task: str) -> str:
        from gnom_hub.llm.types import LLMMessage

        result = self._llm.chat(
            [
                LLMMessage(
                    role="system",
                    content="You are a worker. Execute the task briefly. Plain text only.",
                ),
                LLMMessage(role="user", content=task),
            ],
            **self._agent_llm_kwargs(worker_id),
        )
        return result.content

    # ── helpers ──────────────────────────────────────────────────────

    def _flex_preset(self) -> str:
        if self._agents is None:
            return "security"
        try:
            agent = self._agents.get("flex")
            preset = getattr(agent, "preset", None) or "security"
            return str(preset)
        except (KeyError, ValueError):
            return "security"

    def _use_stubs(self) -> bool:
        if self._llm is None:
            return True
        has = getattr(self._llm, "has_provider", None)
        if callable(has):
            return not bool(has("deepseek"))
        return True

    def _agent_enabled(self, agent_id: str) -> bool:
        if self._agents is None:
            return True
        get = getattr(self._agents, "get", None)
        if callable(get):
            try:
                agent = get(agent_id)
                return bool(getattr(agent, "enabled", True))
            except (KeyError, ValueError):
                return True
        return True

    def _enabled_worker_ids(self) -> list[str]:
        if self._agents is None:
            return ["worker1", "worker2"]
        enabled_workers = getattr(self._agents, "enabled_workers", None)
        if callable(enabled_workers):
            out: list[str] = []
            for w in enabled_workers():
                wid = getattr(w, "id", w)
                out.append(wid.value if hasattr(wid, "value") else str(wid))
            return out
        ids = ["worker1", "worker2"]
        return [i for i in ids if self._agent_enabled(i)]

    @staticmethod
    def _needs_clarify(text: str) -> bool:
        if "?" in text:
            return True
        return bool(re.search(r"\bmaybe\b", text, flags=re.IGNORECASE))

    def _set_stage(self, stage: PipelineStage) -> None:
        self._state.stage = stage
        self._bus.emit("pipeline.stage", {"stage": stage.value})

    def _fail(self, message: str) -> None:
        self._state.stage = PipelineStage.error
        self._state.error = message
        self._bus.emit("pipeline.stage", {"stage": PipelineStage.error.value})
        self._bus.emit("pipeline.error", {"error": message})
