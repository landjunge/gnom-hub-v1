"""Hub scratch workspace + copy of selected HTML into personal WS."""

from __future__ import annotations

import shutil
from pathlib import Path

from gnom_hub.config.paths import project_root, selected_dir
from gnom_hub.memory.atomic import atomic_write_text


class WorkspaceStore:
    """
    Hub (work):
      data/workspace/temp  — scratch
      data/workspace/perm  — hub-local keep

    Personal WS (only deliberate HTML):
      WS-…/selected/       — copy_to_selected()
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.base = self.root / "data" / "workspace"
        self.temp = self.base / "temp"
        self.perm = self.base / "perm"
        self.temp.mkdir(parents=True, exist_ok=True)
        self.perm.mkdir(parents=True, exist_ok=True)
        self.selected = selected_dir(self.root)
        self.selected.mkdir(parents=True, exist_ok=True)

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
        """Copy temp → perm (still on hub)."""
        safe = Path(name).name
        src = self.temp / safe
        if not src.is_file():
            raise FileNotFoundError(safe)
        dst = self.perm / safe
        shutil.copy2(src, dst)
        return dst

    def copy_to_selected(
        self,
        name: str,
        *,
        zone: str = "temp",
    ) -> Path:
        """
        Copy ONE chosen file into personal WS selected/ (HTML only).
        Does not bulk-copy — only the name you pick.
        """
        from gnom_hub.config.user_workspace import copy_selected_html

        safe = Path(name).name
        src = self._dir(zone) / safe
        if not src.is_file():
            # also allow reading from perm if zone was wrong
            alt = self.perm / safe if zone != "perm" else self.temp / safe
            if alt.is_file():
                src = alt
            else:
                raise FileNotFoundError(safe)
        return copy_selected_html(src, self.root)

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

    def list_selected(self) -> list[dict[str, str | int]]:
        out: list[dict[str, str | int]] = []
        if not self.selected.is_dir():
            return out
        for p in sorted(self.selected.iterdir()):
            if p.is_file() and p.suffix.lower() in (".html", ".htm"):
                out.append({"name": p.name, "bytes": p.stat().st_size, "zone": "selected"})
        return out

    def snapshot(self) -> dict:
        return {
            "temp": self.list_files("temp"),
            "perm": self.list_files("perm"),
            "selected": self.list_selected(),
            "paths": {
                "temp": str(self.temp),
                "perm": str(self.perm),
                "selected": str(self.selected),
            },
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
