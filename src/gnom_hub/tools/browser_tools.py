"""Live browser helpers for agent tool use (God-Mode gated via caller)."""

from __future__ import annotations

import platform
import re
import subprocess
from typing import Any
from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if not re.match(r"^https?://", u, re.IGNORECASE):
        u = "https://" + u.lstrip("/")
    # strip trailing punctuation from chat paste
    return u.rstrip(".,;:)\\]\"'")


def extract_urls(text: str) -> list[str]:
    found = re.findall(r"https?://[^\s\]\)\"'<>]+", text or "")
    out: list[str] = []
    seen: set[str] = set()
    for raw in found:
        u = normalize_url(raw)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    # bare domains mentioned with navigate intent
    if not out:
        m = re.search(
            r"\b((?:[a-z0-9-]+\.)+(?:com|ai|io|org|net|de|app))\b",
            (text or "").lower(),
        )
        if m:
            out.append(normalize_url(m.group(1)))
    # brand without TLD
    if not out and "kleinanzeigen" in (text or "").lower():
        out.append(normalize_url("https://www.kleinanzeigen.de"))
    return out


def browser_open_url(url: str) -> dict[str, Any]:
    """
    Open URL in a visible browser (macOS `open`, else Playwright headed Chromium).
    """
    target = normalize_url(url)
    if not target:
        return {"ok": False, "error": "empty url"}
    parsed = urlparse(target)
    if parsed.scheme not in ("http", "https"):
        return {"ok": False, "error": f"unsupported scheme: {parsed.scheme!r}"}

    # 1) OS open (visible default browser) — preferred on macOS
    system = platform.system()
    try:
        if system == "Darwin":
            proc = subprocess.run(
                ["open", target],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if proc.returncode == 0:
                return {
                    "ok": True,
                    "method": "open",
                    "url": target,
                    "detail": "opened in default browser (visible)",
                }
            err = (proc.stderr or proc.stdout or "").strip()
            return {
                "ok": False,
                "method": "open",
                "url": target,
                "error": err or f"open exit={proc.returncode}",
            }
        if system == "Linux":
            proc = subprocess.run(
                ["xdg-open", target],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if proc.returncode == 0:
                return {
                    "ok": True,
                    "method": "xdg-open",
                    "url": target,
                    "detail": "opened via xdg-open",
                }
    except Exception as exc:  # noqa: BLE001
        os_err = str(exc)
    else:
        os_err = ""

    # 2) Playwright headed fallback (real Chromium window)
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(target, wait_until="domcontentloaded", timeout=60_000)
            title = page.title()
            # Keep window open — user wants to see navigation
            # Do not close browser; detach by not using context manager close...
            # Actually exiting `with` closes. Launch without context manager:
        # reopen properly
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        resp = page.goto(target, wait_until="domcontentloaded", timeout=60_000)
        title = page.title()
        status = resp.status if resp else None
        # Leave browser open: stop holding reference but process stays until user closes
        # Playwright keeps process alive while browser object exists — store on module
        _keep_alive(pw, browser)
        return {
            "ok": True,
            "method": "playwright",
            "url": target,
            "title": title,
            "status": status,
            "detail": "opened headed Chromium (left open)",
            "os_fallback_error": os_err or None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "url": target,
            "error": f"browser_open failed: {exc}",
            "os_error": os_err or None,
        }


_ALIVE: list[Any] = []


def _keep_alive(*objs: Any) -> None:
    """Prevent GC from closing headed Playwright browser immediately."""
    _ALIVE.append(objs)
    # keep last 3 sessions only
    while len(_ALIVE) > 3:
        old = _ALIVE.pop(0)
        try:
            for o in old:
                close = getattr(o, "close", None) or getattr(o, "stop", None)
                if callable(close):
                    close()
        except Exception:  # noqa: BLE001
            pass
