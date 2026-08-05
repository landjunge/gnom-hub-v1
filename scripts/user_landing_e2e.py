#!/usr/bin/env python3
"""
Basic user-position E2E: real browser + real keyboard.

Flow (as a human would):
  1. Open UI
  2. Type chat: ask for a landing page (keyboard, not fill API)
  3. Press Enter → Brainstorm
  4. Ctrl+Enter → Execute
  5. Wait for Box 3 worker results
  6. Write report under data/e2e-user/

Requires: live server on BASE_URL (default http://127.0.0.1:8080),
          DeepSeek key for non-stub path, playwright chromium.

  source .venv/bin/activate
  python scripts/user_landing_e2e.py
  GNOM_E2E_HEADED=1 python scripts/user_landing_e2e.py   # see browser
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

BASE_URL = os.environ.get("GNOM_E2E_BASE", "http://127.0.0.1:8080").rstrip("/")
HEADED = os.environ.get("GNOM_E2E_HEADED", "0").strip() in ("1", "true", "yes")
OUT_DIR = ROOT / "data" / "e2e-user"
CHAT_TEXT = (
    "Build a modern landing page for a coffee shop called Bean & Bloom. "
    "Include hero with headline and CTA, three feature cards, and a simple footer. "
    "Output full HTML with inline CSS."
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "FAIL: playwright not installed — pip install playwright && playwright install chromium"
        )
        return 2

    import urllib.request

    try:
        with urllib.request.urlopen(BASE_URL + "/api/health", timeout=5) as r:
            health = json.loads(r.read().decode())
    except Exception as exc:
        print(f"FAIL: server not reachable at {BASE_URL}: {exc}")
        return 2

    stamp = _utc()
    run_dir = OUT_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "name": "basic_user_landing_page",
        "started": stamp,
        "base_url": BASE_URL,
        "health": health,
        "chat_text": CHAT_TEXT,
        "steps": [],
        "ok": False,
        "analysis": {},
    }

    def step(name: str, **kw) -> None:
        entry = {"step": name, "t": time.time(), **kw}
        report["steps"].append(entry)
        print(f"  · {name}: {kw.get('detail', kw.get('status', 'ok'))}")

    def shot(page, name: str) -> str:
        path = run_dir / f"{name}.png"
        page.screenshot(path=str(path), full_page=True)
        return str(path.relative_to(ROOT))

    print(f"USER E2E → {BASE_URL}  headed={HEADED}")
    print(f"  report → {run_dir.relative_to(ROOT)}")

    # Clean pipeline so can_execute / stages start fresh (user would often open fresh)
    try:
        req = urllib.request.Request(
            BASE_URL + "/api/reset",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            report["steps"].append({"step": "api_reset", "status": "ok", "code": r.status})
            print("  · api_reset: ok")
    except Exception as exc:
        report["steps"].append({"step": "api_reset", "status": "skip", "error": str(exc)})
        print(f"  · api_reset: skip ({exc})")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not HEADED)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.set_default_timeout(120_000)

        # 1) Open UI
        page.goto(BASE_URL + "/?v=80", wait_until="domcontentloaded")
        page.wait_for_selector("#chat-input", state="visible")
        step("open_ui", status="ok", shot=shot(page, "01_open"))

        # Ensure agents on (enable-all is bootstrap, but double-check)
        page.wait_for_timeout(800)

        # 2) Focus chat and type with real keyboard (character-by-character)
        inp = page.locator("#chat-input")
        inp.click()
        inp.fill("")  # clear
        # Use keyboard.type for real key events (not only value set)
        page.keyboard.type(CHAT_TEXT, delay=8)
        typed = inp.input_value()
        step(
            "type_chat",
            status="ok" if typed.strip() == CHAT_TEXT.strip() else "partial",
            chars=len(typed),
            detail=f"{len(typed)} chars typed",
            shot=shot(page, "02_typed"),
        )
        if not typed.strip():
            report["analysis"]["fail"] = "keyboard type did not fill chat-input"
            _write_report(run_dir, report)
            browser.close()
            return 1

        # 3) Enter → Send (brainstorm)
        page.keyboard.press("Enter")
        step("press_enter_send", status="ok", detail="Enter")
        # Wait: not busy AND brainstorm content in box2 AND Execute enabled
        try:
            page.wait_for_function(
                """() => {
                  const b = document.getElementById('stage-badge');
                  const send = document.getElementById('btn-send');
                  const ex = document.getElementById('btn-execute');
                  const box2 = document.getElementById('box2-content');
                  const stage = b ? b.textContent.trim() : '';
                  const free = send && !send.disabled && send.textContent !== '…';
                  const hasBrain = box2 && box2.innerText && box2.innerText.length > 40
                    && !box2.innerText.includes('Empty — send');
                  const canEx = ex && !ex.disabled;
                  return free && hasBrain && (stage === 'brainstorm' || stage === 'done'
                    || stage === 'clarify' || canEx);
                }""",
                timeout=180_000,
            )
            # settle UI after busy flag clears
            page.wait_for_timeout(400)
            stage = page.locator("#stage-badge").inner_text().strip()
            step("brainstorm_done", status="ok", stage=stage, shot=shot(page, "03_brainstorm"))
        except Exception as exc:
            stage = (
                page.locator("#stage-badge").inner_text()
                if page.locator("#stage-badge").count()
                else "?"
            )
            step(
                "brainstorm_done",
                status="timeout",
                stage=stage,
                error=str(exc),
                shot=shot(page, "03_brainstorm_fail"),
            )
            report["analysis"]["brainstorm"] = "timeout or failed"
            _write_report(run_dir, report)
            browser.close()
            return 1

        box2 = page.locator("#box2-content").inner_text()
        report["analysis"]["box2_chars"] = len(box2)
        report["analysis"]["box2_preview"] = box2[:400]

        # 4) Execute: wait until button enabled, then click (primary path).
        #    Also try Ctrl+Enter as secondary human path.
        exec_btn = page.locator("#btn-execute")
        try:
            page.wait_for_function(
                "() => { const b=document.getElementById('btn-execute'); return b && !b.disabled; }",
                timeout=30_000,
            )
        except Exception as exc:
            step(
                "wait_execute_enabled",
                status="fail",
                error=str(exc),
                shot=shot(page, "03b_exec_disabled"),
            )
            report["analysis"]["execute"] = "Execute stayed disabled after brainstorm"
            _write_report(run_dir, report)
            browser.close()
            return 1

        # Prefer explicit button click (most reliable for automation)
        exec_btn.click()
        step("execute_click", status="ok", detail="clicked #btn-execute")
        page.wait_for_timeout(300)
        # If still idle, also try keyboard path once
        stage_now = page.locator("#stage-badge").inner_text().strip()
        if stage_now == "brainstorm":
            inp.click()
            page.keyboard.press("Control+Enter")
            step("execute_ctrl_enter_retry", status="ok", detail="Ctrl+Enter after click")

        # 5) Wait for workers / done (live LLM can take minutes)
        try:
            page.wait_for_function(
                """() => {
                  const b = document.getElementById('stage-badge');
                  const stage = b ? b.textContent.trim() : '';
                  const box3 = document.getElementById('box3-content');
                  const text = box3 ? box3.innerText : '';
                  const panels = document.querySelectorAll('.worker-panel').length;
                  const send = document.getElementById('btn-send');
                  const free = send && !send.disabled && send.textContent !== '…';
                  const working = ['distill','flex','coordinate','work','done','clarify','error']
                    .some(s => stage === s);
                  // done when free again and (done/clarify/error or worker panels)
                  if (free && (stage === 'done' || stage === 'clarify' || stage === 'error')) return true;
                  if (free && panels > 0) return true;
                  if (free && text.length > 120 && !text.includes('appear here')) return true;
                  return false;
                }""",
                timeout=300_000,
            )
            stage = page.locator("#stage-badge").inner_text().strip()
            step("execute_finished", status="ok", stage=stage, shot=shot(page, "04_execute"))
        except Exception as exc:
            stage = (
                page.locator("#stage-badge").inner_text()
                if page.locator("#stage-badge").count()
                else "?"
            )
            step(
                "execute_finished",
                status="timeout",
                stage=stage,
                error=str(exc),
                shot=shot(page, "04_execute_fail"),
            )

        # 6) Analyze Box 3
        box3 = page.locator("#box3-content").inner_text()
        panels = page.locator(".worker-panel").count()
        previews = page.locator(".worker-preview-frame").count()
        has_html = bool(
            re.search(r"<!DOCTYPE|<html|</html>|<div|<section|<h1", box3, re.IGNORECASE)
            or previews > 0
        )
        chat_log = page.locator("#chat-log").inner_text()
        cost = (
            page.locator("#cost-badge").inner_text() if page.locator("#cost-badge").count() else ""
        )

        # Snapshot API state
        try:
            with urllib.request.urlopen(BASE_URL + "/api/state", timeout=10) as r:
                state = json.loads(r.read().decode())
        except Exception as exc:
            state = {"error": str(exc)}

        pipe = (state or {}).get("pipeline") or {}
        outs = pipe.get("worker_outputs") or []
        report["analysis"].update(
            {
                "stage": stage,
                "box3_chars": len(box3),
                "box3_preview": box3[:600],
                "worker_panels_dom": panels,
                "html_preview_iframes": previews,
                "looks_like_html": has_html,
                "worker_outputs_api": len(outs),
                "worker_names": [o.get("name") or o.get("worker") for o in outs],
                "cost_badge": cost,
                "chat_log_tail": chat_log[-800:],
                "pipeline_error": pipe.get("error"),
                "quality_notes": (pipe.get("quality_notes") or "")[:300],
            }
        )
        shot(page, "05_final")

        # Success criteria (basic user test)
        ok_brainstorm = report["analysis"].get("box2_chars", 0) > 20
        ok_workers = panels > 0 or len(outs) > 0
        ok_stage = stage in ("done", "clarify") or ok_workers
        ok = ok_brainstorm and ok_workers and ok_stage and not pipe.get("error")
        report["ok"] = bool(ok)
        report["analysis"]["criteria"] = {
            "brainstorm_nonempty": ok_brainstorm,
            "workers_present": ok_workers,
            "stage_ok": ok_stage,
            "no_pipeline_error": not bool(pipe.get("error")),
        }

        # Persist API export if available
        try:
            with urllib.request.urlopen(BASE_URL + "/api/export/last", timeout=10) as r:
                exp = json.loads(r.read().decode())
            (run_dir / "export_last.md").write_text(exp.get("content") or "", encoding="utf-8")
            report["analysis"]["export_chars"] = exp.get("chars")
        except Exception as exc:
            report["analysis"]["export_error"] = str(exc)

        browser.close()

    _write_report(run_dir, report)
    print()
    print("=== ANALYSIS ===")
    for k, v in report["analysis"].items():
        if k in ("box2_preview", "box3_preview", "chat_log_tail"):
            print(f"  {k}: {str(v)[:120].replace(chr(10), ' ')}…")
        else:
            print(f"  {k}: {v}")
    print()
    print("RESULT:", "PASS" if report["ok"] else "FAIL")
    print(f"Report: {run_dir / 'report.json'}")
    # Latest symlink-like copy
    latest = OUT_DIR / "latest_report.json"
    latest.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


def _write_report(run_dir: Path, report: dict) -> None:
    report["finished"] = _utc()
    (run_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md = [
        f"# User E2E: landing page ({report.get('started')})",
        "",
        f"**Result:** {'PASS' if report.get('ok') else 'FAIL'}",
        f"**URL:** {report.get('base_url')}",
        "",
        "## Chat (typed via keyboard)",
        "```",
        report.get("chat_text") or "",
        "```",
        "",
        "## Steps",
    ]
    for s in report.get("steps") or []:
        md.append(f"- `{s.get('step')}`: {s.get('status')} {s.get('detail', s.get('stage', ''))}")
    md.append("")
    md.append("## Analysis")
    a = report.get("analysis") or {}
    for k, v in a.items():
        if isinstance(v, str) and len(v) > 200:
            md.append(f"- **{k}**: {v[:200]}…")
        else:
            md.append(f"- **{k}**: `{v}`")
    (run_dir / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
