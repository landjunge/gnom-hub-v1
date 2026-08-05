"""Pipeline package: plan orchestrator + state models."""

from __future__ import annotations

from typing import Any

from gnom_hub.pipeline.models import DistillQuestion, PipelineStage, PipelineState

__all__ = [
    "DistillQuestion",
    "Orchestrator",
    "Pipeline",
    "PipelineStage",
    "PipelineState",
]


def __getattr__(name: str) -> Any:
    # Lazy import avoids circular import agents.roles ↔ pipeline package
    if name in ("Pipeline", "Orchestrator"):
        from gnom_hub.pipeline.orchestrator import Orchestrator, Pipeline

        return Pipeline if name == "Pipeline" else Orchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
