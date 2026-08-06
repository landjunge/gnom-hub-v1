"""Hub code root vs personal workspace (sibling WS-gnom-hub-v1)."""

from __future__ import annotations

import os
from pathlib import Path

# Code repo: /Users/…/gnom-hub-v1  (work happens here)
# Personal:  /Users/…/WS-gnom-hub-v1 (Key, DB, only selected HTML)
DEFAULT_WS_NAME = "WS-gnom-hub-v1"
USER_DIR_NAME = "User"
SELECTED_DIR_NAME = "selected"  # only user-chosen HTML copies


def project_root() -> Path:
    """Hub code root: …/src/gnom_hub/config/paths.py → four parents up."""
    return Path(__file__).resolve().parents[3]


def is_usb_root(path: Path | None = None) -> bool:
    """Heuristic: path sits on a typical removable mount."""
    base = Path(path) if path is not None else project_root()
    try:
        s = str(base.resolve())
    except OSError:
        s = str(base)
    return s.startswith(("/Volumes/", "/media/", "/run/media/", "/mnt/"))


def is_real_hub_root(root: Path | None = None) -> bool:
    """True when root is the actual installed hub (not a pytest tmp root)."""
    r = Path(root) if root is not None else project_root()
    try:
        return r.resolve() == project_root().resolve()
    except OSError:
        return False


def personal_workspace(root: Path | None = None) -> Path:
    """
    Your personal workspace (not the git hub).

    Real hub:
      GNOM_WS if set, else sibling {hub_parent}/WS-gnom-hub-v1
      Example:
        /Users/you/gnom-hub-v1     ← code, work here
        /Users/you/WS-gnom-hub-v1  ← Key, user.db, selected HTML only

    Tests / tmp roots: personal data stays under that root (isolated).
    """
    env = (os.getenv("GNOM_WS") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    hub = Path(root) if root is not None else project_root()
    if not is_real_hub_root(hub):
        return hub.resolve()
    return (hub.parent / DEFAULT_WS_NAME).resolve()


def user_dir(root: Path | None = None) -> Path:
    """{personal_workspace}/User/ — Key.txt + user.db (live)."""
    return (personal_workspace(root) / USER_DIR_NAME).resolve()


def selected_dir(root: Path | None = None) -> Path:
    """{personal_workspace}/selected/ — only HTML you explicitly copy in."""
    return (personal_workspace(root) / SELECTED_DIR_NAME).resolve()


def backups_dir(root: Path | None = None) -> Path:
    """{personal_workspace}/backups/ — latest user.db mirror."""
    return (personal_workspace(root) / "backups").resolve()
