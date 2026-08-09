#!/usr/bin/env python3
"""
Find or open a Google Chrome tab for the Gnom-Hub UI.

User rule (mandatory for agents):
  1) Search Chrome for an open tab whose URL contains the Gnom host/IP (e.g. 127.0.0.1:8080).
  2) Reuse that tab (bring to front).
  3) Only open a *new* tab if none matches.

Prefers Chrome DevTools CDP (port 9222). Falls back to AppleScript / `open`.

Usage:
  python scripts/gnom_chrome_tab.py
  python scripts/gnom_chrome_tab.py --base http://127.0.0.1:8080
  GNOM_E2E_CDP=http://127.0.0.1:9222 python scripts/gnom_chrome_tab.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from urllib.parse import urlparse

DEFAULT_BASE = os.environ.get("GNOM_E2E_BASE", "http://127.0.0.1:8080").rstrip("/")
CDP = os.environ.get("GNOM_E2E_CDP", "http://127.0.0.1:9222").rstrip("/")


def _host_markers(base: str) -> list[str]:
    u = urlparse(base if "://" in base else "http://" + base)
    host = (u.hostname or "127.0.0.1").lower()
    port = u.port
    markers = [host]
    if port:
        markers.append(f"{host}:{port}")
        markers.append(f"localhost:{port}")
        if host in ("127.0.0.1", "localhost"):
            markers.append(f"127.0.0.1:{port}")
            markers.append(f"localhost:{port}")
    # path-less base for contains checks
    markers.append(base.replace("http://", "").replace("https://", ""))
    # unique, keep order
    seen: set[str] = set()
    out: list[str] = []
    for m in markers:
        m = m.strip().lower()
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _url_matches_gnom(url: str, markers: list[str]) -> bool:
    u = (url or "").lower()
    if not u or u.startswith(("devtools://", "chrome://")):
        return False
    return any(m in u for m in markers)


def cdp_json(path: str, timeout: float = 2.0) -> Any | None:
    try:
        req = urllib.request.Request(CDP + path, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def cdp_available() -> bool:
    return cdp_json("/json/version") is not None


def cdp_list_targets() -> list[dict[str, Any]]:
    data = cdp_json("/json")
    if not isinstance(data, list):
        return []
    return [t for t in data if isinstance(t, dict)]


def cdp_find_gnom_tab(base: str) -> dict[str, Any] | None:
    markers = _host_markers(base)
    pages = [
        t
        for t in cdp_list_targets()
        if (t.get("type") or "page") == "page"
        and _url_matches_gnom(str(t.get("url") or ""), markers)
    ]
    if not pages:
        return None
    # Prefer exact base prefix
    for t in pages:
        if str(t.get("url") or "").startswith(base):
            return t
    return pages[0]


def cdp_activate(target_id: str) -> bool:
    # /json/activate/<id>
    try:
        req = urllib.request.Request(
            CDP + "/json/activate/" + urllib.parse.quote(target_id), method="GET"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp.read()
        return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def cdp_new_tab(base: str) -> dict[str, Any] | None:
    # /json/new?url
    url = base if base.endswith("/") else base + "/"
    try:
        path = "/json/new?" + urllib.parse.quote(url, safe="")
        req = urllib.request.Request(CDP + path, method="PUT")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        # older Chrome: GET
        try:
            path = "/json/new?" + urllib.parse.quote(url, safe="")
            req = urllib.request.Request(CDP + path, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return None


def applescript_find_or_open(base: str) -> tuple[bool, str]:
    """Control the user's real Google Chrome tabs (macOS)."""
    markers = _host_markers(base)
    # Build AppleScript that checks URL contains any marker
    or_checks = " or ".join([f'(tabURL contains "{m}")' for m in markers[:8]])
    url = base if base.endswith("/") else base + "/"
    script = f'''
    set targetURL to "{url}"
    tell application "Google Chrome"
      if not (exists window 1) then
        make new window
      end if
      set found to false
      set winIndex to 1
      repeat with w in windows
        set tabIndex to 1
        repeat with t in tabs of w
          set tabURL to URL of t
          if {or_checks} then
            set active tab index of w to tabIndex
            set index of w to 1
            set found to true
            exit repeat
          end if
          set tabIndex to tabIndex + 1
        end repeat
        if found then exit repeat
        set winIndex to winIndex + 1
      end repeat
      if found then
        activate
        return "reuse"
      else
        tell window 1
          make new tab with properties {{URL:targetURL}}
        end tell
        activate
        return "new"
      end if
    end tell
    '''
    try:
        r = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if r.returncode == 0:
            return True, (r.stdout or "").strip() or "ok"
        return False, (r.stderr or r.stdout or "osascript failed").strip()
    except (subprocess.SubprocessError, OSError) as exc:
        return False, str(exc)


def open_via_system(base: str) -> None:
    url = base if base.endswith("/") else base + "/"
    try:
        subprocess.run(
            ["/usr/bin/open", "-a", "Google Chrome", url],
            check=False,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        subprocess.run(["/usr/bin/open", url], check=False, timeout=10)


def ensure_gnom_tab(base: str = DEFAULT_BASE) -> dict[str, Any]:
    """
    Ensure a Chrome tab is on the Gnom UI.

    Returns {ok, method, action: reuse|new, url?, cdp?, detail?}
    """
    base = (base or DEFAULT_BASE).rstrip("/")
    # 1) CDP — best for Playwright attach + tab reuse
    if cdp_available():
        hit = cdp_find_gnom_tab(base)
        if hit:
            tid = str(hit.get("id") or "")
            if tid:
                cdp_activate(tid)
            return {
                "ok": True,
                "method": "cdp",
                "action": "reuse",
                "url": hit.get("url"),
                "cdp": CDP,
                "id": tid,
            }
        created = cdp_new_tab(base)
        if created:
            return {
                "ok": True,
                "method": "cdp",
                "action": "new",
                "url": created.get("url") or base,
                "cdp": CDP,
                "id": created.get("id"),
            }
        return {
            "ok": False,
            "method": "cdp",
            "action": "fail",
            "detail": "cdp new tab failed",
            "cdp": CDP,
        }

    # 2) AppleScript — user's real Chrome windows/tabs
    ok, detail = applescript_find_or_open(base)
    if ok:
        action = "reuse" if detail == "reuse" else "new"
        return {"ok": True, "method": "applescript", "action": action, "detail": detail}

    # 3) Last resort: open URL (may create a tab; cannot search first)
    open_via_system(base)
    return {
        "ok": True,
        "method": "open",
        "action": "new",
        "detail": "CDP+AppleScript unavailable; opened URL in Chrome",
        "hint": (
            "For reliable tab reuse + live E2E, start Chrome once with:\n"
            "  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome "
            f"--remote-debugging-port=9222\n"
            f"Then leave a tab on {base}"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Find or open Gnom-Hub tab in Google Chrome")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = ensure_gnom_tab(args.base)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"gnom-tab: ok={result.get('ok')} method={result.get('method')} "
            f"action={result.get('action')} url={result.get('url') or args.base}"
        )
        if result.get("detail"):
            print(f"  detail: {result['detail']}")
        if result.get("hint"):
            print(result["hint"])
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
