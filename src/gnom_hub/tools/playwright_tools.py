"""Playwright-backed browser automation for agents (headed Chromium)."""

from __future__ import annotations

from typing import Any

from gnom_hub.tools.browser_tools import normalize_url
from gnom_hub.tools.tool_install import ensure_package

_SESSION: dict[str, Any] = {}


def _ensure_pw() -> dict[str, Any]:
    return ensure_package("playwright", install_browsers=True)


def _get_page(headless: bool = False) -> tuple[Any, dict[str, Any]]:
    """Return (page, meta). Creates headed browser session if needed."""
    ens = _ensure_pw()
    if not ens.get("ok") and not ens.get("already"):
        # still try import if already present
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError(f"playwright unavailable: {ens.get('error') or exc}") from exc

    from playwright.sync_api import sync_playwright

    page = _SESSION.get("page")
    if page is not None:
        try:
            # touch page to see if still alive
            _ = page.url
            return page, {"reused": True, "ensure": ens}
        except Exception:  # noqa: BLE001
            _SESSION.clear()

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    _SESSION.update(
        {
            "pw": pw,
            "browser": browser,
            "context": context,
            "page": page,
        }
    )
    return page, {"reused": False, "ensure": ens, "headless": headless}


def browser_goto(
    url: str, *, headless: bool = False, wait: str = "domcontentloaded"
) -> dict[str, Any]:
    """Navigate headed (default) Chromium to URL; return title/status."""
    target = normalize_url(url)
    if not target:
        return {"ok": False, "error": "empty url"}
    try:
        page, meta = _get_page(headless=bool(headless))
        resp = page.goto(target, wait_until=wait or "domcontentloaded", timeout=60_000)
        title = page.title()
        return {
            "ok": True,
            "url": page.url,
            "title": title,
            "status": resp.status if resp else None,
            "method": "playwright",
            "meta": meta,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "url": target, "error": str(exc)}


def browser_screenshot(
    path: str = "",
    *,
    full_page: bool = False,
) -> dict[str, Any]:
    """Screenshot current Playwright page into data/computer_use/ or given path."""
    try:
        page = _SESSION.get("page")
        if page is None:
            return {"ok": False, "error": "no active page — call browser_goto first"}
        out = path.strip() if path else ""
        if not out:
            from gnom_hub.config.paths import project_root

            dest_dir = project_root() / "data" / "computer_use"
            dest_dir.mkdir(parents=True, exist_ok=True)
            out = str(dest_dir / "agent_browser.png")
        page.screenshot(path=out, full_page=bool(full_page))
        return {
            "ok": True,
            "path": out,
            "url": page.url,
            "title": page.title(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def browser_eval(js: str = "document.title") -> dict[str, Any]:
    """Evaluate short JS in the active page (read-only intent)."""
    expr = (js or "document.title").strip()
    if not expr or len(expr) > 500:
        return {"ok": False, "error": "js empty or too long"}
    # block obvious side-effecty patterns
    low = expr.lower()
    if any(x in low for x in ("fetch(", "xmlhttp", "eval(", "function(", "=>", "import(")):
        return {"ok": False, "error": "js expression blocked for safety"}
    try:
        page = _SESSION.get("page")
        if page is None:
            return {"ok": False, "error": "no active page — call browser_goto first"}
        val = page.evaluate(f"() => ({expr})")
        return {"ok": True, "result": val, "url": page.url}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
