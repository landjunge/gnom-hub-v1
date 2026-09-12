"""
Plugin install_tool — agents self-heal missing deps (pip allowlist only).

API (agents):
  install_tool(package|name, dry_run=False, install_browsers=True for playwright)
  install_tool_check(package|name)
  install_tool_stack(which=all|browser|gui)
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Any

# Tight allowlist (user/product rule)
ALLOWED: dict[str, dict[str, str]] = {
    "playwright": {"import": "playwright", "pip": "playwright"},
    "pyautogui": {"import": "pyautogui", "pip": "pyautogui"},
    "mss": {"import": "mss", "pip": "mss"},
    "pillow": {"import": "PIL", "pip": "Pillow"},
    "pytesseract": {"import": "pytesseract", "pip": "pytesseract"},
    "pynput": {"import": "pynput", "pip": "pynput"},
    "beautifulsoup4": {"import": "bs4", "pip": "beautifulsoup4"},
    "bs4": {"import": "bs4", "pip": "beautifulsoup4"},
    "lxml": {"import": "lxml", "pip": "lxml"},
}

_ALIASES = {
    "pil": "pillow",
    "bs4": "beautifulsoup4",
    "beautiful_soup": "beautifulsoup4",
    "pw": "playwright",
    "browser": "playwright",
    "mouse": "pyautogui",
    "gui": "pyautogui",
    "ocr": "pytesseract",
    "tesseract": "pytesseract",
}


def _norm(name: str) -> str:
    n = (name or "").strip().lower().replace("-", "_")
    if n in _ALIASES:
        n = _ALIASES[n]
    if n == "pillow":
        return "pillow"
    if n == "beautifulsoup4" or n == "bs4":
        return "beautifulsoup4"
    return n


def _meta(key: str) -> dict[str, str] | None:
    k = _norm(key)
    if k in ALLOWED:
        return ALLOWED[k]
    # also try original with hyphen for pip name keys
    for ak, meta in ALLOWED.items():
        if ak.replace("_", "") == k.replace("_", ""):
            return meta
    return None


def _check(key: str) -> dict[str, Any]:
    meta = _meta(key)
    if not meta:
        return {
            "ok": False,
            "installed": False,
            "error": f"package not allowlisted: {key!r}",
            "allowed": sorted(set(ALLOWED) - {"bs4"}),
        }
    try:
        importlib.import_module(meta["import"])
        return {
            "ok": True,
            "installed": True,
            "package": _norm(key),
            "import": meta["import"],
            "pip": meta["pip"],
        }
    except BaseException as exc:  # noqa: BLE001
        # Some optional GUI deps (e.g. pyautogui → mouseinfo) call sys.exit()
        # instead of raising ImportError when a system lib (tkinter) is
        # missing. SystemExit/BaseException must be caught here too, or a
        # single availability check crashes the whole caller (agent/tests).
        return {
            "ok": True,
            "installed": False,
            "package": _norm(key),
            "import": meta["import"],
            "pip": meta["pip"],
            "error": str(exc) or exc.__class__.__name__,
        }


def _playwright_chromium() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "exit": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-800:],
            "stderr_tail": (proc.stderr or "")[-400:],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def install_tool_check(name: str = "", package: str = "") -> dict[str, Any]:
    """Check only — never install."""
    pkg = (package or name or "").strip()
    if not pkg:
        return {"ok": False, "error": "package (or name) required"}
    return _check(pkg)


def install_tool(
    name: str = "",
    package: str = "",
    dry_run: bool = False,
    install_browsers: bool = False,
) -> dict[str, Any]:
    """
    Ensure allowlisted package is importable.

    dry_run=True → only report would_install / already installed, no pip.
    package preferred; name kept for older callers.
    """
    pkg = (package or name or "").strip()
    if not pkg:
        return {"ok": False, "error": "package (or name) required"}
    meta = _meta(pkg)
    if not meta:
        return {
            "ok": False,
            "error": f"refused: {pkg!r} not in allowlist",
            "allowed": sorted(set(ALLOWED) - {"bs4"}),
        }
    key = _norm(pkg)
    pre = _check(key)
    if pre.get("installed"):
        out: dict[str, Any] = {
            "ok": True,
            "already": True,
            "dry_run": bool(dry_run),
            "package": key,
            "detail": f"{key} already importable",
        }
        if key == "playwright" and install_browsers and not dry_run:
            out["browsers"] = _playwright_chromium()
        return out

    if dry_run:
        return {
            "ok": True,
            "already": False,
            "dry_run": True,
            "would_install": meta["pip"],
            "package": key,
            "detail": f"would pip install {meta['pip']}",
            "install_browsers": bool(install_browsers) and key == "playwright",
        }

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", meta["pip"]],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "package": key, "error": f"pip failed: {exc}"}

    post = _check(key)
    result: dict[str, Any] = {
        "ok": bool(post.get("installed")),
        "already": False,
        "dry_run": False,
        "package": key,
        "pip": meta["pip"],
        "pip_exit": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-1200:],
        "stderr_tail": (proc.stderr or "")[-600:],
        "installed": bool(post.get("installed")),
    }
    if key == "playwright" and result["ok"] and install_browsers:
        result["browsers"] = _playwright_chromium()
    if not result["ok"]:
        result["error"] = post.get("error") or "import still failing after pip"
    return result


def install_tool_stack(which: str = "all", dry_run: bool = False) -> dict[str, Any]:
    w = (which or "all").strip().lower()
    if w in ("browser", "playwright", "pw"):
        wanted = ["playwright"]
    elif w in ("gui", "mouse", "pyautogui"):
        wanted = ["pyautogui", "pillow", "mss", "pynput"]
    elif w in ("ocr",):
        wanted = ["pytesseract", "pillow"]
    elif w in ("scrape", "html"):
        wanted = ["beautifulsoup4", "lxml"]
    else:
        wanted = ["playwright", "pyautogui", "pillow", "mss"]

    results = []
    all_ok = True
    for pkg in wanted:
        r = install_tool(
            package=pkg,
            dry_run=bool(dry_run),
            install_browsers=(pkg == "playwright" and not dry_run),
        )
        results.append(r)
        if not r.get("ok"):
            all_ok = False
    return {
        "ok": all_ok,
        "which": w,
        "dry_run": bool(dry_run),
        "packages": results,
        "note": "pip allowlist only — no free apt",
    }
