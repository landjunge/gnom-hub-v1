#!/usr/bin/env python3
"""Headed Playwright probe: scrollbars and overlapping desk chrome.

Fails when boxes, chat, tabs, or action buttons cover each other or when
chrome grows a scrollbar that hides controls.

  GNOM_E2E_HEADED=1 python scripts/layout_overlap_e2e.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from e2e_lib import http_ok, shot

BASE = os.environ.get("GNOM_E2E_BASE", "http://127.0.0.1:8080").rstrip("/")
HEADED = os.environ.get("GNOM_E2E_HEADED", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)
OUT = ROOT / "data" / "e2e-layout"
VIEWPORTS = (
    {"name": "desk-1280", "width": 1280, "height": 800},
    {"name": "desk-1440", "width": 1440, "height": 900},
    {"name": "desk-1100", "width": 1100, "height": 720},
)

PROBE_JS = r"""() => {
  const ids = [
    "app", "agent-cards", "box1", "box2", "box3", "chat-mod",
    "btn-send", "btn-execute", "btn-send-exec", "chat-input"
  ];
  function box(el) {
    const r = el.getBoundingClientRect();
    return {
      id: el.id || el.className,
      x: Math.round(r.x), y: Math.round(r.y),
      w: Math.round(r.width), h: Math.round(r.height),
      right: Math.round(r.right), bottom: Math.round(r.bottom),
      visible: r.width > 1 && r.height > 1
        && r.bottom > 0 && r.right > 0
        && r.top < window.innerHeight && r.left < window.innerWidth
    };
  }
  function areaOverlap(a, b) {
    const x = Math.max(0, Math.min(a.right, b.right) - Math.max(a.x, b.x));
    const y = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y));
    return x * y;
  }
  const nodes = {};
  for (const id of ids) {
    const el = document.getElementById(id);
    if (el) nodes[id] = { el, r: box(el) };
  }
  const overlaps = [];
  const pairs = [
    ["agent-cards", "box1"],
    ["agent-cards", "box2"],
    ["agent-cards", "box3"],
    ["box1", "box2"],
    ["box1", "box3"],
    ["box2", "box3"],
    ["chat-mod", "box1"],
    ["chat-mod", "box3"],
    ["chat-mod", "agent-cards"],
  ];
  for (const [a, b] of pairs) {
    if (!nodes[a] || !nodes[b]) continue;
    const px = areaOverlap(nodes[a].r, nodes[b].r);
    if (px > 40) overlaps.push({ a, b, px });
  }

  const navs = [...document.querySelectorAll(".box-agent-nav")].map((el) => {
    const r = el.getBoundingClientRect();
    const parent = el.closest(".box");
    const pr = parent ? parent.getBoundingClientRect() : r;
    return {
      box: parent ? parent.id : "?",
      w: Math.round(r.width),
      h: Math.round(r.height),
      scrollW: el.scrollWidth,
      scrollH: el.scrollHeight,
      clientW: el.clientWidth,
      clientH: el.clientHeight,
      overflowX: el.scrollWidth - el.clientWidth,
      overflowY: el.scrollHeight - el.clientHeight,
      coversParentTop: r.height > 48,
      clippedByParent: r.right > pr.right + 1 || r.bottom > pr.bottom + 1,
    };
  });

  const scrollers = [];
  const scan = [
    document.getElementById("app"),
    document.querySelector(".boxes"),
    document.getElementById("box1"),
    document.getElementById("box2"),
    document.getElementById("box3"),
    document.getElementById("chat-mod"),
    document.getElementById("agent-cards"),
    ...document.querySelectorAll(".box-agent-nav"),
  ].filter(Boolean);
  for (const el of scan) {
    const dx = el.scrollWidth - el.clientWidth;
    const dy = el.scrollHeight - el.clientHeight;
    const cs = getComputedStyle(el);
    if (dx > 4 || dy > 4) {
      scrollers.push({
        id: el.id || el.className.split(" ")[0] || el.tagName,
        dx, dy,
        overflow: cs.overflow,
        overflowX: cs.overflowX,
        overflowY: cs.overflowY,
      });
    }
  }

  const controls = ["btn-send", "btn-execute", "btn-send-exec", "chat-input"].map((id) => {
    const el = document.getElementById(id);
    if (!el) return { id, missing: true };
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const top = document.elementFromPoint(cx, cy);
    const covered = !!(top && el !== top && !el.contains(top) && !top.contains(el));
    const clipped = r.width < 8 || r.height < 8
      || r.bottom > window.innerHeight - 2
      || r.right > window.innerWidth - 2
      || r.top < 0;
    return {
      id,
      w: Math.round(r.width), h: Math.round(r.height),
      visible: r.width > 8 && r.height > 8,
      coveredBy: covered ? (top.id || top.className || top.tagName) : null,
      clipped,
    };
  });

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const app = document.getElementById("app");
  const appR = app ? app.getBoundingClientRect() : null;

  return {
    viewport: { w: vw, h: vh },
    app: appR ? box(app) : null,
    nodes: Object.fromEntries(Object.entries(nodes).map(([k, v]) => [k, v.r])),
    overlaps,
    navs,
    scrollers,
    controls,
    tabCount: document.querySelectorAll(".box-agent-tab").length,
  };
}"""


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def evaluate(probe: dict) -> list[str]:
    fails: list[str] = []
    for o in probe.get("overlaps") or []:
        fails.append(f"overlap {o['a']}×{o['b']} {o['px']}px")
    for nav in probe.get("navs") or []:
        if nav.get("overflowX", 0) > 8:
            fails.append(f"{nav['box']} tab-bar horizontal scroll +{nav['overflowX']}px")
        if nav.get("h", 0) > 80:
            fails.append(f"{nav['box']} tab-bar too tall ({nav['h']}px)")
    for s in probe.get("scrollers") or []:
        sid = s.get("id") or "?"
        if sid in ("app", "boxes", "box1", "box2", "box3", "agent-cards"):
            if s.get("dx", 0) > 8:
                fails.append(f"chrome {sid} horizontal scrollbar +{s['dx']}px")
            if s.get("dy", 0) > 8 and sid in ("app", "boxes", "agent-cards"):
                fails.append(f"chrome {sid} vertical scrollbar +{s['dy']}px")
    for c in probe.get("controls") or []:
        if c.get("missing"):
            fails.append(f"control {c['id']} missing")
        elif c.get("coveredBy"):
            fails.append(f"control {c['id']} covered by {c['coveredBy']}")
        elif not c.get("visible") or c.get("clipped"):
            fails.append(f"control {c['id']} clipped/hidden")
    nodes = probe.get("nodes") or {}
    for bid in ("box1", "box2", "box3"):
        n = nodes.get(bid) or {}
        if (n.get("h") or 0) < 80:
            fails.append(f"{bid} too short ({n.get('h')}px)")
        if (n.get("w") or 0) < 80:
            fails.append(f"{bid} too narrow ({n.get('w')}px)")
    return fails


def main() -> int:
    if not http_ok(BASE):
        print(f"FAIL server not up at {BASE}", file=sys.stderr)
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("FAIL playwright not installed", file=sys.stderr)
        return 2

    run_dir = OUT / _utc()
    run_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "started": _utc(),
        "base": BASE,
        "headed": HEADED,
        "viewports": [],
        "ok": True,
    }
    print(f"layout overlap e2e  base={BASE} headed={HEADED}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not HEADED, slow_mo=80 if HEADED else 0)
        for vp in VIEWPORTS:
            context = browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = context.new_page()
            page.set_default_timeout(30_000)
            page.goto(BASE + f"/?layout={int(time.time())}", wait_until="domcontentloaded")
            page.wait_for_selector("#box1")
            page.wait_for_selector("#btn-send")
            page.wait_for_timeout(700)
            probe = page.evaluate(PROBE_JS)
            fails = evaluate(probe)
            shot(page, run_dir, vp["name"])
            entry = {
                "name": vp["name"],
                "viewport": {"width": vp["width"], "height": vp["height"]},
                "fails": fails,
                "probe": probe,
            }
            report["viewports"].append(entry)
            status = "PASS" if not fails else "FAIL"
            print(f"  {status} {vp['name']} {vp['width']}x{vp['height']}")
            for f in fails:
                print(f"    - {f}")
            if fails:
                report["ok"] = False
            context.close()
        browser.close()

    (run_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    latest = OUT / "LATEST"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    try:
        latest.symlink_to(run_dir.name)
    except OSError:
        (OUT / "latest_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"shots: {run_dir}")
    print("OVERALL", "PASS" if report["ok"] else "FAIL")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
