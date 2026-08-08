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
        """
        Zip HOT + WARM + agents + checkpoint + consistent user.db into data/backups/.

        user.db is exported via SQLite online backup API (WAL-safe, H11) — not
        a raw shutil of a live WAL DB.
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = self.root / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        path = backup_dir / f"gnom-hub-backup-{stamp}.zip"
        # Ensure current state on disk
        self.hot.save()
        self.warm.save()
        self._save_agent_state()

        # Consistent personal DB snapshot (tmp file, then into zip)
        db_export: Path | None = None
        db_bytes = 0
        try:
            db = getattr(self.hot, "db", None) or getattr(self.warm, "db", None)
            if db is not None and hasattr(db, "export_consistent_copy"):
                db_export = backup_dir / f".tmp-user-{stamp}.db"
                db.export_consistent_copy(db_export)
                db_bytes = db_export.stat().st_size if db_export.is_file() else 0
        except Exception as exc:  # noqa: BLE001
            self._append_trace("backup.user_db_export_fail", {"error": str(exc)})
            db_export = None

        members = 0
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for folder in ("hot", "warm"):
                base = self.root / "data" / folder
                if not base.is_dir():
                    continue
                for f in base.rglob("*"):
                    if f.is_file():
                        # skip temp export if it ever lands under data/
                        if f.name.startswith(".tmp-user-"):
                            continue
                        zf.write(f, arcname=str(f.relative_to(self.root / "data")))
                        members += 1
            if db_export is not None and db_export.is_file():
                zf.write(db_export, arcname="user/user.db")
                members += 1
                # tiny manifest for restore tooling
                meta = {
                    "format": "gnom-hub-backup-v2",
                    "stamp": stamp,
                    "includes_user_db": True,
                    "user_db_bytes": db_bytes,
                }
                zf.writestr("meta.json", json.dumps(meta, indent=2) + "\n")
                members += 1

        if db_export is not None and db_export.is_file():
            try:
                db_export.unlink()
            except OSError:
                pass

        self._append_trace(
            "backup.create",
            {
                "path": str(path),
                "members": members,
                "user_db_bytes": db_bytes,
            },
        )
        return {
            "ok": True,
            "path": str(path),
            "bytes": path.stat().st_size,
            "user_db": bool(db_bytes),
            "user_db_bytes": db_bytes,
        }

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
        restore_user_db: bool = True,
    ) -> dict[str, Any]:
        """Extract backup zip into data/hot + data/warm (+ optional user.db) and reload."""
        import shutil
        import tempfile

        path = self.backup_path(name)
        archived = None
        if archive_current:
            sess = self.hot.session or {}
            if sess.get("messages") or sess.get("facts"):
                archived = self.archive_cold(label="pre-backup-restore").get("archive")

        data_root = (self.root / "data").resolve()
        restored_user_db = False
        with tempfile.TemporaryDirectory(prefix="gnom-backup-") as td:
            tdp = Path(td)
            with zipfile.ZipFile(path, "r") as zf:
                # zip-slip safe extract
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    name_in = info.filename.replace(chr(92), "/").lstrip("/")
                    if ".." in name_in.split("/"):
                        continue
                    top = name_in.split("/", 1)[0]
                    if top not in ("hot", "warm", "user", "meta.json") and name_in != "meta.json":
                        continue
                    if name_in == "meta.json":
                        dest = (tdp / "meta.json").resolve()
                    else:
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

            # Optional: restore personal user.db (v2 backups)
            if restore_user_db:
                src_db = tdp / "user" / "user.db"
                if src_db.is_file() and src_db.stat().st_size > 0:
                    try:
                        from gnom_hub.config.paths import user_dir
                        from gnom_hub.db import sqlite_store as store_mod

                        # Close open handles so we can replace the file
                        live = user_dir(self.root) / "user.db"
                        live.parent.mkdir(parents=True, exist_ok=True)
                        key = str(live.resolve())
                        with store_mod._lock:
                            inst = store_mod._instances.pop(key, None)
                            if inst is None:
                                for k, v in list(store_mod._instances.items()):
                                    if Path(k).resolve() == live.resolve():
                                        inst = store_mod._instances.pop(k, None)
                                        break
                            if inst is not None:
                                try:
                                    inst.close()
                                except Exception:  # noqa: BLE001
                                    pass
                        # Also drop hub refs' connections by re-pointing after copy
                        shutil.copy2(src_db, live)
                        # Remove WAL/SHM so we don't mix old WAL with new main
                        for suffix in ("-wal", "-shm"):
                            side = Path(str(live) + suffix)
                            if side.is_file():
                                try:
                                    side.unlink()
                                except OSError:
                                    pass
                        restored_user_db = True
                    except Exception as exc:  # noqa: BLE001
                        self._append_trace(
                            "backup.restore_user_db_fail",
                            {"error": str(exc)},
                        )

        # Rebind hub memory DBs after possible user.db replace
        if restored_user_db:
            try:
                from gnom_hub.db.sqlite_store import get_db

                fresh = get_db(self.root)
                self.hot.db = fresh
                self.warm.db = fresh
                if hasattr(self, "memory") and hasattr(self.memory, "hot"):
                    self.memory.hot.db = fresh
                if hasattr(self, "memory") and hasattr(self.memory, "warm"):
                    self.memory.warm.db = fresh
            except Exception:  # noqa: BLE001
                pass

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
                "user_db": restored_user_db,
            },
        )
        snap = self.snapshot()
        snap["ok"] = True
        snap["restored_backup"] = path.name
        snap["checkpoint_loaded"] = ckpt_loaded
        snap["restored_user_db"] = restored_user_db
        if archived:
            snap["archived_previous"] = archived
        return snap
