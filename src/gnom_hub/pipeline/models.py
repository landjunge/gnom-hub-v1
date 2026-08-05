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
    options: list[str] = field(default_factory=lambda: ["Yes", "No", "Whatever", "Later"])


@dataclass
class PipelineState:
    stage: PipelineStage = PipelineStage.idle
    user_text: str = ""
    memory_context: str = ""
    brainstorm_notes: str = ""
    distilled_requirements: list[str] = field(default_factory=list)
    flex_notes: str = ""
    pending_question: DistillQuestion | None = None
    worker_results: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
