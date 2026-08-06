"""Backup zip create/list/restore (extracted from Hub — pure move)."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BackupOpsMixin:
    """Mixin: expects Hub attributes (root, hot, warm, agents, …)."""

    def create_backup(self) -> dict[str, Any]:
        """Zip HOT + WARM + agents + checkpoint into data/backups/."""

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = self.root / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        path = backup_dir / f"gnom-hub-backup-{stamp}.zip"
        # Ensure current state on disk
        self.hot.save()
        self.warm.save()
        self._save_agent_state()
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for folder in ("hot", "warm"):
                base = self.root / "data" / folder
                if not base.is_dir():
                    continue
                for f in base.rglob("*"):
                    if f.is_file():
                        zf.write(f, arcname=str(f.relative_to(self.root / "data")))
        self._append_trace("backup.create", {"path": str(path)})
        return {"ok": True, "path": str(path), "bytes": path.stat().st_size}

    def list_backups(self) -> list[dict[str, Any]]:
        backup_dir = self.root / "data" / "backups"
        if not backup_dir.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for p in sorted(backup_dir.glob("gnom-hub-backup-*.zip"), reverse=True):
            try:
                out.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "bytes": p.stat().st_size,
                    }
                )
            except OSError:
                continue
        return out[:30]

    def backup_path(self, name: str) -> Path:
        """Safe path under data/backups for download."""
        safe = Path(name).name
        if not safe.startswith("gnom-hub-backup-") or not safe.endswith(".zip"):
            raise ValueError("invalid backup name")
        path = (self.root / "data" / "backups" / safe).resolve()
        base = (self.root / "data" / "backups").resolve()
        if not str(path).startswith(str(base)) or not path.is_file():
            raise FileNotFoundError(safe)
        return path

    def delete_backup(self, name: str) -> dict[str, Any]:
        path = self.backup_path(name)
        path.unlink()
        self._append_trace("backup.delete", {"name": path.name})
        return {"ok": True, "deleted": path.name, "backups": self.list_backups()}

    def restore_backup(
        self,
        name: str,
        *,
        archive_current: bool = True,
        load_checkpoint: bool = True,
    ) -> dict[str, Any]:
        """Extract backup zip into data/hot + data/warm and reload memory/agents."""
        import shutil
        import tempfile

        path = self.backup_path(name)
        archived = None
        if archive_current:
            sess = self.hot.session or {}
            if sess.get("messages") or sess.get("facts"):
                archived = self.archive_cold(label="pre-backup-restore").get("archive")

        data_root = (self.root / "data").resolve()
        with tempfile.TemporaryDirectory(prefix="gnom-backup-") as td:
            tdp = Path(td)
            with zipfile.ZipFile(path, "r") as zf:
                # zip-slip safe extract
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    # only hot/ and warm/ members
                    name_in = info.filename.replace(chr(92), "/").lstrip("/")
                    if ".." in name_in.split("/"):
                        continue
                    top = name_in.split("/", 1)[0]
                    if top not in ("hot", "warm"):
                        continue
                    dest = (tdp / name_in).resolve()
                    if not str(dest).startswith(str(tdp.resolve())):
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, dest.open("wb") as out:
                        shutil.copyfileobj(src, out)

            for folder in ("hot", "warm"):
                src_dir = tdp / folder
                if not src_dir.is_dir():
                    continue
                dest_dir = data_root / folder
                dest_dir.mkdir(parents=True, exist_ok=True)
                for f in src_dir.rglob("*"):
                    if not f.is_file():
                        continue
                    rel = f.relative_to(src_dir)
                    target = (dest_dir / rel).resolve()
                    if not str(target).startswith(str(dest_dir.resolve())):
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)

        self.hot.load()
        self.warm.load()
        self._load_agent_state()
        ckpt_loaded = False
        if load_checkpoint and self._checkpoint_path.is_file():
            try:
                self.load_checkpoint()
                ckpt_loaded = True
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                ckpt_loaded = False

        self._append_trace(
            "backup.restore",
            {
                "name": path.name,
                "checkpoint": ckpt_loaded,
                "archived_previous": bool(archived),
            },
        )
        snap = self.snapshot()
        snap["ok"] = True
        snap["restored_backup"] = path.name
        snap["checkpoint_loaded"] = ckpt_loaded
        if archived:
            snap["archived_previous"] = archived
        return snap
