"""Minimal dual workspace: temp + permanent (relative, USB-capable)."""

from __future__ import annotations

import shutil
from pathlib import Path

from gnom_hub.config.paths import project_root
from gnom_hub.memory.atomic import atomic_write_text


class WorkspaceStore:
    """
    data/workspace/temp  — scratch
    data/workspace/perm  — keep
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.base = self.root / "data" / "workspace"
        self.temp = self.base / "temp"
        self.perm = self.base / "perm"
        self.temp.mkdir(parents=True, exist_ok=True)
        self.perm.mkdir(parents=True, exist_ok=True)

    def list_files(self, which: str = "temp") -> list[dict[str, str | int]]:
        folder = self._dir(which)
        out: list[dict[str, str | int]] = []
        for p in sorted(folder.iterdir()):
            if p.is_file():
                out.append({"name": p.name, "bytes": p.stat().st_size, "zone": which})
        return out

    def write_text(self, which: str, name: str, content: str) -> Path:
        safe = Path(name).name
        path = self._dir(which) / safe
        atomic_write_text(path, content)
        return path

    def promote(self, name: str) -> Path:
        """Copy temp → perm."""
        safe = Path(name).name
        src = self.temp / safe
        if not src.is_file():
            raise FileNotFoundError(safe)
        dst = self.perm / safe
        shutil.copy2(src, dst)
        return dst

    def clear_temp(self) -> int:
        n = 0
        for p in self.temp.iterdir():
            if p.is_file():
                p.unlink()
                n += 1
        return n

    def snapshot(self) -> dict:
        return {
            "temp": self.list_files("temp"),
            "perm": self.list_files("perm"),
            "paths": {"temp": str(self.temp), "perm": str(self.perm)},
        }

    def _dir(self, which: str) -> Path:
        w = which.strip().lower()
        if w in ("temp", "temporary", "tmp"):
            return self.temp
        if w in ("perm", "permanent", "keep"):
            return self.perm
        raise ValueError(f"Unknown workspace zone: {which!r}")
