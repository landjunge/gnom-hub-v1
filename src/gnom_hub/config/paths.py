"""Hub code root vs personal workspace — one simple rule.

  gnom-hub-v1/              ← code, temp clutter, Clear
  WS-gnom-hub-v1/           ← YOURS only (or GNOM_WS=…)

No home paths, no hub/User live store, no seed chains.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_WS_NAME = "WS-gnom-hub-v1"
USER_DIR_NAME = "User"
SELECTED_DIR_NAME = "selected"


def project_root() -> Path:
    """Hub code root: …/src/gnom_hub/config/paths.py → four parents up."""
    return Path(__file__).resolve().parents[3]


def is_usb_root(path: Path | None = None) -> bool:
    base = Path(path) if path is not None else project_root()
    try:
        s = str(base.resolve())
    except OSError:
        s = str(base)
    return s.startswith(("/Volumes/", "/media/", "/run/media/", "/mnt/"))


def is_real_hub_root(root: Path | None = None) -> bool:
    """True for installed hub, false for pytest tmp roots."""
    r = Path(root) if root is not None else project_root()
    try:
        return r.resolve() == project_root().resolve()
    except OSError:
        return False


def personal_workspace(root: Path | None = None) -> Path:
    """
    Personal data root.

    - tests/tmp roots: always that root (ignore GNOM_WS — isolation)
    - real hub: GNOM_WS if set, else sibling WS-gnom-hub-v1
    """
    hub = Path(root) if root is not None else project_root()
    if not is_real_hub_root(hub):
        return hub.resolve()
    env = (os.getenv("GNOM_WS") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (hub.parent / DEFAULT_WS_NAME).resolve()


def user_dir(root: Path | None = None) -> Path:
    return (personal_workspace(root) / USER_DIR_NAME).resolve()


def selected_dir(root: Path | None = None) -> Path:
    return (personal_workspace(root) / SELECTED_DIR_NAME).resolve()


def backups_dir(root: Path | None = None) -> Path:
    return (personal_workspace(root) / "backups").resolve()


def pin_gnom_ws_env(hub_root: Path | None = None) -> Path:
    """Pin GNOM_WS in process env for the real hub only (never for tests)."""
    hub = Path(hub_root) if hub_root is not None else project_root()
    ws = personal_workspace(hub)
    if is_real_hub_root(hub):
        os.environ.setdefault("GNOM_WS", str(ws))
    return ws
