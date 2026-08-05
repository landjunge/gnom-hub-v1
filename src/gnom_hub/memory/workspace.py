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

    def read_text(self, which: str, name: str, max_chars: int = 12000) -> str:
        safe = Path(name).name
        path = self._dir(which) / safe
        if not path.is_file():
            raise FileNotFoundError(safe)
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text

    def delete(self, which: str, name: str) -> bool:
        safe = Path(name).name
        path = self._dir(which) / safe
        if path.is_file():
            path.unlink()
            return True
        return False

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

    def export_zip(self, zone: str = "all") -> Path:
        """Zip temp, perm, or both into data/workspace/exports/."""
        import zipfile
        from datetime import datetime, timezone

        z = (zone or "all").strip().lower()
        if z in ("temp", "temporary", "tmp"):
            folders = [("temp", self.temp)]
            tag = "temp"
        elif z in ("perm", "permanent", "keep"):
            folders = [("perm", self.perm)]
            tag = "perm"
        elif z in ("all", "both", "*"):
            folders = [("temp", self.temp), ("perm", self.perm)]
            tag = "all"
        else:
            raise ValueError(f"Unknown workspace zone: {zone!r}")

        export_dir = self.base / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = export_dir / f"gnom-hub-workspace-{tag}-{stamp}.zip"
        count = 0
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for label, folder in folders:
                if not folder.is_dir():
                    continue
                for p in sorted(folder.iterdir()):
                    if p.is_file():
                        zf.write(p, arcname=f"{label}/{p.name}")
                        count += 1
        if count == 0:
            # still return empty zip for consistent API
            pass
        return out

    def _dir(self, which: str) -> Path:
        w = which.strip().lower()
        if w in ("temp", "temporary", "tmp"):
            return self.temp
        if w in ("perm", "permanent", "keep"):
            return self.perm
        raise ValueError(f"Unknown workspace zone: {which!r}")
