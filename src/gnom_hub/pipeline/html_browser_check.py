"""Playwright check: worker HTML must load as a real page before GELIEFERT."""

from __future__ import annotations

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

PAGE_INCOMPLETE_MSG = "Worker konnte keine vollständige Seite liefern."

# Prefer controls that stay on the page; a[href] can navigate away.
_INTERACT_SELECTORS = (
    "button",
    "[onclick]",
    "input[type=button]",
    "input[type=submit]",
    "a[href]",
)


def browser_check_enabled() -> bool:
    v = os.getenv("GNOM_HTML_BROWSER_CHECK", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def verify_worker_html(
    html: str,
    *,
    interaction_required: bool = False,
    timeout_ms: int = 8000,
) -> dict[str, Any]:
    """Load worker HTML in Chromium. Never raises — returns a result dict."""
    from gnom_hub.export_ops import _extract_html_document
    from gnom_hub.pipeline.dod_gate import html_complete

    raw = (html or "").strip()
    doc = _extract_html_document(raw) or raw
    if not html_complete(doc):
        return {
            "ok": False,
            "skipped": False,
            "issues": ["incomplete_html"],
            "pageerrors": [],
            "screenshot": False,
        }
    if not browser_check_enabled():
        return {
            "ok": False,
            "skipped": True,
            "reason": "disabled",
            "issues": [],
            "pageerrors": [],
            "screenshot": False,
        }
    if not playwright_available():
        return {
            "ok": False,
            "skipped": True,
            "reason": "playwright_unavailable",
            "issues": [],
            "pageerrors": [],
            "screenshot": False,
        }
    return _run_playwright(doc, interaction_required=interaction_required, timeout_ms=timeout_ms)


def _chromium_executable_missing(exc: BaseException) -> bool:
    """True only when the browser binary is absent — not any Chromium launch error."""
    msg = str(exc).lower()
    return (
        "executable doesn't exist" in msg
        or "executable not found" in msg
        or "browser is not installed" in msg
        or "browsers are not installed" in msg
    )


def _run_playwright(doc: str, *, interaction_required: bool, timeout_ms: int) -> dict[str, Any]:
    """Always run Sync Playwright on a thread with no asyncio loop."""
    wait_s = max(30.0, (timeout_ms / 1000.0) + 20.0)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="gnom-html-pw") as pool:
        fut = pool.submit(
            _playwright_sync,
            doc,
            interaction_required=interaction_required,
            timeout_ms=timeout_ms,
        )
        try:
            return fut.result(timeout=wait_s)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "skipped": False,
                "issues": ["page_load_error"],
                "pageerrors": [],
                "screenshot": False,
                "error": str(exc)[:240],
            }


def _playwright_sync(doc: str, *, interaction_required: bool, timeout_ms: int) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    issues: list[str] = []
    errors: list[str] = []
    screenshot_ok = False
    structure = False
    launch_args: list[str] = []
    if os.getenv("CI") or os.getenv("GNOM_PW_NO_SANDBOX"):
        launch_args.append("--no-sandbox")
    try:
        with tempfile.TemporaryDirectory(prefix="gnom-html-gate-") as td:
            path = Path(td) / "page.html"
            path.write_text(doc, encoding="utf-8")
            url = path.resolve().as_uri()
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(headless=True, args=launch_args)
                except Exception as exc:  # noqa: BLE001
                    missing = _chromium_executable_missing(exc)
                    return {
                        "ok": False,
                        "skipped": missing,
                        "reason": "chromium_missing" if missing else "launch_error",
                        "issues": [] if missing else ["page_load_error"],
                        "pageerrors": [],
                        "screenshot": False,
                        "error": str(exc)[:240],
                    }
                try:
                    page = browser.new_page()
                    page.on("pageerror", lambda err: errors.append(str(err)))
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    if page.query_selector("html") is None:
                        issues.append("no_html")
                    if page.query_selector("body") is None:
                        issues.append("no_body")
                    text = ""
                    try:
                        text = page.inner_text("body") or ""
                    except Exception:  # noqa: BLE001
                        issues.append("no_body_text")
                    landmark = page.query_selector(
                        "header, main, h1, nav, footer, section, [role='main']"
                    )
                    structure = landmark is not None or len(text.strip()) >= 8
                    if not structure:
                        issues.append("no_main_structure")
                    if interaction_required:
                        target = None
                        for sel in _INTERACT_SELECTORS:
                            target = page.query_selector(sel)
                            if target is not None:
                                break
                        if target is None:
                            issues.append("no_interaction_target")
                        else:
                            try:
                                target.click(timeout=min(2000, timeout_ms))
                            except Exception:  # noqa: BLE001
                                issues.append("interaction_failed")
                    try:
                        shot = page.screenshot(type="png")
                        screenshot_ok = bool(shot and len(shot) > 32)
                    except Exception:  # noqa: BLE001
                        screenshot_ok = False
                    if not screenshot_ok:
                        issues.append("screenshot_failed")
                finally:
                    browser.close()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "skipped": False,
            "issues": ["page_load_error"],
            "pageerrors": errors[:8],
            "screenshot": False,
            "error": str(exc)[:240],
        }
    if errors:
        issues.append("pageerror")
    return {
        "ok": not issues,
        "skipped": False,
        "issues": issues,
        "pageerrors": errors[:8],
        "screenshot": screenshot_ok,
        "structure": structure,
    }


def attach_browser_checks(state: Any) -> None:
    """Fill ``browser_check`` on each HTML worker output (idempotent)."""
    from gnom_hub.pipeline.dod_gate import html_complete, interaction_required, wants_html_artifact

    outputs = getattr(state, "worker_outputs", None) or []
    if not outputs:
        return
    user_text = str(getattr(state, "user_text", "") or "")
    wants = wants_html_artifact(user_text)
    any_html = False
    for o in outputs:
        if isinstance(o, dict) and html_complete(str(o.get("result") or "")):
            any_html = True
            break
        if isinstance(o, dict) and "<html" in str(o.get("result") or "").lower():
            any_html = True
            break
    if not wants and not any_html:
        return
    for o in outputs:
        if not isinstance(o, dict):
            continue
        if isinstance(o.get("browser_check"), dict):
            continue
        body = str(o.get("result") or "")
        task = str(o.get("task") or "")
        if not html_complete(body):
            o["browser_check"] = {
                "ok": False,
                "skipped": False,
                "issues": ["incomplete_html"],
                "pageerrors": [],
                "screenshot": False,
            }
            continue
        need_ix = interaction_required(user_text, task)
        o["browser_check"] = verify_worker_html(body, interaction_required=need_ix)


def note_incomplete_page(state: Any) -> None:
    qn = (getattr(state, "quality_notes", None) or "").strip()
    if PAGE_INCOMPLETE_MSG in qn:
        return
    state.quality_notes = (qn + "\n" + PAGE_INCOMPLETE_MSG).strip() if qn else PAGE_INCOMPLETE_MSG


def _complete_html_browser_checks(state: Any) -> list[dict[str, Any]]:
    """Checks for complete HTML bodies only — fragments must not vote."""
    from gnom_hub.pipeline.dod_gate import html_complete

    checks: list[dict[str, Any]] = []
    for o in getattr(state, "worker_outputs", None) or []:
        if not isinstance(o, dict):
            continue
        bc = o.get("browser_check")
        if not isinstance(bc, dict):
            continue
        if "incomplete_html" in (bc.get("issues") or []):
            continue
        body = str(o.get("result") or o.get("body") or "")
        if not html_complete(body):
            continue
        checks.append(bc)
    return checks


def any_browser_ok(state: Any) -> bool:
    return any(c.get("ok") is True for c in _complete_html_browser_checks(state))


def all_browser_skipped(state: Any) -> bool:
    checks = _complete_html_browser_checks(state)
    return bool(checks) and all(bool(c.get("skipped")) for c in checks)
