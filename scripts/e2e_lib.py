"""Shared helpers for Playwright + Gnom hub E2E (real browser / tools)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def http_json(
    base: str,
    method: str,
    path: str,
    body: dict | None = None,
    *,
    timeout: float = 120.0,
) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def http_ok(base: str, path: str = "/api/health", timeout: float = 5.0) -> dict[str, Any] | None:
    try:
        return http_json(base, "GET", path, timeout=timeout)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def poll_job(base: str, job_id: str, *, max_s: float = 300.0) -> dict[str, Any]:
    deadline = time.time() + max_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = http_json(base, "GET", f"/api/jobs/{job_id}", timeout=30)
        if last.get("status") in ("done", "error", "clarify", "cancelled"):
            return last
        time.sleep(0.45)
    raise TimeoutError(f"job {job_id} timeout status={last.get('status')}")


def api_reset(base: str) -> None:
    try:
        http_json(base, "POST", "/api/reset", {}, timeout=20)
    except Exception:
        pass


def api_clean(base: str) -> None:
    """HOT + temp + pipeline; WARM kept."""
    try:
        http_json(base, "POST", "/api/clean", {}, timeout=20)
    except Exception:
        pass


class StepLog:
    def __init__(self) -> None:
        self.steps: list[dict[str, Any]] = []

    def add(self, name: str, **kw: Any) -> None:
        self.steps.append({"step": name, "t": time.time(), **kw})
        detail = kw.get("detail") or kw.get("status") or "ok"
        print(f"  · {name}: {detail}")


def shot(page: Any, run_dir: Path, name: str) -> str:
    path = run_dir / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path.name


def wait_brainstorm_ready(page: Any, timeout_ms: int = 180_000) -> None:
    page.wait_for_function(
        """() => {
          const send = document.getElementById('btn-send');
          const ex = document.getElementById('btn-execute');
          const box2 = document.getElementById('box2-content');
          const free = send && !send.disabled && send.textContent !== '…';
          const hasBrain = box2 && box2.innerText && box2.innerText.length > 40
            && !box2.innerText.includes('Empty — send');
          const canEx = ex && !ex.disabled;
          return free && hasBrain && canEx;
        }""",
        timeout=timeout_ms,
    )


def wait_execute_done(page: Any, timeout_ms: int = 300_000) -> None:
    page.wait_for_function(
        """() => {
          const b = document.getElementById('stage-badge');
          const stage = b ? b.textContent.trim() : '';
          const box3 = document.getElementById('box3-content');
          const text = box3 ? box3.innerText : '';
          const panels = document.querySelectorAll('.worker-panel').length;
          const send = document.getElementById('btn-send');
          const free = send && !send.disabled && send.textContent !== '…';
          if (free && (stage === 'done' || stage === 'clarify' || stage === 'error')) return true;
          if (free && panels > 0) return true;
          if (free && text.length > 120 && !text.includes('appear here')) return true;
          return false;
        }""",
        timeout=timeout_ms,
    )


def type_chat(page: Any, text: str) -> str:
    inp = page.locator("#chat-input")
    inp.click()
    inp.fill("")
    page.keyboard.type(text, delay=6)
    return inp.input_value()


def stage_text(page: Any) -> str:
    if page.locator("#stage-badge").count() == 0:
        return ""
    return page.locator("#stage-badge").inner_text().strip()
