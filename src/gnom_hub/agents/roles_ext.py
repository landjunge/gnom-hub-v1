"""Coordinator, Worker, and Memory role agents."""

from __future__ import annotations

from gnom_hub.agents.base import BaseAgent
from gnom_hub.agents.plan_fast_path import _html_page_score, resolve_plan_mode
from gnom_hub.agents.roles_helpers import (
    _is_flex_meta_requirement,
    _lines,
    _needs_clarify,
    _with_memory,
)
from gnom_hub.pipeline.models import DistillQuestion


class CoordinatorAgent(BaseAgent):
    def distill(
        self, user_text: str, brainstorm: str, memory_ctx: str = ""
    ) -> tuple[list[str], DistillQuestion | None]:
        self.emit_active(True)
        try:
            from gnom_hub.agents.chat_policy import (
                coordinator_distill_system,
                coordinator_should_skip_clarify,
                task_kind,
            )

            kind = task_kind(user_text)
            reqs: list[str] | None = None

            # Deterministic reqs for tool/browser — no LLM inventing HTML DoD
            if kind == "tool_drill":
                reqs = [
                    f"Ziel: {user_text}",
                    "Echte Tools aufrufen (kein HTML-Ersatz)",
                    "tool_ensure wenn Deps fehlen",
                    "Playwright und/oder Shell und/oder GUI je nach Szenario",
                    "Ergebnisse der Tools wörtlich berichten",
                ]
            elif kind == "browser_nav":
                reqs = [
                    f"Ziel: {user_text}",
                    "Live-Browser öffnen/navigieren",
                    "URL sichtbar, Methode + Status melden",
                    "Kein HTML-Artefakt erzeugen",
                ]

            if reqs is None and self.has_llm():
                try:
                    raw = self.ask(
                        system=coordinator_distill_system(kind),
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
            if not coordinator_should_skip_clarify(kind) and _needs_clarify(user_text, brainstorm):
                # Plain German — Box 1 must be understandable without jargon
                question = DistillQuestion(
                    id="q1",
                    text="Wie soll ich vorgehen?",
                    options=[
                        "Schnell und einfach",
                        "Gründlich und robust",
                        "Egal — du entscheidest",
                        "Später entscheiden",
                    ],
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
            from gnom_hub.agents.chat_policy import task_kind, tool_plan

            kind = task_kind(user_text)
            mode = (plan_mode or "default").strip().lower()
            clean = [r for r in requirements if not _is_flex_meta_requirement(r)]
            # Tool/browser never go through HTML team plans
            if kind in ("tool_drill", "browser_nav"):
                planned = tool_plan(user_text, worker_ids, clean, kind)
                self.last_plan_meta = {
                    "plan_mode": kind,
                    "fast_path": True,
                    "requested_mode": mode,
                    "task_kind": kind,
                    "html_score": 0,
                }
                return planned
            effective, fast_path = resolve_plan_mode(mode, user_text, clean)
            html_score = _html_page_score(user_text, clean)
            self.last_plan_meta = {
                "plan_mode": effective,
                "fast_path": fast_path,
                "requested_mode": mode,
                "task_kind": kind,
                "html_score": html_score,
            }
            if effective == "full_page_html":
                return _html_full_page_plan(user_text, worker_ids, clean)
            if effective == "team":
                # Multi-agent: research / plan / implement — never single-worker shortcut
                return _team_html_landing_plan(user_text, worker_ids, clean)
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
                    # Only force multi-worker HTML split when plan_mode is explicitly team.
                    # Otherwise prefer single-worker full pages (coord quality / no section-split).
                    teamish = effective == "team"
                    sys = (
                        "You are the Coordinator designing a work plan. "
                        "Output exactly one line per worker: workerN | task. "
                        "No other text. "
                    )
                    if teamish:
                        sys += (
                            "MUST use at least 2 different workers when available. "
                            "Split: (1) research+IA+effects brief, "
                            "(2) full single-file HTML with modern effects, "
                            "(3) optional polish/a11y. "
                            "Never assign only one worker for a full landing page."
                        )
                    else:
                        sys += (
                            "Prefer a single clear concrete task on worker1 when the user "
                            "wants a page/UI/landing. Only split across workers for clearly "
                            "independent non-HTML workstreams (research vs implement is OK "
                            "only if plan_mode is team)."
                        )
                    raw = self.ask(
                        system=sys,
                        user=(
                            f"User: {user_text}\n"
                            f"Requirements:\n"
                            + "\n".join(f"- {r}" for r in requirements[:8])
                            + f"\nWorkers: {', '.join(worker_ids)}"
                        ),
                        max_tokens=500,
                        temperature=0.35,
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
            if effective == "team":
                return _team_html_landing_plan(user_text, worker_ids, clean)
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
        f"Produce ONE complete, self-contained single-file HTML document for: {topic}.\n"
        "Hard requirements:\n"
        "1. Output starts with <!DOCTYPE html> and MUST end with a real </html> — never truncate.\n"
        "2. ALL sections (hero, features, footer, CTA …) live in the SAME file.\n"
        "3. Strong visual design: dark product UI preferred, CSS grid/flex, gradients or glass, "
        "at least one motion/effect that respects prefers-reduced-motion.\n"
        "4. At least one real user interaction (onclick or addEventListener).\n"
        "5. Semantic HTML, readable contrast, viewport meta; no lorem if product facts exist.\n"
        "Priority: complete structure → working interaction → design polish.\n"
        "If approaching token limit: close the HTML properly rather than leave open tags."
    )
    if clean:
        primary += "\nBinding DoD (must satisfy):\n" + "\n".join(f"- {r}" for r in clean[:8])
    return [(worker_ids[0], primary)]


def _team_html_landing_plan(
    user_text: str,
    worker_ids: list[str],
    clean: list[str],
) -> list[tuple[str, str]]:
    """
    Explicit multi-worker plan for high-quality landings:
    research/IA → full HTML with modern effects → optional polish.
    """
    topic = (user_text or "").strip().rstrip(".")
    if not worker_ids:
        return []
    dod = "\n".join(f"- {r}" for r in (clean or [])[:8])
    wids = list(worker_ids[:3])
    tasks: list[tuple[str, str]] = []
    # Worker A: research + team brief (structure + effects checklist)
    tasks.append(
        (
            wids[0],
            (
                f"TEAM PLAN / RESEARCH brief for: {topic}\n"
                "Output a structured German markdown brief (no full HTML file):\n"
                "1) Information architecture (6 sections max)\n"
                "2) Core message (1 sentence)\n"
                "3) Content bullets from product facts (README)\n"
                "4) Modern single-file effects checklist 2025/26 "
                "(gradient mesh, glass header backdrop-filter, scroll-reveal "
                "IntersectionObserver, CSS grid, micro-interactions, "
                "prefers-reduced-motion)\n"
                "5) Acceptance criteria for the implementer\n"
                + (f"\nRequirements:\n{dod}" if dod else "")
            ),
        )
    )
    # Worker B: implement the full page using the brief intent
    implementer = wids[1] if len(wids) > 1 else wids[0]
    tasks.append(
        (
            implementer,
            (
                f"IMPLEMENT complete single-file HTML landing for: {topic}\n"
                "Use product facts + a modern effects stack (not a bare dark box).\n"
                "MUST include: sticky glass header, hero with CTA, feature cards grid, "
                "pipeline section, audience section, quickstart, footer with version.\n"
                "MUST include CSS: gradients, backdrop-filter or soft blur, "
                "@keyframes or scroll-reveal via IntersectionObserver, "
                "prefers-reduced-motion media query.\n"
                "MUST include JS interaction (tabs/copy/theme/nav).\n"
                "DE UI texts. ONE file <!DOCTYPE html> … </html>. Never truncate.\n"
                + (f"\nDoD:\n{dod}" if dod else "")
            ),
        )
    )
    if len(wids) > 2 and implementer != wids[0]:
        tasks.append(
            (
                wids[2],
                (
                    f"POLISH / QA pass notes for the landing about: {topic}\n"
                    "List visual upgrades and a11y checks; if you produce HTML, "
                    "it must be a complete improved single file ending with </html>."
                ),
            )
        )
    return tasks


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


from gnom_hub.agents.roles_workers import MemoryAgent, WorkerAgent  # noqa: F401
