"""
V1 Orchestrator — real agent roles.

Default UX: brainstorm_turn (dialogue only).
Explicit execute: distill → flex → coordinator → workers → memory.
start() still runs full pipeline (tests / Telegram /do).
"""

from __future__ import annotations

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
        self._build_roles()

    def _build_roles(self) -> None:
        get = self.agents.get
        self.brainstorm = BrainstormAgent(get(AgentId.BRAINSTORM), self.bus, self.llm)
        self.flex = FlexAgent(get(AgentId.FLEX), self.bus, self.llm)
        self.coordinator = CoordinatorAgent(get(AgentId.COORDINATOR), self.bus, self.llm)
        self.worker1 = WorkerAgent(get(AgentId.WORKER1), self.bus, self.llm)
        self.worker2 = WorkerAgent(get(AgentId.WORKER2), self.bus, self.llm)
        self.memory = MemoryAgent(get(AgentId.MEMORY), self.bus, self.llm, memory=self.memory_store)
        self._workers = {
            "worker1": self.worker1,
            "worker2": self.worker2,
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

            mem = self._state.memory_context or self.memory.recall(text)
            self._state.memory_context = mem

            self._set_stage(PipelineStage.distill)
            reqs, question = self.coordinator.distill(text, notes, mem)
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
        except Exception as exc:  # noqa: BLE001
            self._fail(str(exc))
        return self._state

    def _run_flex_coord_workers(self) -> None:
        text = self._state.user_text
        mem = self._state.memory_context
        reqs = list(self._state.distilled_requirements)

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

        self._set_stage(PipelineStage.work)
        results: list[str] = []
        outputs: list[dict] = []
        for i, (wid, task) in enumerate(tasks, start=1):
            worker = self._workers.get(wid)
            if worker is None or not worker.enabled:
                continue
            result = worker.run(
                task,
                text,
                self._state.distilled_requirements,
                mem,
            )
            results.append(result)
            outputs.append(
                {
                    "worker": wid,
                    "name": worker.state.name,
                    "index": i,
                    "task": task,
                    "result": result,
                }
            )
            self.bus.emit(
                "pipeline.worker",
                {"worker": wid, "index": i, "result": result, "task": task},
            )
        self._state.worker_results = results
        self._state.worker_outputs = outputs
        self._finish()

    def _finish(self) -> None:
        self.memory.store(
            user_text=self._state.user_text,
            requirements=list(self._state.distilled_requirements),
            brainstorm=self._state.brainstorm_notes,
            flex_notes=self._state.flex_notes,
            results=list(self._state.worker_results),
        )
        self._set_stage(PipelineStage.done)
        self.bus.emit(
            "pipeline.done",
            {
                "requirements": list(self._state.distilled_requirements),
                "results": list(self._state.worker_results),
                "flex_notes": self._state.flex_notes,
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


Pipeline = Orchestrator
