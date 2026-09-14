"""Pure pipeline helpers (DoD wrappers, execute heuristics)."""

from __future__ import annotations

from typing import Any


def _question_assignment_id(q: Any) -> str:
    """FlexQuestion.assignment_id, or dict key if snapshot restored as dict."""
    if isinstance(q, dict):
        return str(q.get("assignment_id") or "")
    return str(getattr(q, "assignment_id", "") or "")


def _worker_direct_too_big(text: str) -> bool:
    t = (text or "").strip()
    low = t.lower()
    if len(t) > 360:
        return True
    keys = (
        "ganzes projekt",
        "alle dateien",
        "alle worker",
        "koordinier",
        "mehrere dateien",
        "umbauen",
    )
    return any(k in low for k in keys)


def _is_go_only(text: str) -> bool:
    """True when the message only means 'do it / execute prior task' — not a new task."""
    t = (text or "").strip()
    if not t:
        return False
    low = t.lower().strip(" !.。")
    exact = {
        "go",
        "los",
        "ok",
        "okay",
        "ja",
        "jap",
        "jo",
        "yes",
        "yep",
        "sure",
        "machs",
        "mach das",
        "mach es",
        "mach",
        "execute",
        "do it",
        "ja mach",
        "ja bitte",
        "bitte",
        "jetzt",
        "bau es",
        "bau das",
        "umsetzen",
        "setz um",
        "run it",
        "tu es",
        "ausführen",
        "ausfuehren",
        "jetzt ausführen",
        "jetzt ausfuehren",
        "pipeline starten",
        "starte execute",
        "start execute",
        "run execute",
        "flex execute",
        "los gehts",
        "los geht's",
        "do the plan",
        "create the plan",
        "plan erstellen",
        "erstell den plan",
        "erstelle den plan",
        "mach den plan",
        "ja erstell",
        "ja erstellen",
    }
    if low in exact:
        return True
    # "mach jetzt das was ich gesagt habe" / "do what i said"
    vague_do = (
        "was ich gesagt",
        "was ich gesagt habe",
        "what i said",
        "what i told",
        "wie gesagt",
        "das was ich",
        "mach jetzt das",
        "jetzt das was",
        "tu was ich",
        "do what i",
        "as i said",
        "wie besprochen",
    )
    if any(v in low for v in vague_do) and len(low) < 80:
        return True
    return bool(low.startswith(("ja ", "ok ", "okay ")) and len(low) < 24)


def _wants_auto_execute(text: str, turns: list[dict] | None = None) -> bool:
    from gnom_hub.agents.plan_fast_path import _wants_one_html_page
    from gnom_hub.tools.agent_bridge import is_live_browser_task

    t = (text or "").strip()
    if not t:
        return False
    # Live browser navigation must run tools without waiting for "ja/execute"
    if is_live_browser_task(t):
        return True
    from gnom_hub.tools.tool_scenarios import is_tool_drill_task

    if is_tool_drill_task(t):
        return True
    low = t.lower().strip(" !.。")

    users = [
        str(x.get("text") or "").strip()
        for x in (turns or [])
        if x.get("role") == "user" and str(x.get("text") or "").strip()
    ]
    if len(users) >= 2 and _is_go_only(t):
        return True

    if len(t) < 6:
        return False

    diagnose = (
        "wo hakt",
        "wo es hakt",
        "wo ist der fehler",
        "was ist mit",
        "warum",
        "erklär",
        "analys",
        "prüfe die pipeline",
        "only brainstorm",
        "nur brainstorm",
        "nur ideen",
        "ideen zu",
        "soll ich",
    )
    buildish = (
        "baue",
        "build",
        "html",
        "landing",
        "seite",
        "page",
        "implement",
        "erstelle",
        "mach mir",
        "todo",
    )
    if any(d in low for d in diagnose) and not any(b in low for b in buildish):
        return False
    if low.endswith("?") and not any(b in low for b in buildish):
        return False

    if _wants_one_html_page(t):
        return True
    triggers = (
        "baue ",
        "baue eine",
        "baue mir",
        "build a",
        "build me",
        "erstelle ",
        "create a",
        "implement ",
        "mach mir",
        "mach eine",
        "schreibe ",
        "schreib eine",
        "single-file",
        "single file",
        "landingpage",
        "landing page",
        "website",
        "todo app",
        "ausführen",
        "setz um",
        "umsetzen",
        "deliver",
        "fertig machen",
        "plan erstellen",
        "erstell den plan",
    )
    return any(k in low for k in triggers)


def _pick_execute_task(turns: list[dict], fallback: str = "") -> str:
    """
    Choose the real user task to execute — never a bare go-phrase.

    Priority (newest first): live browser nav → HTML page → long concrete line.
    """
    from gnom_hub.agents.plan_fast_path import _wants_one_html_page
    from gnom_hub.tools.agent_bridge import is_live_browser_task

    users = [
        str(t.get("text") or "").strip()
        for t in turns
        if t.get("role") == "user" and str(t.get("text") or "").strip()
    ]
    # Drop go-only chatter ("mach das", "was ich gesagt habe")
    real = [u for u in users if not _is_go_only(u)]
    if not real:
        fb = (fallback or "").strip()
        if fb and not _is_go_only(fb):
            return fb
        return users[-1] if users else fb

    for u in reversed(real):
        if is_live_browser_task(u):
            return u
    for u in reversed(real):
        if _wants_one_html_page(u):
            return u
    for u in reversed(real):
        if len(u) >= 48:
            return u
    return real[-1]


def _format_turns(turns: list[dict]) -> str:
    lines: list[str] = []
    for t in turns:
        role = str(t.get("role") or "")
        text = str(t.get("text") or "").strip()
        if not text:
            continue
        if role == "user":
            lines.append(f"You: {text}")
        elif role == "flex":
            lines.append(f"Flex:\n{text}")
        elif role == "brainstorm":
            lines.append(f"Brainstorm:\n{text}")
        else:
            lines.append(f"{role}:\n{text}")
        lines.append("")
    return "\n".join(lines).strip()


def _is_topic_switch(turns: list[dict], new_text: str) -> bool:
    new = (new_text or "").strip()
    if len(new) < 48:
        return False
    prior_users = [
        str(t.get("text") or "").strip()
        for t in turns
        if t.get("role") == "user" and str(t.get("text") or "").strip()
    ]
    if not prior_users:
        return False
    first = prior_users[0].lower()
    new_l = new.lower()
    a = {w for w in first.split() if len(w) > 2}
    b = {w for w in new_l.split() if len(w) > 2}
    if not a:
        return True
    overlap = len(a & b) / max(len(a), 1)
    if len(new) >= 80 and overlap < 0.28:
        return True
    deliverable = (
        "html",
        "landing",
        "website",
        "webpage",
        "web page",
        "build ",
        "create ",
        "make ",
        "implement ",
        "seite",
    )
    return (
        any(k in new_l for k in deliverable)
        and not any(k in first for k in deliverable)
        and overlap < 0.4
    )


def _prefetch_urls(blob: str, *, limit: int = 3) -> str:
    """Backward-compatible URL-only prefetch (tests may call this)."""
    return _prefetch_worker_tools(blob, max_urls=limit, max_tool_calls=limit)


def _prefetch_worker_tools(
    blob: str,
    *,
    bus: Any = None,
    tools: Any = None,
    memory: Any = None,
    max_urls: int = 3,
    max_tool_calls: int | None = None,
    record: list | None = None,
) -> str:
    from gnom_hub.tools.worker_prefetch import default_max_tool_calls, prefetch_for_workers

    cap = max_tool_calls if max_tool_calls is not None else default_max_tool_calls(blob or "")
    return prefetch_for_workers(
        blob,
        bus=bus,
        tools=tools,
        memory=memory,
        max_urls=max_urls,
        max_tool_calls=cap,
        record=record,
    )


def _definition_of_done(user_text: str, requirements: list[str]) -> str:
    from gnom_hub.pipeline.dod_gate import definition_of_done

    return definition_of_done(user_text, requirements)


def _wants_html_artifact(user_text: str, task: str = "") -> bool:
    from gnom_hub.pipeline.dod_gate import wants_html_artifact

    return wants_html_artifact(user_text, task)


def _html_complete(body: str) -> bool:
    from gnom_hub.pipeline.dod_gate import html_complete

    return html_complete(body)


def _has_interaction(body: str) -> bool:
    from gnom_hub.pipeline.dod_gate import has_interaction

    return has_interaction(body)


def _css_heavy_without_js(body: str) -> bool:
    from gnom_hub.pipeline.dod_gate import css_heavy_without_js

    return css_heavy_without_js(body)


def _validate_worker_draft(
    body: str,
    *,
    user_text: str = "",
    task: str = "",
    requirements: list[str] | None = None,
    tool_calls: list | None = None,
) -> dict:
    """Automated DoD gate (delegates to gnom_hub.pipeline.dod_gate)."""
    from gnom_hub.pipeline.dod_gate import validate_worker_draft

    return validate_worker_draft(
        body,
        user_text=user_text,
        task=task,
        requirements=requirements,
        tool_calls=tool_calls,
    )


def _quality_check(
    user_text: str,
    requirements: list[str],
    outputs: list[dict],
) -> str:
    if not outputs:
        return "Quality: no worker outputs."
    lines: list[str] = ["Quality check (gates + DoD):"]
    task_low = (user_text or "").lower()
    fail_n = 0
    for out in outputs:
        name = str(out.get("name") or out.get("worker") or "worker")
        body = str(out.get("result") or "").strip()
        gate = out.get("validation") or _validate_worker_draft(
            body,
            user_text=user_text,
            task=str(out.get("task") or ""),
            requirements=requirements,
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
