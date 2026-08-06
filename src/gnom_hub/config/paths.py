"""Project root and relative path helpers (USB-capable)."""

from __future__ import annotations

from pathlib import Path

# Personal unit in the workspace (never pushed: Key.txt + user.db).
USER_DIR_NAME = "User"


def project_root() -> Path:
    """Repo root: …/src/gnom_hub/config/paths.py → four parents up."""
    return Path(__file__).resolve().parents[3]


def user_dir(root: Path | None = None) -> Path:
    """
    Workspace personal folder: {root}/User/

    Holds Key.txt (API keys) and user.db (WARM/HOT personal store).
    Sync this folder in your own workflow — never git-push secrets/db.
    """
    base = Path(root) if root is not None else project_root()
    return (base / USER_DIR_NAME).resolve()
