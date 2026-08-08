"""
Personal WS bootstrap — KISS.

  hub work:   gnom-hub-v1/
  your data:  WS-gnom-hub-v1/   (GNOM_WS)

    User/Key.txt
    User/user.db
    backups/user.db     ← one latest mirror
    selected/*.html     ← Copy button only
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gnom_hub.config.keys import parse_key_file
from gnom_hub.config.paths import (
    backups_dir,
    is_usb_root,
    personal_workspace,
    pin_gnom_ws_env,
    project_root,
    selected_dir,
    user_dir,
)


@dataclass
class UserWorkspaceStatus:
    hub_root: str
    personal_ws: str
    workspace_ok: bool
    user_dir: str
    user_dir_ok: bool
    key_path: str | None
    key_ok: bool
    key_has_deepseek: bool
    db_path: str
    db_ok: bool
    selected_dir: str
    selected_count: int = 0
    backup_path: str | None = None
    on_usb: bool = False
    sync_unit: str = "WS-gnom-hub-v1"
    db_created: bool = False
    key_seeded: bool = False
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ready: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_real_deepseek_key(key_path: Path | None) -> bool:
    if key_path is None or not key_path.is_file():
        return False
    try:
        keys = parse_key_file(key_path.read_text(encoding="utf-8"))
    except OSError:
        return False
    val = (keys.get("DEEPSEEK_API_KEY") or "").strip()
    if not val:
        return False
    low = val.lower()
    if low in ("sk-your-system-deepseek-key", "sk-...", "your-key", "changeme"):
        return False
    return not ("your-" in low and "key" in low)


def _ensure_key_file(ud: Path, hub: Path, actions: list[str], warnings: list[str]) -> Path | None:
    """Create User/Key.txt only if missing — from example template, never from home."""
    target = ud / "Key.txt"
    if target.is_file():
        return target
    for src in (hub / "Key.txt.example", ud / "Key.txt.example"):
        if src.is_file():
            try:
                shutil.copy2(src, target)
                actions.append("created User/Key.txt from example")
                warnings.append("edit User/Key.txt — set DEEPSEEK_API_KEY")
                return target
            except OSError as exc:
                warnings.append(f"Key.txt create failed: {exc}")
                return None
    skeleton = (
        "# Personal keys — never commit\n"
        "DEEPSEEK_MODEL=deepseek-v4-flash\n"
        "DEEPSEEK_API_KEY=\n"
        "WORKER_API_KEY=\n"
    )
    try:
        target.write_text(skeleton, encoding="utf-8")
        actions.append("created empty User/Key.txt")
        warnings.append("edit User/Key.txt — set DEEPSEEK_API_KEY")
        return target
    except OSError as exc:
        warnings.append(f"Key.txt create failed: {exc}")
        return None


def backup_user_db(root: Path | None = None) -> Path | None:
    """
    One latest mirror: backups/user.db (+ keep 3 dated).

    Prefer SQLite online backup API (WAL-safe). Falls back to shutil.copy2
    of the main file only if the DB is not open via our store.
    """
    r = Path(root) if root is not None else project_root()
    live = user_dir(r) / "user.db"
    if not live.is_file() or live.stat().st_size == 0:
        return None
    bdir = backups_dir(r)
    bdir.mkdir(parents=True, exist_ok=True)
    latest = bdir / "user.db"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stamped_path = bdir / f"user-{stamp}.db"
    try:
        # WAL-safe consistent snapshot
        import sqlite3

        from gnom_hub.db.sqlite_store import get_db

        db = get_db(r)
        db.export_consistent_copy(latest)
        shutil.copy2(latest, stamped_path)
    except (OSError, sqlite3.Error, ValueError, ImportError):
        # Fallback: copy main file (may miss uncheckpointed WAL frames)
        try:
            shutil.copy2(live, latest)
            shutil.copy2(live, stamped_path)
        except OSError:
            return None
    try:
        stamped = sorted(bdir.glob("user-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in stamped[3:]:
            try:
                old.unlink()
            except OSError:
                pass
        return latest
    except OSError:
        return latest if latest.is_file() else None


def copy_selected_html(
    source: Path | str,
    root: Path | None = None,
    *,
    name: str | None = None,
) -> Path:
    src = Path(source)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    if src.suffix.lower() not in (".html", ".htm"):
        raise ValueError("only .html / .htm")
    dest_dir = selected_dir(root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = Path(name).name if name else src.name
    if not safe.lower().endswith((".html", ".htm")):
        safe = safe + ".html"
    dest = dest_dir / safe
    if dest.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        dest = dest_dir / f"{dest.stem}-{stamp}{dest.suffix}"
    shutil.copy2(src, dest)
    return dest


def copy_selected_html_text(
    content: str,
    name: str,
    root: Path | None = None,
) -> Path:
    safe = Path(name).name
    if not safe.lower().endswith((".html", ".htm")):
        safe = f"{safe}.html"
    dest_dir = selected_dir(root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe
    if dest.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        dest = dest_dir / f"{dest.stem}-{stamp}{dest.suffix}"
    dest.write_text(content, encoding="utf-8")
    return dest


def inspect_user_workspace(root: Path | None = None) -> UserWorkspaceStatus:
    hub = Path(root) if root is not None else project_root()
    pws = personal_workspace(hub)
    ud = user_dir(hub)
    db_path = ud / "user.db"
    key_path = ud / "Key.txt" if (ud / "Key.txt").is_file() else None
    sel = selected_dir(hub)
    sel_n = 0
    if sel.is_dir():
        sel_n = sum(1 for p in sel.iterdir() if p.suffix.lower() in (".html", ".htm"))

    hub_ok = hub.is_dir()
    user_ok = ud.is_dir()
    key_ok = key_path is not None
    db_ok = db_path.is_file() and db_path.stat().st_size > 0
    has_ds = _has_real_deepseek_key(key_path)
    warnings: list[str] = []
    if not user_ok:
        warnings.append("User/ missing")
    if not key_ok:
        warnings.append("Key.txt missing")
    elif not has_ds:
        warnings.append("no real DEEPSEEK_API_KEY yet")
    if not db_ok:
        warnings.append("user.db missing")

    return UserWorkspaceStatus(
        hub_root=str(hub.resolve()) if hub_ok else str(hub),
        personal_ws=str(pws),
        workspace_ok=hub_ok and pws.is_dir(),
        user_dir=str(ud),
        user_dir_ok=user_ok,
        key_path=str(key_path) if key_path else None,
        key_ok=key_ok,
        key_has_deepseek=has_ds,
        db_path=str(db_path),
        db_ok=db_ok,
        selected_dir=str(sel),
        selected_count=sel_n,
        on_usb=is_usb_root(pws),
        sync_unit=pws.name,
        ready=hub_ok and user_ok and key_ok and db_ok,
        warnings=warnings,
    )


def ensure_user_workspace(
    root: Path | None = None,
    *,
    seed_key: bool = True,
    ensure_db: bool = True,
) -> UserWorkspaceStatus:
    """
    Create personal WS layout if missing. No legacy home/hub copies.
    """
    hub = Path(root) if root is not None else project_root()
    actions: list[str] = []
    warnings: list[str] = []

    if not hub.is_dir():
        return UserWorkspaceStatus(
            hub_root=str(hub),
            personal_ws=str(personal_workspace(hub)),
            workspace_ok=False,
            user_dir=str(user_dir(hub)),
            user_dir_ok=False,
            key_path=None,
            key_ok=False,
            key_has_deepseek=False,
            db_path=str(user_dir(hub) / "user.db"),
            db_ok=False,
            selected_dir=str(selected_dir(hub)),
            ready=False,
            warnings=["hub root missing"],
        )

    pin_gnom_ws_env(hub)
    pws = personal_workspace(hub)
    if not pws.is_dir():
        pws.mkdir(parents=True, exist_ok=True)
        actions.append(f"created {pws.name}/")

    ud = user_dir(hub)
    ud.mkdir(parents=True, exist_ok=True)
    sel = selected_dir(hub)
    sel.mkdir(parents=True, exist_ok=True)
    backups_dir(hub).mkdir(parents=True, exist_ok=True)

    key_path: Path | None = ud / "Key.txt"
    if not key_path.is_file():
        if seed_key:
            key_path = _ensure_key_file(ud, hub, actions, warnings)
        else:
            key_path = None
            warnings.append("Key.txt missing")
    key_ok = key_path is not None and key_path.is_file()
    has_ds = _has_real_deepseek_key(key_path)
    if key_ok and not has_ds:
        warnings.append("no real DEEPSEEK_API_KEY yet")

    db_path = ud / "user.db"
    db_created = False
    db_ok = False
    if ensure_db:
        try:
            from gnom_hub.db.sqlite_store import get_db

            existed = db_path.is_file() and db_path.stat().st_size > 0
            db = get_db(hub)
            db_ok = db.path.is_file()
            if not existed and db_ok:
                db_created = True
                actions.append("created user.db")
            elif db_ok:
                actions.append("user.db ok")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"user.db open failed: {exc}")
            db_ok = db_path.is_file()
    else:
        db_ok = db_path.is_file() and db_path.stat().st_size > 0

    backup = backup_user_db(hub)
    if backup:
        actions.append("backup ok")

    sel_n = (
        sum(1 for p in sel.iterdir() if p.suffix.lower() in (".html", ".htm"))
        if sel.is_dir()
        else 0
    )
    ready = hub.is_dir() and ud.is_dir() and key_ok and db_ok
    return UserWorkspaceStatus(
        hub_root=str(hub.resolve()),
        personal_ws=str(pws.resolve()),
        workspace_ok=True,
        user_dir=str(ud.resolve()),
        user_dir_ok=True,
        key_path=str(key_path.resolve()) if key_path and key_path.is_file() else None,
        key_ok=key_ok,
        key_has_deepseek=has_ds,
        db_path=str(db_path.resolve()),
        db_ok=db_ok,
        selected_dir=str(sel.resolve()),
        selected_count=sel_n,
        backup_path=str(backup) if backup else None,
        on_usb=is_usb_root(pws),
        sync_unit=pws.name,
        db_created=db_created,
        key_seeded=any("Key.txt" in a for a in actions),
        actions=actions,
        warnings=warnings,
        ready=ready,
    )


def format_user_workspace_report(status: UserWorkspaceStatus) -> str:
    where = "USB" if status.on_usb else "disk"
    lines = [
        "Personal WS (simple)",
        f"  hub:      {status.hub_root}",
        f"  yours:    {status.personal_ws}  ({where})",
        f"  Key.txt:  {'OK' if status.key_ok else 'MISSING'}"
        + (f"  deepseek={'yes' if status.key_has_deepseek else 'no'}" if status.key_ok else ""),
        f"  user.db:  {'OK' if status.db_ok else 'MISSING'}",
        f"  selected: {status.selected_count} HTML",
        f"  backup:   {status.backup_path or '—'}",
    ]
    for a in status.actions:
        lines.append(f"  + {a}")
    for w in status.warnings:
        lines.append(f"  ! {w}")
    lines.append(f"  ready:    {'yes' if status.ready else 'no'}")
    return "\n".join(lines)
