"""
Chat-derived agent policy for Gnom-Hub v1.

Lessons from live desk use (compress into agent behavior):
1. Live browser nav ≠ HTML page
2. Tool drill / Playwright / shell / GUI → real tools, never HTML team
3. Go-only ("mach das was ich gesagt habe") → prior concrete task
4. Flex = personal companion only (not designer/worker)
5. Workers: no token cap; tools via TOOL_CALL / forced scenarios
6. Landing/page HTML → ONE worker full single-file page (never multi half-pages)
7. Never invent tool results; tool_ensure if deps missing
"""

from __future__ import annotations


def _is_go_only_local(text: str) -> bool:
    """Mirror orchestrator go-only (no import cycle with pipeline)."""
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
    }
    if low in exact:
        return True
    vague = (
        "was ich gesagt",
        "what i said",
        "wie gesagt",
        "mach jetzt das",
        "do what i",
        "wie besprochen",
    )
    return any(v in low for v in vague) and len(low) < 80


def task_kind(text: str) -> str:
    """
    Classify user/task text for agent routing.

    Returns one of:
      tool_drill | browser_nav | html_page | go_only | diagnose | general
    """
    t = (text or "").strip()
    if not t:
        return "general"
    try:
        from gnom_hub.agents.plan_fast_path import _wants_one_html_page
        from gnom_hub.tools.agent_bridge import is_live_browser_task
        from gnom_hub.tools.tool_scenarios import is_tool_drill_task
    except Exception:  # noqa: BLE001
        return "general"

    if is_tool_drill_task(t):
        return "tool_drill"
    if is_live_browser_task(t):
        return "browser_nav"
    if _is_go_only_local(t):
        return "go_only"
    low = t.lower()
    # Natural language → tool drill (without magic "tool drill" phrase)
    if any(
        k in low
        for k in (
            "screenshot vom bildschirm",
            "bildschirm lesen",
            "was ist auf dem screen",
            "was ist auf dem bildschirm",
            "maus klicken",
            "tippe auf dem desktop",
            "shell ausführen",
            "terminal befehl",
            "installiere playwright",
            "install_tool",
            "git status",
            "dateien listen",
            "liste dateien in data",
        )
    ):
        return "tool_drill"
    if any(
        k in low
        for k in (
            "wo hakt",
            "bug",
            "fehler",
            "debug",
            "diagnos",
            "warum",
            "analys",
            "kaputt",
        )
    ):
        return "diagnose"
    if _wants_one_html_page(t):
        return "html_page"
    return "general"


def brainstorm_system_extra(kind: str) -> str:
    if kind == "tool_drill":
        return (
            "# Intent: TOOL DRILL\n"
            "- User will force real tools (Playwright/Shell/GUI).\n"
            "- DO NOT propose HTML landing or code dump.\n"
            "- 2–4 lines: which tools (browser_goto, computer_shell, inspect) and that Hub runs them now.\n"
            "- No „Soll ich umsetzen?“ — pipeline auto-executes tool scenarios.\n"
        )
    if kind == "browser_nav":
        return (
            "# Intent: LIVE BROWSER\n"
            "- User wants a real browser open/navigate — NOT a webpage artifact.\n"
            "- Confirm URL in one short line; Hub calls browser_open/browser_goto.\n"
            "- No HTML generation. No long plan.\n"
        )
    if kind == "go_only":
        return (
            "# Intent: GO-ONLY (mach das / was ich gesagt habe)\n"
            "- No new task invention. Prior concrete user task will be re-used.\n"
            "- One line: bestätigen, dass der letzte klare Auftrag ausgeführt wird.\n"
        )
    if kind == "html_page":
        return (
            "# Intent: HTML / LANDING\n"
            "- ONE worker builds ONE complete single-file HTML (not multi half-pages).\n"
            "- Mention modern effects once (glass/gradient/scroll-reveal) — no full code here.\n"
            "- Clear build order → no soft question when intent is clear (Hub executes).\n"
        )
    if kind == "diagnose":
        return (
            "# Intent: DIAGNOSE\n"
            "- Max 4 numbered points: UI / Keys / Workers-RESULT / Tools-GodMode.\n"
            "- No product rewrite of Gnom-Hub.\n"
        )
    return ""


def flex_line_for_kind(kind: str) -> str | None:
    """Optional short Flex co-pilot line by intent."""
    return {
        "tool_drill": "Flex: Tool-Pfad — Playwright/Shell/GUI, kein HTML-Ersatz.",
        "browser_nav": "Flex: Live-Browser — URL öffnen, keine Landing bauen.",
        "go_only": "Flex: Go-only — letzten klaren Auftrag ausführen, nicht neu erfinden.",
        "html_page": "Flex: Seite bauen — Team + moderne Effects, fertiges </html>.",
        "diagnose": "Flex: Diagnose zuerst — Execute erst bei klarem Fix-Auftrag.",
    }.get(kind)


def coordinator_distill_system(kind: str) -> str:
    base = (
        "You are the Coordinator distilling the USER TASK into requirements. "
        "Use the brainstorm dialogue as input. "
        "Output ONLY 4–7 requirement lines for that task. No intro. "
        "Do not redefine Gnom-Hub. Match user language.\n"
    )
    if kind == "tool_drill":
        return base + (
            "This is a TOOL DRILL. Requirements must be about calling real tools "
            "(tool_ensure, browser_goto, computer_shell, computer_inspect) and reporting results. "
            "NEVER require HTML pages or CSS.\n"
        )
    if kind == "browser_nav":
        return base + (
            "This is LIVE BROWSER navigation. Requirements: open URL, visible browser, "
            "confirm title/status. NEVER require generating a landing HTML file.\n"
        )
    if kind == "html_page":
        return base + (
            "Prefer testable DoD: full HTML with </html>, layout, modern effects, "
            "at least one JS interaction, user language.\n"
        )
    return base + (
        "Prefer testable Definition-of-Done lines (observable behavior or complete deliverable).\n"
    )


def coordinator_should_skip_clarify(kind: str) -> bool:
    return kind in ("tool_drill", "browser_nav", "go_only")


def tool_plan(
    user_text: str,
    worker_ids: list[str],
    clean: list[str],
    kind: str,
) -> list[tuple[str, str]]:
    """Deterministic worker tasks for tool/browser intents (one primary worker)."""
    if not worker_ids:
        return []
    wid = worker_ids[0]
    topic = (user_text or "").strip()
    dod = "\n".join(f"- {r}" for r in (clean or [])[:6])
    if kind == "browser_nav":
        task = (
            f"LIVE BROWSER: open/navigate for: {topic}\n"
            "Use tools: browser_open OR tool_ensure+browser_goto. "
            "Report method, URL, title/status. NO HTML file.\n" + (f"DoD:\n{dod}" if dod else "")
        )
        return [(wid, task)]
    if kind == "tool_drill":
        task = (
            f"TOOL DRILL (forced real tools) for: {topic}\n"
            "Call tools in order (TOOL_CALL or deterministic scenario):\n"
            "  tool_ensure → browser_goto/screenshot OR computer_shell OR computer_inspect\n"
            "Never invent results. Never ship HTML instead of tools.\n"
            + (f"DoD:\n{dod}" if dod else "")
        )
        return [(wid, task)]
    return []
