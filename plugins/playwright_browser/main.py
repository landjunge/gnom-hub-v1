"""Plugin: Playwright browser automation (goto/click/fill/screenshot)."""

from __future__ import annotations

from typing import Any

DEFAULT_URL = "https://www.kleinanzeigen.de"


def pw_goto(url: str = "", headless: bool = False) -> dict[str, Any]:
    target = (url or "").strip() or DEFAULT_URL
    try:
        from gnom_hub.tools.playwright_tools import browser_goto

        return browser_goto(target, headless=bool(headless))
    except Exception as exc:  # noqa: BLE001
        # self-heal playwright then retry once
        try:
            from gnom_hub.tools.tool_install import ensure_package

            ensure_package("playwright", install_browsers=True)
            from gnom_hub.tools.playwright_tools import browser_goto

            return browser_goto(target, headless=bool(headless))
        except Exception as exc2:  # noqa: BLE001
            return {"ok": False, "error": f"{exc}; retry: {exc2}", "url": target}


def pw_click(selector: str = "") -> dict[str, Any]:
    sel = (selector or "").strip()
    if not sel:
        return {"ok": False, "error": "selector required"}
    try:
        from gnom_hub.tools import playwright_tools as pw

        page = pw._SESSION.get("page")
        if page is None:
            return {"ok": False, "error": "no active page — call pw_goto first"}
        page.click(sel, timeout=15_000)
        return {"ok": True, "selector": sel, "url": page.url}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "selector": sel}


def pw_fill(selector: str = "", text: str = "") -> dict[str, Any]:
    sel = (selector or "").strip()
    if not sel:
        return {"ok": False, "error": "selector required"}
    try:
        from gnom_hub.tools import playwright_tools as pw

        page = pw._SESSION.get("page")
        if page is None:
            return {"ok": False, "error": "no active page — call pw_goto first"}
        page.fill(sel, str(text or ""), timeout=15_000)
        return {"ok": True, "selector": sel, "chars": len(str(text or "")), "url": page.url}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "selector": sel}


def pw_screenshot(path: str = "") -> dict[str, Any]:
    try:
        from gnom_hub.tools.playwright_tools import browser_screenshot

        return browser_screenshot(str(path or ""))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
