#!/usr/bin/env python3
"""
Real-user quality suite (fixed dev gate) — YOU watch; the script IS the user.

Three absolute real UI journeys via Playwright **headed** (mouse + keyboard on the
live Gnom-Hub frontend). Scores Brainstorm · Flex · Result, then compares to the
previous run (better / worse / same).

Usage (hub must be running on :8080 with a real LLM key preferred):
  ./scripts/start.sh
  source .venv/bin/activate
  python scripts/real_user_quality_e2e.py              # headed, slow, all 3
  GNOM_E2E_HEADED=0 python scripts/real_user_quality_e2e.py   # CI optional

Artifacts: data/e2e-real/<timestamp>/  +  data/e2e-real/LATEST/
  SCORECARD.md  scores.json  TREND.md  screenshots  RESULT.html
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from e2e_lib import (
    StepLog,
    api_reset,
    http_json,
    http_ok,
    shot,
    stage_text,
    wait_brainstorm_ready,
    wait_execute_done,
)

BASE = os.environ.get("GNOM_E2E_BASE", "http://127.0.0.1:8080").rstrip("/")
# Default HEADED so you can watch (override with GNOM_E2E_HEADED=0)
HEADED = os.environ.get("GNOM_E2E_HEADED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)
SLOW_MS = int(os.environ.get("GNOM_E2E_SLOW_MS", "90" if HEADED else "0"))
TYPE_DELAY = int(os.environ.get("GNOM_E2E_TYPE_DELAY", "18" if HEADED else "4"))
OUT_ROOT = ROOT / "data" / "e2e-real"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _pipe() -> dict[str, Any]:
    try:
        return http_json(BASE, "GET", "/api/state", timeout=20).get("pipeline") or {}
    except Exception:
        return {}


def _box2(page) -> str:
    return page.locator("#box2-content").inner_text()


def _box3(page) -> str:
    return page.locator("#box3-content").inner_text()


def _user_type(page, text: str) -> str:
    """Type like a human: click input, clear, keyboard type, short pause."""
    inp = page.locator("#chat-input")
    inp.click()
    time.sleep(0.15 if HEADED else 0.02)
    inp.fill("")
    page.keyboard.type(text, delay=TYPE_DELAY)
    time.sleep(0.2 if HEADED else 0.05)
    return inp.input_value()


def _user_send(page) -> None:
    """Press Enter like a real user (primary path)."""
    page.keyboard.press("Enter")
    time.sleep(0.25 if HEADED else 0.05)


def _user_click_execute(page) -> None:
    btn = page.locator("#btn-execute")
    btn.scroll_into_view_if_needed()
    time.sleep(0.2 if HEADED else 0.05)
    btn.click(delay=40 if HEADED else 0)
    time.sleep(0.2 if HEADED else 0.05)


def _best_worker(outs: list) -> dict[str, Any]:
    best: dict[str, Any] = {}
    best_len = 0
    for o in outs or []:
        raw = str(o.get("result") or "")
        if len(raw) > best_len:
            best_len = len(raw)
            best = o
    return best


def _save_result(run_dir: Path, outs: list) -> dict[str, Any]:
    o = _best_worker(outs)
    raw = str(o.get("result") or "")
    body = raw
    if "```" in body:
        m = re.search(r"```(?:html)?\s*([\s\S]*?)```", body, re.IGNORECASE)
        if m:
            body = m.group(1).strip()
    has_html = "<html" in body.lower() or "<!doctype" in body.lower()
    if body.strip():
        (run_dir / "RESULT.txt").write_text(raw[:80_000], encoding="utf-8")
        if has_html:
            (run_dir / "RESULT.html").write_text(body + "\n", encoding="utf-8")
    return {
        "chars": len(body),
        "has_html": has_html,
        "worker": o.get("worker"),
        "has_interaction": any(
            k in body.lower()
            for k in ("onclick=", "addeventlistener", "addEventListener", "onsubmit=")
        ),
    }


def _score_brainstorm(
    box2: str,
    pipe: dict,
    *,
    expect_keywords: list[str] | None = None,
) -> dict[str, Any]:
    notes = (pipe.get("brainstorm_notes") or box2 or "").strip()
    turns = pipe.get("brainstorm_turns") or []
    low = notes.lower()
    points = 0
    max_p = 10
    reasons: list[str] = []
    if len(notes) >= 80:
        points += 3
        reasons.append("+3 length≥80")
    elif len(notes) >= 40:
        points += 2
        reasons.append("+2 length≥40")
    else:
        reasons.append("+0 too short")
    if turns and any(t.get("role") == "brainstorm" for t in turns):
        points += 2
        reasons.append("+2 dialogue turn")
    if expect_keywords:
        hits = sum(1 for k in expect_keywords if k.lower() in low)
        if hits >= 2:
            points += 3
            reasons.append(f"+3 keyword hits={hits}")
        elif hits == 1:
            points += 1
            reasons.append("+1 keyword hit")
        else:
            reasons.append("+0 keywords miss")
    else:
        points += 2
        reasons.append("+2 no keyword req")
    # Not pure dump of "Empty"
    if "empty — send" in low or len(notes) < 20:
        points = max(0, points - 3)
        reasons.append("-3 empty-ish")
    # Question or structure often good for brainstorm
    if "?" in notes or "•" in notes or "-" in notes[:200]:
        points += 2
        reasons.append("+2 structure/question")
    points = min(max_p, points)
    return {"score": points, "max": max_p, "reasons": reasons, "chars": len(notes)}


def _score_flex(pipe: dict) -> dict[str, Any]:
    notes = (pipe.get("flex_notes") or "").strip()
    reqs = [str(r) for r in (pipe.get("distilled_requirements") or [])]
    req_blob = "\n".join(reqs).lower()
    points = 0
    max_p = 10
    reasons: list[str] = []
    if notes:
        points += 3
        reasons.append("+3 flex_notes present")
    else:
        reasons.append("+0 no flex_notes")
    if len(notes) >= 40:
        points += 2
        reasons.append("+2 flex depth")
    wish_hits = sum(1 for r in reqs if r.lower().startswith("flex-wish") or "flex/" in r.lower())
    if wish_hits:
        points += 3
        reasons.append(f"+3 flex in requirements ({wish_hits})")
    else:
        reasons.append("+0 no flex-wish in reqs")
    # Soft signal: personal language
    if any(k in notes.lower() for k in ("user", "du", "wish", "wunsch", "prefer", "personal")):
        points += 2
        reasons.append("+2 personal language")
    points = min(max_p, points)
    return {
        "score": points,
        "max": max_p,
        "reasons": reasons,
        "flex_chars": len(notes),
        "req_flex_lines": wish_hits,
        "req_preview": req_blob[:200],
    }


def _score_result(pipe: dict, art: dict, *, want_html: bool) -> dict[str, Any]:
    outs = pipe.get("worker_outputs") or []
    points = 0
    max_p = 10
    reasons: list[str] = []
    stage = str(pipe.get("stage") or "")
    err = pipe.get("error")
    chars = int(art.get("chars") or 0)
    if stage == "done" and not err:
        points += 2
        reasons.append("+2 stage done")
    elif stage == "clarify":
        points += 1
        reasons.append("+1 stuck clarify")
    else:
        reasons.append(f"+0 stage={stage} err={err!r}")
    if chars >= 1500:
        points += 3
        reasons.append("+3 body≥1500")
    elif chars >= 800:
        points += 2
        reasons.append("+2 body≥800")
    elif chars >= 200:
        points += 1
        reasons.append("+1 body≥200")
    else:
        reasons.append("+0 body thin")
    if want_html:
        if art.get("has_html"):
            points += 3
            reasons.append("+3 html present")
        else:
            reasons.append("+0 no html")
        if art.get("has_interaction"):
            points += 2
            reasons.append("+2 interaction")
        else:
            reasons.append("+0 no interaction")
    else:
        points += 2
        reasons.append("+2 non-html task")
    if outs:
        points = min(max_p, points + 0)
    points = min(max_p, points)
    return {
        "score": points,
        "max": max_p,
        "reasons": reasons,
        "chars": chars,
        "stage": stage,
        "workers": len(outs),
    }


def _total(scores: dict[str, dict]) -> dict[str, Any]:
    s = sum(int(v.get("score") or 0) for v in scores.values())
    m = sum(int(v.get("max") or 0) for v in scores.values())
    return {"score": s, "max": m, "pct": round(100.0 * s / m, 1) if m else 0.0}


def scenario_r1_dialogue_to_build(page, run_dir: Path, log: StepLog) -> dict:
    """
    R1 — Real brainstorm dialogue then commit.
    User starts soft, answers like a human, then execute.
    """
    name = "dialogue_to_build"
    api_reset(BASE)
    page.goto(BASE + "/?e2e=real-r1", wait_until="domcontentloaded")
    page.wait_for_selector("#chat-input", state="visible")
    log.add("r1_open", status="ok", shot=shot(page, run_dir, "r1_01_open"))

    # Soft entry — brainstorm should help shape
    t1 = (
        "Ich will irgendwas Kleines für mein Café online, "
        "noch unsicher was genau — nur brainstorm bitte."
    )
    _user_type(page, t1)
    _user_send(page)
    wait_brainstorm_ready(page, timeout_ms=240_000)
    log.add("r1_brain1", status="ok", shot=shot(page, run_dir, "r1_02_brain1"))
    box2_a = _box2(page)

    # User decides
    t2 = (
        "Ok: eine schlichte Landingpage für Café Morgenlicht, "
        "Hero mit CTA, drei Features, Footer. Volles HTML."
    )
    _user_type(page, t2)
    _user_send(page)
    # May auto-execute or stay brainstorm
    try:
        wait_brainstorm_ready(page, timeout_ms=120_000)
    except Exception:
        pass
    # If still not executing, click Execute like a user
    pipe_mid = _pipe()
    if (
        str(pipe_mid.get("stage") or "") not in ("done", "work", "coordinate", "flex", "distill")
        and page.locator("#btn-execute").is_enabled()
    ):
        _user_click_execute(page)
    try:
        wait_execute_done(page, timeout_ms=360_000)
    except Exception as exc:
        log.add("r1_wait", status="timeout", detail=str(exc))
    log.add("r1_done_ui", status="ok", shot=shot(page, run_dir, "r1_03_done"))

    pipe = _pipe()
    art = _save_result(run_dir, pipe.get("worker_outputs") or [])
    scores = {
        "brainstorm": _score_brainstorm(
            box2_a,
            {**pipe, "brainstorm_notes": box2_a or pipe.get("brainstorm_notes")},
            expect_keywords=["café", "cafe", "landing", "hero", "html", "feature"],
        ),
        "flex": _score_flex(pipe),
        "result": _score_result(pipe, art, want_html=True),
    }
    tot = _total(scores)
    ok = tot["pct"] >= 45 and not pipe.get("error") and art.get("chars", 0) >= 400
    return {
        "id": "R1",
        "name": name,
        "ok": ok,
        "scores": scores,
        "total": tot,
        "detail": f"pct={tot['pct']} stage={pipe.get('stage')} chars={art.get('chars')}",
        "artifact": art,
        "flex_notes": (pipe.get("flex_notes") or "")[:400],
        "brainstorm_preview": box2_a[:400],
    }


def scenario_r2_clear_build_order(page, run_dir: Path, log: StepLog) -> dict:
    """
    R2 — Hard build order (user knows what they want).
    Tests auto-execute / execute path + result quality under clear intent.
    """
    name = "clear_build_order"
    api_reset(BASE)
    page.goto(BASE + "/?e2e=real-r2", wait_until="domcontentloaded")
    page.wait_for_selector("#chat-input", state="visible")
    log.add("r2_open", status="ok", shot=shot(page, run_dir, "r2_01_open"))

    text = (
        "Build a modern single-file todo app: three columns (Today / Week / Later), "
        "keyboard-first, localStorage, dark theme. Full HTML with inline CSS and JS."
    )
    _user_type(page, text)
    _user_send(page)
    # Either auto-execute or brainstorm-then-execute
    try:
        wait_brainstorm_ready(page, timeout_ms=180_000)
        log.add("r2_brain", status="ok", shot=shot(page, run_dir, "r2_02_brain"))
        # If still only brainstorm (no auto), user hits Execute
        if page.locator("#btn-execute").is_enabled() and stage_text(page) in (
            "brainstorm",
            "idle",
            "",
        ):
            _user_click_execute(page)
    except Exception:
        pass
    wait_execute_done(page, timeout_ms=360_000)
    log.add("r2_done", status="ok", shot=shot(page, run_dir, "r2_03_done"))

    pipe = _pipe()
    box2 = _box2(page)
    art = _save_result(run_dir, pipe.get("worker_outputs") or [])
    # rename result for this scenario folder namespace
    if (run_dir / "RESULT.html").is_file():
        (run_dir / "R2_RESULT.html").write_bytes((run_dir / "RESULT.html").read_bytes())
    scores = {
        "brainstorm": _score_brainstorm(
            box2, pipe, expect_keywords=["todo", "column", "keyboard", "html"]
        ),
        "flex": _score_flex(pipe),
        "result": _score_result(pipe, art, want_html=True),
    }
    tot = _total(scores)
    task_hit = any(
        k in (pipe.get("user_text") or "").lower() for k in ("todo", "column", "keyboard")
    )
    ok = tot["pct"] >= 50 and task_hit and art.get("chars", 0) >= 800
    return {
        "id": "R2",
        "name": name,
        "ok": ok,
        "scores": scores,
        "total": tot,
        "detail": f"pct={tot['pct']} chars={art.get('chars')} interact={art.get('has_interaction')}",
        "artifact": art,
        "flex_notes": (pipe.get("flex_notes") or "")[:400],
    }


def scenario_r3_flex_wish_support(page, run_dir: Path, log: StepLog) -> dict:
    """
    R3 — Flex should notice standing preference and support the user.
    Plant a warm flex-style fact, then ask for a page that should respect it.
    """
    name = "flex_wish_support"
    api_reset(BASE)
    # Standing wish into WARM (Flex personal)
    try:
        http_json(
            BASE,
            "POST",
            "/api/memory/warm",
            {"text": "User: always prefer dark theme and German UI labels"},
            timeout=15,
        )
    except Exception:
        pass

    page.goto(BASE + "/?e2e=real-r3", wait_until="domcontentloaded")
    page.wait_for_selector("#chat-input", state="visible")
    log.add("r3_open", status="ok", shot=shot(page, run_dir, "r3_01_open"))

    text = (
        "Bau mir bitte eine kleine Portfolio-Landingpage für eine Fotografin "
        "namens Lena Berg. Hero, drei Arbeiten als Karten, Kontakt. "
        "Denk an meine Vorlieben."
    )
    _user_type(page, text)
    _user_send(page)
    try:
        wait_brainstorm_ready(page, timeout_ms=180_000)
        log.add("r3_brain", status="ok", shot=shot(page, run_dir, "r3_02_brain"))
        if page.locator("#btn-execute").is_enabled() and stage_text(page) in (
            "brainstorm",
            "idle",
            "",
        ):
            _user_click_execute(page)
    except Exception:
        pass
    wait_execute_done(page, timeout_ms=360_000)
    log.add("r3_done", status="ok", shot=shot(page, run_dir, "r3_03_done"))

    pipe = _pipe()
    box2 = _box2(page)
    art = _save_result(run_dir, pipe.get("worker_outputs") or [])
    body = ""
    if (run_dir / "RESULT.html").is_file():
        body = (run_dir / "RESULT.html").read_text(encoding="utf-8", errors="replace")
    elif (run_dir / "RESULT.txt").is_file():
        body = (run_dir / "RESULT.txt").read_text(encoding="utf-8", errors="replace")
    low = body.lower()
    dark_ok = any(
        k in low
        for k in ("dark", "background:#0", "background: #0", "#111", "#0d0", "prefers-color-scheme")
    )
    de_ok = (
        any(k in body for k in ("Kontakt", "Arbeiten", "Über", "Fotografie", "Hero"))
        or "lena" in low
    )

    scores = {
        "brainstorm": _score_brainstorm(
            box2, pipe, expect_keywords=["portfolio", "lena", "landing", "hero"]
        ),
        "flex": _score_flex(pipe),
        "result": _score_result(pipe, art, want_html=True),
    }
    # Bonus dimension encoded into flex score reasons
    if dark_ok or de_ok:
        scores["flex"]["score"] = min(10, scores["flex"]["score"] + 2)
        scores["flex"]["reasons"].append(f"+2 wish reflected dark={dark_ok} germanish={de_ok}")
    tot = _total(scores)
    ok = tot["pct"] >= 45 and art.get("chars", 0) >= 500
    return {
        "id": "R3",
        "name": name,
        "ok": ok,
        "scores": scores,
        "total": tot,
        "detail": f"pct={tot['pct']} dark={dark_ok} de={de_ok} chars={art.get('chars')}",
        "artifact": art,
        "flex_notes": (pipe.get("flex_notes") or "")[:400],
        "wish_reflected": {"dark": dark_ok, "germanish": de_ok},
    }


SCENARIOS = {
    "1": ("R1", scenario_r1_dialogue_to_build),
    "2": ("R2", scenario_r2_clear_build_order),
    "3": ("R3", scenario_r3_flex_wish_support),
}


def _load_prev_scores() -> dict[str, Any] | None:
    p = OUT_ROOT / "LATEST" / "scores.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _trend_line(curr: float, prev: float | None) -> str:
    if prev is None:
        return "first run (no baseline)"
    d = round(curr - prev, 1)
    if d > 2:
        return f"↑ better (+{d} pts)"
    if d < -2:
        return f"↓ worse ({d} pts)"
    return f"→ same ({d:+.1f} pts)"


def _write_reports(run_dir: Path, report: dict, prev: dict | None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "scores.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        f"# Real-user quality scorecard — {report.get('started')}",
        "",
        (
            f"**Overall:** {'PASS' if report.get('ok') else 'FAIL'} · "
            f"**Score:** {report.get('score_pct')}% "
            f"({report.get('score_sum')}/{report.get('score_max')})"
        ),
        f"**Base:** {report.get('base_url')} · **Headed:** {report.get('headed')}",
        f"**LLM:** {report.get('llm')}",
        "",
        "## Scenarios",
        "",
        "| ID | Name | OK | % | Brainstorm | Flex | Result | Trend |",
        "|----|------|----|---|------------|------|--------|-------|",
    ]
    prev_sc = {s["id"]: s for s in (prev or {}).get("scenarios") or []}
    for s in report.get("scenarios") or []:
        sc = s.get("scores") or {}
        tot = s.get("total") or {}
        prev_pct = (prev_sc.get(s["id"]) or {}).get("total", {}).get("pct")
        tr = _trend_line(
            float(tot.get("pct") or 0), float(prev_pct) if prev_pct is not None else None
        )
        lines.append(
            f"| {s.get('id')} | {s.get('name')} | "
            f"{'PASS' if s.get('ok') else 'FAIL'} | {tot.get('pct')} | "
            f"{(sc.get('brainstorm') or {}).get('score')}/10 | "
            f"{(sc.get('flex') or {}).get('score')}/10 | "
            f"{(sc.get('result') or {}).get('score')}/10 | {tr} |"
        )
    lines += ["", "## Details", ""]
    for s in report.get("scenarios") or []:
        lines.append(f"### {s.get('id')} — {s.get('name')}")
        lines.append(f"- detail: {s.get('detail')}")
        for dim, blob in (s.get("scores") or {}).items():
            lines.append(
                f"- **{dim}:** {blob.get('score')}/{blob.get('max')} — "
                + "; ".join(blob.get("reasons") or [])
            )
        if s.get("flex_notes"):
            lines.append(f"- flex_notes: `{str(s.get('flex_notes'))[:200]}`")
        lines.append("")

    # Trend summary
    prev_pct = (prev or {}).get("score_pct")
    overall_tr = _trend_line(
        float(report.get("score_pct") or 0),
        float(prev_pct) if prev_pct is not None else None,
    )
    trend_md = [
        f"# Trend — {report.get('started')}",
        "",
        f"**Overall:** {overall_tr}",
        f"- this run: {report.get('score_pct')}%",
        f"- previous: {prev_pct if prev_pct is not None else 'n/a'}%",
        "",
    ]
    for s in report.get("scenarios") or []:
        pid = s["id"]
        prev_s = prev_sc.get(pid) or {}
        trend_md.append(
            f"- **{pid}:** {_trend_line(float((s.get('total') or {}).get('pct') or 0), (prev_s.get('total') or {}).get('pct'))}"
        )
    trend_md.append("")

    (run_dir / "SCORECARD.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run_dir / "TREND.md").write_text("\n".join(trend_md) + "\n", encoding="utf-8")

    latest = OUT_ROOT / "LATEST"
    latest.mkdir(parents=True, exist_ok=True)
    for name in (
        "scores.json",
        "SCORECARD.md",
        "TREND.md",
        "RESULT.html",
        "RESULT.txt",
        "R2_RESULT.html",
    ):
        src = run_dir / name
        if src.is_file():
            (latest / name).write_bytes(src.read_bytes())
    # copy a few shots
    for png in sorted(run_dir.glob("*.png"))[-6:]:
        (latest / png.name).write_bytes(png.read_bytes())


def main() -> int:
    ap = argparse.ArgumentParser(description="Real-user quality E2E (headed by default)")
    ap.add_argument("--only", default="1,2,3", help="comma ids 1,2,3")
    args = ap.parse_args()

    health = http_ok(BASE)
    if not health:
        print(f"FAIL: hub not reachable at {BASE} — start with ./scripts/start.sh", file=sys.stderr)
        return 2

    only = [x.strip() for x in args.only.split(",") if x.strip()]
    run_dir = OUT_ROOT / _utc()
    run_dir.mkdir(parents=True, exist_ok=True)
    log = StepLog()
    prev = _load_prev_scores()

    print("=" * 60)
    print("REAL USER QUALITY E2E — script plays the user")
    print(f"  base={BASE}  headed={HEADED}  slow_ms={SLOW_MS}  type_delay={TYPE_DELAY}")
    print(f"  out={run_dir}")
    print("  Watch the browser window if headed=1")
    print("=" * 60)

    from playwright.sync_api import sync_playwright

    scenarios_out: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not HEADED,
            slow_mo=SLOW_MS,
        )
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            locale="de-DE",
        )
        page = context.new_page()
        page.set_default_timeout(120_000)

        for key in only:
            meta = SCENARIOS.get(key)
            if not meta:
                print(f"  skip unknown scenario {key}")
                continue
            sid, fn = meta
            print(f"\n▶ {sid} starting…")
            try:
                row = fn(page, run_dir, log)
            except Exception as exc:
                print(f"  ✗ {sid} exception: {exc}")
                row = {
                    "id": sid,
                    "name": "error",
                    "ok": False,
                    "detail": str(exc),
                    "scores": {
                        "brainstorm": {"score": 0, "max": 10, "reasons": ["exception"]},
                        "flex": {"score": 0, "max": 10, "reasons": ["exception"]},
                        "result": {"score": 0, "max": 10, "reasons": ["exception"]},
                    },
                    "total": {"score": 0, "max": 30, "pct": 0.0},
                }
            scenarios_out.append(row)
            print(
                f"  {'✓' if row.get('ok') else '✗'} {sid} "
                f"{(row.get('total') or {}).get('pct')}% — {row.get('detail')}"
            )
            time.sleep(0.8 if HEADED else 0.1)

        browser.close()

    score_sum = sum(int((s.get("total") or {}).get("score") or 0) for s in scenarios_out)
    score_max = sum(int((s.get("total") or {}).get("max") or 0) for s in scenarios_out) or 1
    score_pct = round(100.0 * score_sum / score_max, 1)
    report = {
        "started": _utc(),
        "base_url": BASE,
        "headed": HEADED,
        "slow_ms": SLOW_MS,
        "ok": all(bool(s.get("ok")) for s in scenarios_out) and score_pct >= 45,
        "score_sum": score_sum,
        "score_max": score_max,
        "score_pct": score_pct,
        "llm": (health or {}).get("llm"),
        "scenarios": scenarios_out,
        "steps": log.steps,
        "previous_pct": (prev or {}).get("score_pct"),
        "trend_overall": _trend_line(
            score_pct,
            float(prev["score_pct"]) if prev and prev.get("score_pct") is not None else None,
        ),
    }
    _write_reports(run_dir, report, prev)

    print("\n" + "=" * 60)
    print(f"OVERALL: {'PASS' if report['ok'] else 'FAIL'}  {score_pct}%  {report['trend_overall']}")
    print(f"Scorecard: {run_dir / 'SCORECARD.md'}")
    print(f"Trend:     {run_dir / 'TREND.md'}")
    print(f"Latest:    {OUT_ROOT / 'LATEST'}")
    print("=" * 60)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
