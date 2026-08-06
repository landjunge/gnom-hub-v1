"""Orchestrator: Pipeline subclass with per-stage timing instrumentation."""

from __future__ import annotations

import re
import time
from typing import Any

from gnom_hub.pipeline.models import PipelineStage
from gnom_hub.pipeline.pipeline import (
    _GO_WORDS,
    Pipeline,
    _format_turns,
    _is_topic_switch,
    _pick_execute_task,
    _wants_auto_execute,
)

# Re-export Pipeline so callers can do:  from gnom_hub.pipeline.orchestrator import Pipeline
__all__ = [
    "_GO_WORDS",
    "Orchestrator",
    "Pipeline",
    "_definition_of_done",
    "_format_turns",
    "_has_interaction",
    "_html_complete",
    "_is_topic_switch",
    "_pick_execute_task",
    "_prefetch_urls",
    "_quality_check",
    "_validate_worker_draft",
    "_wants_auto_execute",
]

# ── module-level helpers (also used by regression tests) ─────────────────────


def _html_complete(html: str) -> bool:
    """Return True when *html* looks like a structurally complete HTML document."""
    low = html.lower()
    return "</html>" in low or ("</body>" in low and "<html" in low)


def _has_interaction(html: str) -> bool:
    """Return True when *html* contains interactive elements."""
    low = html.lower()
    return any(
        token in low
        for token in ("onclick", "onsubmit", "onchange", "href=", "<button", "<input", "<form")
    )


def _definition_of_done(user_text: str, requirements: list[str]) -> str:
    """Build a DoD string from requirements, keeping Flex-wish lines, stripping meta."""
    from gnom_hub.agents.roles_helpers import _is_flex_meta_requirement

    lines: list[str] = []
    for req in requirements:
        if req.startswith("Flex-wish:"):
            # Keep only the wish content after "User:" prefix
            wish = req.removeprefix("Flex-wish:").strip()
            if wish.startswith("User:"):
                wish = wish.removeprefix("User:").strip()
            if wish:
                lines.append(wish)
        elif not _is_flex_meta_requirement(req):
            lines.append(req)
    body = "\n".join(lines)
    return f"DEFINITION OF DONE\n{body}".strip()


def _validate_worker_draft(html: str, user_text: str = "", task: str = "") -> dict[str, object]:
    issues: list[str] = []
    low_task = (task or "").lower()
    is_html_task = any(x in low_task for x in ("html", "page", "web", "site", "landing"))
    if is_html_task:
        if not _html_complete(html):
            issues.append("incomplete HTML (missing closing tags)")
        if not _has_interaction(html):
            issues.append("no interactive elements")
    return {"ok": len(issues) == 0, "issues": issues}


def _quality_check(
    user_text: str,
    requirements: list[str],
    worker_results_dicts: list[dict],
) -> str:
    lines = ["Quality", "Gates:"]
    for w in worker_results_dicts:
        validation = w.get("validation") or {}
        ok = bool(validation.get("ok", True))
        name = w.get("name", "?")
        lines.append(f"  {name}: {'✓' if ok else '✗ ' + ', '.join(validation.get('issues', []))}")
    return "\n".join(lines)


def _prefetch_urls(text: str) -> str:
    urls = re.findall(r"https?://\S+", text or "")
    if not urls:
        return ""
    return ""


class Orchestrator(Pipeline):
    """Pipeline with stage-timing helpers used by plan-fast-path tests."""

    def __init__(
        self,
        bus: Any,
        llm_manager: Any | None = None,
        agent_manager: Any | None = None,
        memory: Any | None = None,
    ) -> None:
        super().__init__(bus, llm_manager, agent_manager, memory)
        self._stage_t0: float | None = None
        self._stage_name: str | None = None

    @property
    def coordinator(self):
        if not hasattr(self, "_coordinator"):
            from gnom_hub.agents.models import COLORS, AgentId, AgentState
            from gnom_hub.agents.roles_ext import CoordinatorAgent

            st = AgentState(
                id=AgentId.COORDINATOR,
                name="Coordinator",
                role="coordinator",
                color=COLORS[AgentId.COORDINATOR],
                enabled=True,
                toggleable=True,
            )
            self._coordinator = CoordinatorAgent(st, self._bus, llm=None)
        return self._coordinator

    # ── timing helpers ────────────────────────────────────────────────

    def _begin_stage_timing(self, stage_name: str) -> None:
        """Start a timing window for *stage_name*."""
        self._stage_name = stage_name
        self._stage_t0 = time.monotonic()

    def _close_stage_timing(self) -> None:
        """Close the current timing window and record elapsed seconds."""
        if self._stage_t0 is None or self._stage_name is None:
            return
        elapsed = time.monotonic() - self._stage_t0
        self._state.stage_timings[self._stage_name] = elapsed
        self._bus.emit("pipeline.stage_timing", {"stage": self._stage_name, "elapsed": elapsed})
        self._stage_t0 = None
        self._stage_name = None

    def _set_stage(self, stage: PipelineStage) -> None:
        """Advance the pipeline stage, closing any open timing window first."""
        self._close_stage_timing()
        super()._set_stage(stage)
