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


def _prepare_deutsch_ui(page) -> None:
    """UI-Sprache Deutsch + TTS freischalten (Klick) + Brainstorm-TTS an."""
    try:
        http_json(BASE, "POST", "/api/system", {"ui_lang": "de"}, timeout=15)
    except Exception:
        pass
    page.goto(BASE + "/?lang=de&e2e=prep", wait_until="domcontentloaded")
    page.wait_for_selector("#chat-input", state="visible")
    # Volle Desk-Fläche nutzbar machen
    page.evaluate("() => { document.documentElement.style.zoom = '0.85'; }")
    # User-Geste: TTS freischalten
    page.locator("body").click(position={"x": 40, "y": 40})
    time.sleep(0.3)
    # Brainstorm-TTS per Karte aktivieren (falls aus) — spricht DE-Hinweis
    try:
        tts = page.locator('.agent-card[data-agent-id="brainstorm"] .card-tts input')
        if tts.count() and not tts.is_checked():
            tts.click()
            time.sleep(0.4)
        # Flex TTS optional an
        tts_f = page.locator('.agent-card[data-agent-id="flex"] .card-tts input')
        if tts_f.count() and not tts_f.is_checked():
            tts_f.click()
            time.sleep(0.4)
    except Exception:
        pass
    # Kurz warten damit TTS-Freigabe greift
    time.sleep(0.5)


def _focus_box3_visible(page) -> None:
    """Box 3 ins Sichtfeld holen (wie echter User nach Execute)."""
    try:
        page.evaluate(
            """() => {
              const box = document.getElementById('box3');
              if (box) {
                box.scrollIntoView({ behavior: 'instant', block: 'center' });
                box.classList.add('box3-flash');
              }
              if (typeof focusBox3 === 'function') focusBox3();
            }"""
        )
    except Exception:
        try:
            page.locator("#box3").scroll_into_view_if_needed()
        except Exception:
            pass
    time.sleep(0.8 if HEADED else 0.2)


def _wait_box3_result(page, *, timeout_ms: int = 120_000) -> str:
    """Warten bis Box 3 echten Worker-Inhalt zeigt (nicht nur Platzhalter)."""
    deadline = time.time() + timeout_ms / 1000.0
    last = ""
    while time.time() < deadline:
        _focus_box3_visible(page)
        try:
            last = page.locator("#box3-content").inner_text()
        except Exception:
            last = ""
        panels = page.locator(".worker-panel").count()
        iframes = page.locator(".worker-preview-frame").count()
        # Content markers
        low = last.lower()
        has_body = len(last) > 80 and "appear here" not in low
        if (panels >= 1 or iframes >= 1 or has_body) and (has_body or iframes >= 1):
            time.sleep(1.2 if HEADED else 0.3)  # kurz sichtbar lassen
            return last
        time.sleep(0.5)
    return last


def _maybe_execute(page) -> None:
    pipe_mid = _pipe()
    st = str(pipe_mid.get("stage") or "")
    if (
        st not in ("done", "work", "coordinate", "flex", "distill")
        and page.locator("#btn-execute").is_enabled()
    ):
        _user_click_execute(page)


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
    """R1 — Weicher Einstieg, dann klare Landing (alles Deutsch)."""
    name = "dialog_zu_landing"
    api_reset(BASE)
    _prepare_deutsch_ui(page)
    page.goto(BASE + "/?e2e=real-r1&lang=de", wait_until="domcontentloaded")
    page.wait_for_selector("#chat-input", state="visible")
    page.evaluate("() => { document.documentElement.style.zoom = '0.85'; }")
    page.locator("body").click(position={"x": 50, "y": 50})
    log.add("r1_open", status="ok", shot=shot(page, run_dir, "r1_01_open"))

    t1 = (
        "Hallo — ich will irgendwas Kleines für mein Café online. "
        "Noch unsicher was genau. Bitte nur brainstormen, noch nicht bauen."
    )
    _user_type(page, t1)
    _user_send(page)
    wait_brainstorm_ready(page, timeout_ms=240_000)
    log.add("r1_brain1", status="ok", shot=shot(page, run_dir, "r1_02_brain1"))
    box2_a = _box2(page)
    # TTS der Gedanken zu Ende laufen lassen (sichtbar/hörbar)
    time.sleep(4.0 if HEADED else 0.5)

    t2 = (
        "Alles klar: eine schlichte Landingpage für Café Morgenlicht, "
        "Hero mit großer Überschrift und CTA-Button, drei Feature-Karten, "
        "Footer. Bitte vollständiges HTML mit CSS."
    )
    _user_type(page, t2)
    _user_send(page)
    try:
        wait_brainstorm_ready(page, timeout_ms=120_000)
    except Exception:
        pass
    _maybe_execute(page)
    try:
        wait_execute_done(page, timeout_ms=360_000)
    except Exception as exc:
        log.add("r1_wait", status="timeout", detail=str(exc))
    box3_txt = _wait_box3_result(page)
    log.add(
        "r1_done_ui",
        status="ok",
        shot=shot(page, run_dir, "r1_03_box3"),
        detail=f"box3_len={len(box3_txt)}",
    )

    pipe = _pipe()
    art = _save_result(run_dir, pipe.get("worker_outputs") or [])
    scores = {
        "brainstorm": _score_brainstorm(
            box2_a,
            {**pipe, "brainstorm_notes": box2_a or pipe.get("brainstorm_notes")},
            expect_keywords=["café", "cafe", "landing", "hero", "morgenlicht", "feature"],
        ),
        "flex": _score_flex(pipe),
        "result": _score_result(pipe, art, want_html=True),
    }
    tot = _total(scores)
    ok = (
        tot["pct"] >= 45
        and not pipe.get("error")
        and (art.get("chars", 0) >= 400 or len(box3_txt) > 80)
    )
    return {
        "id": "R1",
        "name": name,
        "ok": ok,
        "scores": scores,
        "total": tot,
        "detail": (
            f"pct={tot['pct']} stage={pipe.get('stage')} "
            f"chars={art.get('chars')} box3={len(box3_txt)}"
        ),
        "artifact": art,
        "flex_notes": (pipe.get("flex_notes") or "")[:400],
        "brainstorm_preview": box2_a[:400],
        "box3_preview": box3_txt[:300],
    }


def scenario_r2_clear_build_order(page, run_dir: Path, log: StepLog) -> dict:
    """R2 — Klare Bau-Anweisung (Todo-App), alles Deutsch."""
    name = "klare_bauanweisung"
    api_reset(BASE)
    _prepare_deutsch_ui(page)
    page.goto(BASE + "/?e2e=real-r2&lang=de", wait_until="domcontentloaded")
    page.wait_for_selector("#chat-input", state="visible")
    page.evaluate("() => { document.documentElement.style.zoom = '0.85'; }")
    page.locator("body").click(position={"x": 50, "y": 50})
    log.add("r2_open", status="ok", shot=shot(page, run_dir, "r2_01_open"))

    text = (
        "Baue mir eine moderne Todo-App als eine HTML-Datei: "
        "drei Spalten Heute / Woche / Später, Tastaturbedienung, "
        "localStorage, dunkles Theme. Volles HTML mit CSS und JavaScript, "
        "mit klickbaren Buttons."
    )
    _user_type(page, text)
    _user_send(page)
    try:
        wait_brainstorm_ready(page, timeout_ms=180_000)
        log.add("r2_brain", status="ok", shot=shot(page, run_dir, "r2_02_brain"))
        time.sleep(3.0 if HEADED else 0.3)
        _maybe_execute(page)
    except Exception:
        _maybe_execute(page)
    wait_execute_done(page, timeout_ms=360_000)
    box3_txt = _wait_box3_result(page)
    log.add("r2_done", status="ok", shot=shot(page, run_dir, "r2_03_box3"))

    pipe = _pipe()
    box2 = _box2(page)
    art = _save_result(run_dir, pipe.get("worker_outputs") or [])
    if (run_dir / "RESULT.html").is_file():
        (run_dir / "R2_RESULT.html").write_bytes((run_dir / "RESULT.html").read_bytes())
    scores = {
        "brainstorm": _score_brainstorm(
            box2, pipe, expect_keywords=["todo", "spalte", "html", "heute", "tastatur"]
        ),
        "flex": _score_flex(pipe),
        "result": _score_result(pipe, art, want_html=True),
    }
    tot = _total(scores)
    user = (pipe.get("user_text") or "").lower()
    task_hit = any(k in user for k in ("todo", "spalte", "html", "localstorage", "taste"))
    ok = (
        tot["pct"] >= 50
        and (task_hit or art.get("chars", 0) >= 800)
        and (art.get("chars", 0) >= 600 or len(box3_txt) > 80)
    )
    return {
        "id": "R2",
        "name": name,
        "ok": ok,
        "scores": scores,
        "total": tot,
        "detail": (
            f"pct={tot['pct']} chars={art.get('chars')} "
            f"interact={art.get('has_interaction')} box3={len(box3_txt)}"
        ),
        "artifact": art,
        "flex_notes": (pipe.get("flex_notes") or "")[:400],
        "box3_preview": box3_txt[:300],
    }


def scenario_r3_flex_wish_support(page, run_dir: Path, log: StepLog) -> dict:
    """R3 — Flex soll Vorlieben (dunkel + Deutsch) erkennen und unterstützen."""
    name = "flex_wuensche"
    api_reset(BASE)
    try:
        http_json(
            BASE,
            "POST",
            "/api/memory/warm",
            {"text": "User: immer dunkles Theme und deutsche UI-Beschriftungen"},
            timeout=15,
        )
    except Exception:
        pass

    _prepare_deutsch_ui(page)
    page.goto(BASE + "/?e2e=real-r3&lang=de", wait_until="domcontentloaded")
    page.wait_for_selector("#chat-input", state="visible")
    page.evaluate("() => { document.documentElement.style.zoom = '0.85'; }")
    page.locator("body").click(position={"x": 50, "y": 50})
    log.add("r3_open", status="ok", shot=shot(page, run_dir, "r3_01_open"))

    text = (
        "Bitte eine kleine Portfolio-Landingpage für die Fotografin Lena Berg. "
        "Hero, drei Arbeiten als Karten, Kontakt. "
        "Berücksichtige meine Vorlieben — dunkel und deutsche Texte."
    )
    _user_type(page, text)
    _user_send(page)
    try:
        wait_brainstorm_ready(page, timeout_ms=180_000)
        log.add("r3_brain", status="ok", shot=shot(page, run_dir, "r3_02_brain"))
        time.sleep(3.0 if HEADED else 0.3)
        _maybe_execute(page)
    except Exception:
        _maybe_execute(page)
    wait_execute_done(page, timeout_ms=360_000)
    box3_txt = _wait_box3_result(page)
    log.add("r3_done", status="ok", shot=shot(page, run_dir, "r3_03_box3"))

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
    ok = tot["pct"] >= 45 and (art.get("chars", 0) >= 500 or len(box3_txt) > 80)
    return {
        "id": "R3",
        "name": name,
        "ok": ok,
        "scores": scores,
        "total": tot,
        "detail": (
            f"pct={tot['pct']} dark={dark_ok} de={de_ok} "
            f"chars={art.get('chars')} box3={len(box3_txt)}"
        ),
        "artifact": art,
        "flex_notes": (pipe.get("flex_notes") or "")[:400],
        "wish_reflected": {"dark": dark_ok, "germanish": de_ok},
        "box3_preview": box3_txt[:300],
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
    print("ECHTER USER-TEST — ich spiele dich (Maus + Tastatur, DEUTSCH)")
    print(f"  base={BASE}  sichtbar={HEADED}  slow_ms={SLOW_MS}  tippen={TYPE_DELAY}")
    print(f"  out={run_dir}")
    print("  → Chromium-Fenster beobachten (Box 2 Brainstorm, Box 3 Ergebnis)")
    print("=" * 60)

    from playwright.sync_api import sync_playwright

    scenarios_out: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not HEADED,
            slow_mo=SLOW_MS,
            args=["--start-maximized"] if HEADED else None,
        )
        context = browser.new_context(
            # Großes Fenster + DE — UI soll komplett sichtbar sein
            viewport={"width": 1680, "height": 1050} if HEADED else {"width": 1400, "height": 900},
            locale="de-DE",
            no_viewport=False,
        )
        page = context.new_page()
        page.set_default_timeout(120_000)

        for key in only:
            meta = SCENARIOS.get(key)
            if not meta:
                print(f"  unbekannter Test {key} — übersprungen")
                continue
            sid, fn = meta
            print(f"\n▶ {sid} startet (Deutsch, sichtbares UI)…")
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
