"""
Controlled dependency install for agent tools.

Agents must NOT run arbitrary apt/pip. Only packages from ALLOWED_PACKAGES
may be installed via the current Python (venv) interpreter.
Playwright browsers use `playwright install chromium`.
"""

from __future__ import annotations

import importlib
import platform
import subprocess
import sys
from typing import Any

# name -> import module / optional pip extra
ALLOWED_PACKAGES: dict[str, dict[str, str]] = {
    "playwright": {"import": "playwright", "pip": "playwright"},
    "pyautogui": {"import": "pyautogui", "pip": "pyautogui"},
    "pillow": {"import": "PIL", "pip": "Pillow"},
    "pillow_pil": {"import": "PIL", "pip": "Pillow"},
}

# Aliases agents might request
_ALIASES = {
    "pil": "pillow",
    "pillow": "pillow",
    "pw": "playwright",
    "browser": "playwright",
    "mouse": "pyautogui",
    "keyboard": "pyautogui",
    "gui": "pyautogui",
}


def _norm(name: str) -> str:
    n = (name or "").strip().lower().replace("_", "-")
    if n in _ALIASES:
        n = _ALIASES[n]
    # map back to keys
    if n == "pillow":
        return "pillow"
    return n.replace("-", "_") if n.replace("-", "_") in ALLOWED_PACKAGES else n


def check_package(name: str) -> dict[str, Any]:
    key = _norm(name)
    meta = ALLOWED_PACKAGES.get(key)
    if not meta:
        return {
            "ok": False,
            "installed": False,
            "error": f"package not allowlisted: {name!r}",
            "allowed": sorted(ALLOWED_PACKAGES.keys()),
        }
    mod = meta["import"]
    try:
        importlib.import_module(mod)
        return {"ok": True, "installed": True, "name": key, "import": mod}
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "installed": False,
            "name": key,
            "import": mod,
            "error": str(exc),
        }


def ensure_package(name: str, *, install_browsers: bool = False) -> dict[str, Any]:
    """
    Ensure allowlisted package is importable; pip install if missing.
    """
    key = _norm(name)
    meta = ALLOWED_PACKAGES.get(key)
    if not meta:
        return {
            "ok": False,
            "error": f"refused: {name!r} not in allowlist",
            "allowed": sorted(ALLOWED_PACKAGES.keys()),
            "hint": "Only playwright, pyautogui, pillow — no free apt/pip.",
        }
    pre = check_package(key)
    if pre.get("installed"):
        out: dict[str, Any] = {
            "ok": True,
            "already": True,
            "name": key,
            "detail": f"{key} already importable",
        }
        if key == "playwright" and install_browsers:
            out["browsers"] = _playwright_install_chromium()
        return out

    pip_name = meta["pip"]
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", pip_name],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "name": key, "error": f"pip failed: {exc}"}

    post = check_package(key)
    result: dict[str, Any] = {
        "ok": bool(post.get("installed")),
        "already": False,
        "name": key,
        "pip": pip_name,
        "pip_exit": proc.returncode,
        "pip_stdout": (proc.stdout or "")[-1500:],
        "pip_stderr": (proc.stderr or "")[-800:],
        "installed": bool(post.get("installed")),
        "platform": platform.system(),
    }
    if key == "playwright" and result["ok"] and install_browsers:
        result["browsers"] = _playwright_install_chromium()
    if not result["ok"]:
        result["error"] = post.get("error") or "import still failing after pip"
    return result


def _playwright_install_chromium() -> dict[str, Any]:
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
            "stdout": (proc.stdout or "")[-1200:],
            "stderr": (proc.stderr or "")[-600:],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def ensure_tool_stack(which: str = "all") -> dict[str, Any]:
    """
    Ensure agent tool stack.

    which: all | browser | gui | playwright | pyautogui
    """
    w = (which or "all").strip().lower()
    wanted: list[str]
    if w in ("browser", "playwright", "pw"):
        wanted = ["playwright"]
    elif w in ("gui", "mouse", "keyboard", "pyautogui"):
        wanted = ["pyautogui", "pillow"]
    else:
        wanted = ["playwright", "pyautogui", "pillow"]

    results = []
    all_ok = True
    for pkg in wanted:
        r = ensure_package(pkg, install_browsers=(pkg == "playwright"))
        results.append(r)
        if not r.get("ok"):
            all_ok = False
    return {
        "ok": all_ok,
        "which": w,
        "packages": results,
        "note": "apt is not used (macOS desk); pip allowlist only.",
    }
