"""Coordinator, Worker, and Memory role agents."""

from __future__ import annotations

from typing import Any

from gnom_hub.agents.base import BaseAgent
from gnom_hub.agents.roles_helpers import (
    _is_flex_meta_requirement,
    _is_garbage_fact,
    _lines,
    _needs_clarify,
    _with_memory,
)
from gnom_hub.core.event_bus import EventBus
from gnom_hub.agents.plan_fast_path import _wants_one_html_page, resolve_plan_mode
from gnom_hub.pipeline.models import DistillQuestion


class CoordinatorAgent(BaseAgent):
    def distill(
        self, user_text: str, brainstorm: str, memory_ctx: str = ""
    ) -> tuple[list[str], DistillQuestion | None]:
        self.emit_active(True)
        try:
            reqs: list[str] | None = None
            if self.has_llm():
                try:
                    raw = self.ask(
                        system=(
                            "You are the Coordinator distilling the USER TASK into requirements. "
                            "Use the brainstorm dialogue as input. "
                            "Output ONLY 4–7 requirement lines for that task. No intro. "
                            "Prefer testable Definition-of-Done lines (observable behavior or "
                            "complete deliverable, e.g. full HTML with </html>). "
                            "Do not redefine Gnom-Hub. Match user language."
                        ),
                        user=_with_memory(
                            f"{user_text}\n\nBrainstorm dialogue:\n{brainstorm[:2500]}",
                            memory_ctx,
                        ),
                        max_tokens=400,
                        temperature=0.3,
                    )
                    reqs = _lines(raw) or [f"Ziel: {user_text}"]
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "distill", "error": str(exc)},
                    )
            if not reqs:
                reqs = [
                    f"Ziel: {user_text}",
                    "MVP mit 3 Kernfunktionen",
                    "Klare Desktop-UI und lesbare Ausgaben",
                    "Fehler- und Leerzustände behandeln",
                ]
            question = None
            if _needs_clarify(user_text, brainstorm):
                question = DistillQuestion(
                    id="q1",
                    text="MVP/schnell oder gründlich/robust?",
                    options=["MVP/schnell", "Gründlich/robust", "Egal", "Später"],
                )
            return reqs[:8], question
        finally:
            self.emit_active(False)

    def plan(
        self,
        user_text: str,
        requirements: list[str],
        worker_ids: list[str],
        plan_mode: str = "default",
    ) -> list[tuple[str, str]]:
        if not worker_ids:
            return []
        self.emit_active(True)
        try:
            mode = (plan_mode or "default").strip().lower()
            clean = [r for r in requirements if not _is_flex_meta_requirement(r)]
            effective, fast_path = resolve_plan_mode(mode, user_text, clean)
            self.last_plan_meta = {
                "plan_mode": effective,
                "fast_path": fast_path,
                "requested_mode": mode,
            }
            if effective == "full_page_html":
                return _html_full_page_plan(user_text, worker_ids, clean)
            if effective == "plan_qa":
                return _simple_task_plan(
                    user_text,
                    worker_ids,
                    clean,
                    (
                        "QA checklist + acceptance criteria for",
                        "Edge cases / failure modes for",
                        "Test plan (happy path + empty/error) for",
                        "Risks and open questions for",
                    ),
                )
            if effective == "diagnosis":
                return _simple_task_plan(
                    user_text,
                    worker_ids,
                    clean,
                    (
                        "Root-cause hypotheses for",
                        "Evidence checklist for",
                        "Minimal fix plan for",
                        "Regression risks for",
                    ),
                )
            if self.has_llm():
                try:
                    raw = self.ask(
                        system=(
                            "You are the Coordinator assigning tasks. "
                            "Output exactly one line per worker: workerN | task. "
                            "No other text."
                        ),
                        user=(
                            f"User: {user_text}\n"
                            f"Requirements:\n"
                            + "\n".join(f"- {r}" for r in requirements[:6])
                            + f"\nWorkers: {', '.join(worker_ids)}"
                        ),
                        max_tokens=300,
                        temperature=0.3,
                    )
                    tasks: list[tuple[str, str]] = []
                    for ln in raw.splitlines():
                        if "|" not in ln:
                            continue
                        left, right = ln.split("|", 1)
                        wid = left.strip().lower().replace(" ", "")
                        task = right.strip()
                        if wid in worker_ids and task:
                            tasks.append((wid, task))
                    if tasks:
                        return tasks[:4]
                except Exception as exc:  # noqa: BLE001
                    self.bus.emit(
                        "pipeline.warning",
                        {"stage": "coordinate", "error": str(exc)},
                    )
            return _simple_task_plan(
                user_text,
                worker_ids,
                clean,
                (
                    "Umsetzungsplan (Schritte) für",
                    "Konkretes Ergebnis-Artefakt für",
                    "Checkliste / QA für",
                    "Alternativen / Edge-Cases für",
                ),
            )
        finally:
            self.emit_active(False)


def _html_full_page_plan(
    user_text: str,
    worker_ids: list[str],
    clean: list[str],
) -> list[tuple[str, str]]:
    """Exactly one worker builds the page — no second page, no parallel HTML."""
    topic = (user_text or "").strip().rstrip(".")
    if not worker_ids:
        return []
    primary = (
        f"ONE complete single-file HTML page for: {topic}. "
        "Include ALL requested sections in the SAME file "
        "(hero/features/footer as applicable). "
        "<!DOCTYPE html> … </html>. Functions first, minimal CSS. "
        "At least one real interaction (onclick or addEventListener). "
        "You are the only worker for this deliverable — deliver the full page."
    )
    if clean:
        primary += "\nDoD:\n" + "\n".join(f"- {r}" for r in clean[:4])
    return [(worker_ids[0], primary)]


def _simple_task_plan(
    user_text: str,
    worker_ids: list[str],
    clean: list[str],
    prefixes: tuple[str, ...],
) -> list[tuple[str, str]]:
    """Deterministic non-HTML task lines (QA / diagnosis / stub default)."""
    topic = (user_text or "").strip().rstrip(".")
    templates = [f"{p}: {topic}" for p in prefixes]
    if clean and templates:
        templates[0] += "\n" + "\n".join(f"- {r}" for r in clean[:4])
    return [(wid, templates[i % len(templates)]) for i, wid in enumerate(worker_ids[:4])]


from gnom_hub.agents.roles_workers import MemoryAgent, WorkerAgent  # noqa: E402,F401
