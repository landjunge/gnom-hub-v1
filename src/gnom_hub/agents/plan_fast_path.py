"""Plan-mode fast path helpers (prod)."""

from __future__ import annotations


def resolve_plan_mode(
    plan_mode: str,
    user_text: str,
    requirements: list[str] | None = None,
) -> tuple[str, bool]:
    """
    Return (effective_mode, fast_path).

    default + page-like intent → full_page_html (skips multi-worker LLM split).
    Explicit modes pass through unchanged.
    Tool/browser drills never map to HTML modes.
    """
    mode = (plan_mode or "default").strip().lower() or "default"
    if mode == "team":
        return "team", False
    if mode in ("full_page_html", "plan_qa", "diagnosis"):
        return mode, mode == "full_page_html"
    if mode == "default" and _wants_one_html_page(user_text, requirements):
        return "full_page_html", True
    return mode, False


def _wants_one_html_page(
    user_text: str,
    requirements: list[str] | None = None,
) -> bool:
    """True when the task should be ONE single-file HTML page (prod fast path)."""
    return _html_page_score(user_text, requirements) >= 3


def _html_page_score(
    user_text: str,
    requirements: list[str] | None = None,
) -> int:
    """
    Weighted score for single-file HTML intent.
    Higher = stronger evidence for full_page_html fast path.
    Never returns a negative value.
    """
    parts = [user_text or ""]
    if requirements:
        parts.extend(str(r) for r in requirements if r)
    blob = "\n".join(parts).lower()
    if not blob.strip():
        return 0

    # Hard negatives – tool / live browser always win
    try:
        from gnom_hub.tools.agent_bridge import is_live_browser_task
        from gnom_hub.tools.tool_scenarios import is_tool_drill_task

        if is_tool_drill_task(user_text or "") or is_live_browser_task(user_text or ""):
            return 0
    except Exception:  # noqa: BLE001
        pass

    score = 0

    # Strong positives
    strong_positives = (
        ("html", 3),
        ("landingpage", 3),
        ("landing-page", 3),
        ("landing page", 3),
        ("single-file", 3),
        ("single file", 3),
        ("single-page", 3),
        ("single page", 3),
        ("one-page", 3),
        ("one page", 3),
        ("webseite", 2),
        ("website", 2),
        ("webpage", 2),
        ("web page", 2),
        ("homepage", 2),
        ("startseite", 2),
        ("frontend", 2),
        ("portfolio", 2),
        ("dashboard", 2),
        ("todo app", 2),
        ("todo-app", 2),
        ("checklist app", 2),
        ("web ui", 2),
        ("spa ", 2),
        (" pwa", 2),
        ("onepager", 3),
        ("one-pager", 3),
        ("one pager", 3),
        ("einzelne seite", 3),
        ("einzeldatei", 3),
    )
    for phrase, weight in strong_positives:
        if phrase in blob:
            score += weight

    # Medium positives (natural language / German)
    medium_positives = (
        ("baue die", 2),
        ("build a", 2),
        ("build me", 2),
        ("build an", 2),
        ("erstelle eine seite", 3),
        ("eine seite", 2),
        ("seite bauen", 3),
        ("seite erstellen", 3),
        ("mach mir eine seite", 3),
        ("zeig mir eine ui", 2),
        ("ui für", 2),
        ("frontend für", 2),
        ("eine seite mit", 2),
        ("hero", 1),
        ("feature cards", 1),
        ("feature grid", 1),
        ("html datei", 3),
        ("seite für", 2),
        ("landing für", 3),
        ("landingpage für", 3),
        ("webseite bauen", 3),
        ("webseite erstellen", 3),
        ("website bauen", 3),
        ("website erstellen", 3),
        ("mach eine seite", 3),
        ("bau mir", 2),
        ("baue mir", 2),
        ("create a page", 3),
        ("make a page", 3),
        ("make me a page", 3),
        ("landing page for", 3),
        ("dark theme landing", 3),
    )
    for phrase, weight in medium_positives:
        if phrase in blob:
            score += weight

    # Weak supporting signals
    if "seite" in blob:
        score += 1
    if any(x in blob for x in (" page", "page ", "page.", "page\n")):
        score += 1

    # Strong negatives (pull score down)
    strong_negatives = (
        ("multi-page", -5),
        ("multipage", -5),
        ("mehrere seiten", -5),
        ("several pages", -5),
        ("multiple pages", -5),
        ("separate pages", -4),
        ("backend only", -4),
        ("api only", -4),
        ("nur api", -4),
        ("microservices", -4),
        ("cli tool", -4),
        ("command line", -4),
        ("database schema only", -4),
        ("playwright", -3),
        ("tool drill", -5),
        ("tools testen", -4),
        ("computer_shell", -4),
        ("live browser", -5),
        ("navigiere zu", -4),
        ("öffne https", -4),
        ("oeffne https", -4),
        ("rest api", -3),
        ("openapi", -3),
        ("swagger", -3),
        ("unit test only", -3),
        ("nur tests", -3),
        ("refactor only", -3),
        ("nur refactor", -3),
        ("code review only", -3),
    )
    for phrase, weight in strong_negatives:
        if phrase in blob:
            score += weight

    return max(0, score)
