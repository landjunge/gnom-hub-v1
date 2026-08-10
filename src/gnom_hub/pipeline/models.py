"""Pipeline stages and state models (v1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PipelineStage(str, Enum):
    idle = "idle"
    brainstorm = "brainstorm"
    distill = "distill"
    clarify = "clarify"
    flex = "flex"
    coordinate = "coordinate"
    work = "work"
    done = "done"
    error = "error"


@dataclass
class DistillQuestion:
    id: str
    text: str
    options: list[str] = field(
        default_factory=lambda: [
            "Schnell und einfach",
            "Gründlich und robust",
            "Egal — du entscheidest",
            "Später entscheiden",
        ]
    )


@dataclass
class PipelineState:
    stage: PipelineStage = PipelineStage.idle
    user_text: str = ""
    memory_context: str = ""
    brainstorm_notes: str = ""
    # Multi-turn brainstorm dialogue (user + agent)
    brainstorm_turns: list[dict] = field(default_factory=list)
    # True while user is collecting ideas; Execute switches to full run
    mode: str = "brainstorm"
    distilled_requirements: list[str] = field(default_factory=list)
    flex_notes: str = ""
    pending_question: DistillQuestion | None = None
    # Parked clarify answers (Later) — not zombies; user can resume later
    deferred_clarifies: list[dict] = field(default_factory=list)
    worker_results: list[str] = field(default_factory=list)
    worker_outputs: list[dict] = field(default_factory=list)
    # Light tool trace (prefetch / registry calls this run)
    tool_calls: list[dict] = field(default_factory=list)
    # Light quality notes after workers (plan §8)
    quality_notes: str = ""
    # Flex proactive corrections: [{agent, message, reason}] before user has to yell
    agent_nudges: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    # Per-stage wall times in milliseconds (prod observability)
    stage_timings: dict[str, float] = field(default_factory=dict)
    # Effective plan mode after fast-path resolution (may differ from hub plan_mode)
    resolved_plan_mode: str = ""
    # Weighted HTML-page intent score from plan_fast_path (observability)
    plan_html_score: int | None = None
    # Compact tool calls for desk (live + after done)
    # [{tool, ok, mode, agent?, scenario?}, ...]
    tool_log: list[dict] = field(default_factory=list)
