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
    """
    mode = (plan_mode or "default").strip().lower() or "default"
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
    parts = [user_text or ""]
    if requirements:
        parts.extend(str(r) for r in requirements if r)
    blob = "\n".join(parts).lower()
    if not blob.strip():
        return False

    negatives = (
        "multi-page",
        "multipage",
        "mehrere seiten",
        "several pages",
        "multiple pages",
        "backend only",
        "api only",
        "nur api",
        "microservices",
        "separate pages",
        "cli tool",
        "command line",
        "database schema only",
    )
    if any(n in blob for n in negatives):
        return False

    positives = (
        "html",
        "landing",
        "landingpage",
        "landing-page",
        "webpage",
        "web page",
        "website",
        "webseite",
        "homepage",
        "single file",
        "single-file",
        "single page",
        "single-page",
        "one page",
        "one-page",
        "frontend",
        "portfolio",
        "dashboard",
        "todo app",
        "todo-app",
        "checklist app",
        "baue die",
        "build a",
        "build me",
        "build an",
        "erstelle eine seite",
        "eine seite",
        "web ui",
        "spa ",
        " pwa",
        "seite bauen",
        "seite erstellen",
    )
    if any(k in blob for k in positives):
        return True

    if "seite" in blob and any(
        x in blob for x in ("html", "web", "landing", "bau", "erstell", "page", "ui")
    ):
        return True
    if " page" in blob or "page " in blob or blob.startswith("page") or "page." in blob:
        return True
    return False
