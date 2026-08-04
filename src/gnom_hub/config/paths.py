"""Project root and relative path helpers (USB-capable)."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Repo root: …/src/gnom_hub/config/paths.py → four parents up."""
    return Path(__file__).resolve().parents[3]
