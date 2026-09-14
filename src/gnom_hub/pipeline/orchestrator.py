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
from gnom_hub.flex_desk import FlexDesk
from gnom_hub.pipeline.brainstorm import BrainstormMixin
from gnom_hub.pipeline.constants import ALLOWED_SEND_TARGETS, PipelineCancelled
from gnom_hub.pipeline.dispatch import DispatchMixin
from gnom_hub.pipeline.distill import DistillMixin
from gnom_hub.pipeline.flex import FlexMixin
from gnom_hub.pipeline.helpers import (
    _css_heavy_without_js,
    _definition_of_done,
    _format_turns,
    _has_interaction,
    _html_complete,
    _is_go_only,
    _is_topic_switch,
    _pick_execute_task,
    _prefetch_urls,
    _prefetch_worker_tools,
    _quality_check,
    _question_assignment_id,
    _validate_worker_draft,
    _wants_auto_execute,
    _wants_html_artifact,
    _worker_direct_too_big,
)
from gnom_hub.pipeline.models import PipelineStage, PipelineState
from gnom_hub.pipeline.persist import PersistMixin
from gnom_hub.pipeline.plan import PlanMixin
from gnom_hub.pipeline.worker import WorkerMixin

__all__ = [
    "ALLOWED_SEND_TARGETS",
    "Orchestrator",
    "Pipeline",
    "PipelineCancelled",
    "_css_heavy_without_js",
    "_definition_of_done",
    "_format_turns",
    "_has_interaction",
    "_html_complete",
    "_is_go_only",
    "_is_topic_switch",
    "_pick_execute_task",
    "_prefetch_urls",
    "_prefetch_worker_tools",
    "_quality_check",
    "_question_assignment_id",
    "_validate_worker_draft",
    "_wants_auto_execute",
    "_wants_html_artifact",
    "_worker_direct_too_big",
]


class Orchestrator(
    PersistMixin,
    WorkerMixin,
    DispatchMixin,
    PlanMixin,
    DistillMixin,
    FlexMixin,
    BrainstormMixin,
):
    def __init__(
        self,
        bus: EventBus,
        llm_manager: Any | None = None,
        agent_manager: AgentManager | None = None,
        memory: Any | None = None,
        tools: Any | None = None,
    ) -> None:
        self.bus = bus
        self.llm = llm_manager
        self.agents = agent_manager or AgentManager(bus)
        self.memory_store = memory
        self._tools = tools  # ToolRegistry — workers + prefetch/short-circuits
        self._state = PipelineState()
        self._clarified_once = False
        self.cancel_check: Callable[[], bool] | None = None
        self.plan_mode: str = "default"
        self._stage_t0: float | None = None
        self._stage_name: str | None = None
        self.flex_desk = FlexDesk()
        self._build_roles()

    @property
    def tools(self) -> Any | None:
        return self._tools

    @tools.setter
    def tools(self, value: Any | None) -> None:
        self._tools = value
        for w in getattr(self, "_workers", {}).values():
            w.tools = value

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
        tools = self.tools
        self.brainstorm = BrainstormAgent(get(AgentId.BRAINSTORM), self.bus, self.llm)
        self.flex = FlexAgent(get(AgentId.FLEX), self.bus, self.llm)
        self.coordinator = CoordinatorAgent(get(AgentId.COORDINATOR), self.bus, self.llm)
        self.worker1 = WorkerAgent(get(AgentId.WORKER1), self.bus, self.llm, tools=tools)
        self.worker2 = WorkerAgent(get(AgentId.WORKER2), self.bus, self.llm, tools=tools)
        self.worker3 = WorkerAgent(get(AgentId.WORKER3), self.bus, self.llm, tools=tools)
        self.worker4 = WorkerAgent(get(AgentId.WORKER4), self.bus, self.llm, tools=tools)
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

    def _open_assignment_id(self) -> str:
        """START-ID from the latest open Flex question (object or dict)."""
        open_qs = list(self.flex_desk.open_questions() or [])
        if not open_qs:
            return ""
        return _question_assignment_id(open_qs[-1])

    def _fail(self, message: str) -> None:
        self._close_stage_timing()
        self._state.stage = PipelineStage.error
        self._state.error = message
        self._state.result_status = "FEHLER"
        self.bus.emit("pipeline.stage", {"stage": PipelineStage.error.value})
        self.bus.emit(
            "pipeline.error",
            {
                "error": message,
                "stage_timings": dict(self._state.stage_timings),
            },
        )


Pipeline = Orchestrator
