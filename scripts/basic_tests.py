#!/usr/bin/env python3
"""
Three basic stability tests + short analysis report.

  B1  API: brainstorm → execute (live if key, else stub path in smoke-run)
  B2  API: can_execute after brainstorm; Execute not blocked by sticky state
  B3  UI:  keyboard Send → UI unfreezes (input free, Execute enabled)

Usage:
  source .venv/bin/activate
  python scripts/basic_tests.py              # needs server for B3; B1/B2 can use live or isolated
  GNOM_BASIC_BASE=http://127.0.0.1:8080 python scripts/basic_tests.py
  GNOM_BASIC_SKIP_UI=1 python scripts/basic_tests.py

Writes: data/basic-tests/<timestamp>/REPORT.md
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

BASE = os.environ.get("GNOM_BASIC_BASE", "http://127.0.0.1:8080").rstrip("/")
SKIP_UI = os.environ.get("GNOM_BASIC_SKIP_UI", "").strip() in ("1", "true", "yes")
OUT = ROOT / "data" / "basic-tests" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def http_json(method: str, path: str, body: dict | None = None, timeout: float = 180.0) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        # strict parse — invalid control chars = FAIL
        return json.loads(raw.decode("utf-8"))


def poll_job(job_id: str, max_s: float = 180.0) -> dict:
    deadline = time.time() + max_s
    last = {}
    while time.time() < deadline:
        last = http_json("GET", f"/api/jobs/{job_id}", timeout=30)
        st = last.get("status")
        if st in ("done", "error", "clarify", "cancelled"):
            return last
        time.sleep(0.5)
    raise TimeoutError(f"job {job_id} timeout last={last.get('status')}")


class Results:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self.findings: list[str] = []

    def add(self, name: str, ok: bool, detail: str, **extra: object) -> None:
        self.rows.append({"name": name, "ok": ok, "detail": detail, **extra})
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}: {detail}")

    def find(self, msg: str) -> None:
        self.findings.append(msg)
        print(f"  !! {msg}")


def test_b1_api_pipeline(res: Results) -> None:
    """B1: live server brainstorm + execute with non-empty worker output."""
    name = "B1_api_brainstorm_execute"
    try:
        health = http_json("GET", "/api/health", timeout=5)
        if health.get("status") != "ok":
            res.add(name, False, f"health not ok: {health}")
            return
        # reset for clean can_execute
        try:
            http_json("POST", "/api/reset", {}, timeout=15)
        except Exception as e:
            res.find(f"reset failed (non-fatal): {e}")

        start = http_json(
            "POST",
            "/api/chat",
            {"text": "Basic test B1: list three bullet ideas for a tiny todo app."},
            timeout=30,
        )
        if start.get("job_id"):
            job = poll_job(start["job_id"], 180)
            if job.get("status") == "error":
                res.add(name, False, f"brainstorm job error: {job.get('error')}")
                return
            snap = job.get("snapshot") or http_json("GET", "/api/state")
        else:
            snap = start
        pipe = snap.get("pipeline") or {}
        notes = pipe.get("brainstorm_notes") or ""
        if pipe.get("stage") != "brainstorm" and not notes:
            res.add(name, False, f"unexpected stage after chat: {pipe.get('stage')}")
            return
        if len(notes.strip()) < 40:
            res.find(
                f"B1: brainstorm very short ({len(notes)} chars) — model may still be weak: {notes[:80]!r}"
            )
        if not pipe.get("can_execute"):
            res.add(name, False, "can_execute false after brainstorm")
            return

        ex = http_json("POST", "/api/execute", timeout=30)
        if ex.get("job_id"):
            job = poll_job(ex["job_id"], 300)
            if job.get("status") == "error":
                res.add(name, False, f"execute error: {job.get('error')}")
                return
            snap = job.get("snapshot") or http_json("GET", "/api/state")
        else:
            snap = ex
        pipe = snap.get("pipeline") or {}
        stage = pipe.get("stage")
        outs = pipe.get("worker_outputs") or []
        if stage not in ("done", "clarify"):
            res.add(name, False, f"stage={stage} workers={len(outs)}")
            return
        if stage == "done" and not outs:
            res.add(name, False, "stage done but no worker_outputs")
            return
        # content quality
        lengths = [len(str(o.get("result") or "")) for o in outs]
        if lengths and max(lengths) < 80:
            res.find(f"B1: worker results short max={max(lengths)} — check thinking/max_tokens")
        res.add(
            name,
            True,
            f"stage={stage} notes={len(notes)} workers={len(outs)} max_result={max(lengths) if lengths else 0}",
            notes_len=len(notes),
            workers=len(outs),
        )
    except Exception as e:
        res.add(name, False, f"{type(e).__name__}: {e}")


def test_b2_can_execute_and_json(res: Results) -> None:
    """B2: job JSON is strict-parseable; sticky busy not required for can_execute."""
    name = "B2_can_execute_and_valid_json"
    try:
        http_json("POST", "/api/reset", {}, timeout=15)
        start = http_json(
            "POST",
            "/api/chat",
            {"text": "Basic test B2: one sentence about coffee."},
            timeout=30,
        )
        jid = start.get("job_id")
        if not jid:
            res.add(name, False, "no job_id from async chat")
            return
        # fetch raw and ensure json.loads works (browser uses same)
        with urllib.request.urlopen(BASE + f"/api/jobs/{jid}", timeout=30) as r:
            raw = r.read()
        try:
            json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            res.add(name, False, f"invalid JSON from /api/jobs: {e}")
            res.find("Browser pollJob would throw → UI can freeze at Send")
            return
        job = poll_job(jid, 180)
        snap = job.get("snapshot") or {}
        # re-serialize snapshot to detect non-json-safe content
        try:
            json.dumps(snap)
        except (TypeError, ValueError) as e:
            res.add(name, False, f"snapshot not JSON-serializable: {e}")
            return
        pipe = (snap.get("pipeline") if snap else None) or http_json("GET", "/api/state").get(
            "pipeline", {}
        )
        can = bool(pipe.get("can_execute"))
        stage = pipe.get("stage")
        if not can:
            res.add(name, False, f"can_execute=false stage={stage}")
            return
        res.add(name, True, f"valid JSON · can_execute · stage={stage}")
    except Exception as e:
        res.add(name, False, f"{type(e).__name__}: {e}")


def test_b3_ui_unfreeze(res: Results) -> None:
    """B3: real keyboard Send; UI must not stay busy forever."""
    name = "B3_ui_keyboard_unfreeze"
    if SKIP_UI:
        res.add(name, True, "skipped (GNOM_BASIC_SKIP_UI=1)")
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        res.add(name, False, "playwright not installed")
        return
    try:
        http_json("GET", "/api/health", timeout=5)
    except Exception as e:
        res.add(name, False, f"server down: {e}")
        return

    try:
        try:
            http_json("POST", "/api/reset", {}, timeout=15)
        except Exception:
            pass
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(120_000)
            page.goto(BASE + "/?v=80", wait_until="domcontentloaded")
            page.wait_for_selector("#chat-input")
            page.wait_for_timeout(600)
            page.locator("#chat-input").click()
            page.keyboard.type("Basic UI test B3: say hello in one short line.", delay=5)
            page.keyboard.press("Enter")
            # Must become free again
            page.wait_for_function(
                """() => {
                  const send = document.getElementById('btn-send');
                  const inp = document.getElementById('chat-input');
                  const freeSend = send && !send.disabled && send.textContent !== '…';
                  const freeInp = inp && !inp.disabled;
                  return freeSend && freeInp;
                }""",
                timeout=180_000,
            )
            page.wait_for_timeout(300)
            send_dis = page.locator("#btn-send").is_disabled()
            inp_dis = page.locator("#chat-input").is_disabled()
            ex_dis = page.locator("#btn-execute").is_disabled()
            stage = page.locator("#stage-badge").inner_text().strip()
            box2 = page.locator("#box2-content").inner_text()
            # Capture freeze signals
            if send_dis or inp_dis:
                res.add(name, False, f"UI still busy send={send_dis} input={inp_dis} stage={stage}")
                page.screenshot(path=str(OUT / "b3_fail.png"))
                browser.close()
                return
            if stage == "running…" or stage == "running…":
                res.find("stage badge stuck on running… after busy cleared")
            if ex_dis:
                res.find(
                    "Execute still disabled after brainstorm — lastCanExecute regression?"
                )
            if len(box2) < 20:
                res.find(f"Box2 almost empty ({len(box2)} chars)")
            # Execute should be enabled after successful brainstorm
            ok_ex = not ex_dis
            res.add(
                name,
                ok_ex,
                f"unfrozen stage={stage!r} box2={len(box2)} execute_disabled={ex_dis}",
                stage=stage,
                execute_disabled=ex_dis,
            )
            page.screenshot(path=str(OUT / "b3_ok.png"))
            browser.close()
    except Exception as e:
        res.add(name, False, f"{type(e).__name__}: {e}")
        res.find("UI may appear frozen if pollJob times out or JSON parse fails")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"BASIC TESTS → {BASE}")
    print(f"  out → {OUT.relative_to(ROOT)}")
    res = Results()

    test_b1_api_pipeline(res)
    test_b2_can_execute_and_json(res)
    test_b3_ui_unfreeze(res)

    failed = [r for r in res.rows if not r["ok"]]
    report = {
        "when": _utc(),
        "base": BASE,
        "results": res.rows,
        "findings": res.findings,
        "ok": len(failed) == 0,
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# Basic tests report ({report['when']})",
        "",
        f"**Overall:** {'PASS' if report['ok'] else 'FAIL'}",
        f"**Base:** {BASE}",
        "",
        "## Results",
    ]
    for r in res.rows:
        lines.append(f"- **{r['name']}**: {'PASS' if r['ok'] else 'FAIL'} — {r['detail']}")
    if res.findings:
        lines.append("")
        lines.append("## Findings (errors / weak spots)")
        for f in res.findings:
            lines.append(f"- {f}")
    lines.append("")
    lines.append("## What each test means")
    lines.append("- **B1**: real API brainstorm+execute; workers must appear")
    lines.append("- **B2**: `/api/jobs` JSON is browser-safe; `can_execute` after chat")
    lines.append("- **B3**: keyboard Send must free input/Send; Execute should enable")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    latest = ROOT / "data" / "basic-tests" / "latest_report.json"
    latest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print()
    print("RESULT:", "PASS" if report["ok"] else "FAIL")
    for f in res.findings:
        print("FINDING:", f)
    print("Report:", OUT / "REPORT.md")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
