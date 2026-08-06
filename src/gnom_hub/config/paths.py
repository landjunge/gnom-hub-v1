"""Project root and relative path helpers (USB-capable)."""

from __future__ import annotations

from pathlib import Path

# Personal unit in the workspace (never pushed: Key.txt + user.db).
# Lives next to the code — on disk, SSD, or USB stick. This is the sync unit.
USER_DIR_NAME = "User"


def project_root() -> Path:
    """Repo root: …/src/gnom_hub/config/paths.py → four parents up."""
    return Path(__file__).resolve().parents[3]


def is_usb_root(root: Path | None = None) -> bool:
    """Heuristic: workspace sits on a typical removable mount."""
    base = Path(root) if root is not None else project_root()
    try:
        s = str(base.resolve())
    except OSError:
        s = str(base)
    return s.startswith(("/Volumes/", "/media/", "/run/media/", "/mnt/"))


def user_dir(root: Path | None = None) -> Path:
    """
    Workspace personal folder: {root}/User/

    Always relative to the hub root — if the hub lives on a USB stick,
    User/ is created and updated on that stick. Sync/update this folder
    (Key.txt + user.db); never git-push secrets/db; not under ~/.local.
    """
    base = Path(root) if root is not None else project_root()
    return (base / USER_DIR_NAME).resolve()
