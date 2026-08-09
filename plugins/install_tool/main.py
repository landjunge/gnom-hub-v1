"""install_tool plugin – allowlisted package check + pip install.

Only packages needed for computer-use / tools may be installed.
Runs with hub privileges; keep the allowlist tight.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from typing import Any

# Short name → (pip name, import name)
_ALLOW: dict[str, tuple[str, str]] = {
    "playwright": ("playwright", "playwright"),
    "pyautogui": ("pyautogui", "pyautogui"),
    "mss": ("mss", "mss"),
    "pillow": ("Pillow", "PIL"),
    "pil": ("Pillow", "PIL"),
    "pytesseract": ("pytesseract", "pytesseract"),
    "pynput": ("pynput", "pynput"),
    "beautifulsoup4": ("beautifulsoup4", "bs4"),
    "bs4": ("beautifulsoup4", "bs4"),
    "lxml": ("lxml", "lxml"),
}


def _is_installed(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def _pip_install(pip_name: str) -> dict[str, Any]:
    cmd = [sys.executable, "-m", "pip", "install", "--quiet", pip_name]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-1500:],
            "stderr": (proc.stderr or "")[-1000:],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _playwright_install_browsers() -> dict[str, Any]:
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-1500:],
            "stderr": (proc.stderr or "")[-1000:],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def run(package: str = "", dry_run: bool = False) -> dict[str, Any]:
    """Check and optionally install an allowlisted package.

    Parameters
    ----------
    package :
        Short name or pip name (playwright, pyautogui, mss, …).
    dry_run :
        If True, only report whether the package is present.
    """
    key = (package or "").strip().lower()
    if not key:
        return {"ok": False, "error": "package is required"}

    if key not in _ALLOW:
        return {
            "ok": False,
            "error": f"package not allowlisted: {package!r}",
            "allowed": sorted(_ALLOW.keys()),
        }

    pip_name, import_name = _ALLOW[key]
    already = _is_installed(import_name)

    result: dict[str, Any] = {
        "ok": True,
        "package": key,
        "pip_name": pip_name,
        "import_name": import_name,
        "already_installed": already,
        "dry_run": bool(dry_run),
    }

    if already:
        result["message"] = f"{pip_name} already installed"
        # For playwright still offer browser install check if requested later
        return result

    if dry_run:
        result["message"] = f"would install {pip_name}"
        return result

    install = _pip_install(pip_name)
    result["install"] = install
    if not install.get("ok"):
        result["ok"] = False
        result["message"] = f"failed to install {pip_name}"
        return result

    # Re-check after install
    result["already_installed"] = _is_installed(import_name)
    result["message"] = f"installed {pip_name}"

    if key == "playwright":
        browsers = _playwright_install_browsers()
        result["playwright_browsers"] = browsers
        if not browsers.get("ok"):
            result["ok"] = False
            result["message"] += " (package ok, chromium install failed)"

    return result
