"""
Personal workspace bootstrap (sibling of the hub).

  /Users/…/gnom-hub-v1          ← CODE — work happens here
  /Users/…/WS-gnom-hub-v1       ← YOURS — Key, user.db, selected HTML only
      User/Key.txt
      User/user.db              ← live DB (always updated here)
      backups/user.db           ← latest mirror / backup
      selected/*.html           ← only pages you explicitly copy

Nothing auto-dumps worker output into selected/ — only deliberate copy.
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gnom_hub.config.keys import parse_key_file, resolve_key_txt_path
from gnom_hub.config.paths import (
    backups_dir,
    is_real_hub_root,
    is_usb_root,
    personal_workspace,
    project_root,
    selected_dir,
    user_dir,
)


def _find_key_path(base: Path) -> Path | None:
    preferred = user_dir(base) / "Key.txt"
    if preferred.is_file():
        return preferred
    if (base / "Key.txt").is_file():
        return base / "Key.txt"
    if (base / "User" / "Key.txt").is_file():
        return base / "User" / "Key.txt"
    # real hub only: inspect legacy hub User/
    if is_real_hub_root(base):
        hub_user = project_root() / "User" / "Key.txt"
        if hub_user.is_file():
            return hub_user
    return None


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


def _seed_key_txt(ud: Path, hub: Path, actions: list[str], warnings: list[str]) -> Path | None:
    target = ud / "Key.txt"
    if target.is_file():
        return target

    candidates = [
        hub / "User" / "Key.txt",
        hub / "Key.txt",
        ud / "Key.txt.example",
        hub / "Key.txt.example",
    ]
    # real hub: also allow seeding from code-tree User/ (sibling WS empty)
    if is_real_hub_root(hub):
        candidates = [
            project_root() / "User" / "Key.txt",
            project_root() / "Key.txt",
            *candidates,
            project_root() / "Key.txt.example",
        ]
    for src in candidates:
        if src.is_file():
            try:
                shutil.copy2(src, target)
                actions.append(f"seeded Key.txt from {src}")
                if "example" in src.name.lower() or not _has_real_deepseek_key(target):
                    warnings.append("User/Key.txt — set DEEPSEEK_API_KEY if needed")
                return target
            except OSError as exc:
                warnings.append(f"could not seed Key.txt: {exc}")
                break

    skeleton = (
        "# Gnom-Hub personal keys — never commit\n"
        "DEEPSEEK_MODEL=deepseek-v4-flash\n"
        "DEEPSEEK_API_KEY=\n"
        "WORKER_API_KEY=\n"
    )
    try:
        target.write_text(skeleton, encoding="utf-8")
        actions.append("created empty User/Key.txt")
        warnings.append("User/Key.txt empty — add DEEPSEEK_API_KEY=sk-...")
        return target
    except OSError as exc:
        warnings.append(f"could not create Key.txt: {exc}")
        return None


def _seed_db_from_hub(target: Path, hub: Path, actions: list[str]) -> None:
    """One-shot: hub User/user.db or home → personal User/user.db if missing."""
    if target.exists() and target.stat().st_size > 0:
        return
    candidates = [
        hub / "User" / "user.db",
        Path.home() / ".local" / "share" / "gnom-hub" / "user.db",
    ]
    for src in candidates:
        if src.is_file() and src.stat().st_size > 0:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
                actions.append(f"seeded user.db from {src}")
                return
            except OSError:
                continue


def backup_user_db(root: Path | None = None) -> Path | None:
    """
    Mirror live User/user.db → personal_ws/backups/user.db (always latest).
    Also writes a dated copy (keeps last few via overwrite of latest only + one stamp).
    """
    r = Path(root) if root is not None else project_root()
    live = user_dir(r) / "user.db"
    if not live.is_file() or live.stat().st_size == 0:
        return None
    bdir = backups_dir(r)
    bdir.mkdir(parents=True, exist_ok=True)
    latest = bdir / "user.db"
    try:
        # Safe copy even if SQLite has WAL: copy main file after checkpoint best-effort
        shutil.copy2(live, latest)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(live, bdir / f"user-{stamp}.db")
        # prune old stamped backups, keep 5 newest
        stamped = sorted(bdir.glob("user-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in stamped[5:]:
            try:
                old.unlink()
            except OSError:
                pass
        return latest
    except OSError:
        return None


def copy_selected_html(
    source: Path | str,
    root: Path | None = None,
    *,
    name: str | None = None,
) -> Path:
    """
    Copy ONE chosen HTML file into personal_ws/selected/.
    Only deliberate copies — never bulk dump from hub temp.
    """
    src = Path(source)
    if not src.is_file():
        raise FileNotFoundError(str(src))
    if src.suffix.lower() not in (".html", ".htm"):
        raise ValueError("only .html / .htm can go into selected/")
    dest_dir = selected_dir(root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = Path(name).name if name else src.name
    if not safe.lower().endswith((".html", ".htm")):
        safe = safe + ".html"
    dest = dest_dir / safe
    # avoid overwrite: add stamp if exists
    if dest.exists():
        stem = dest.stem
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        dest = dest_dir / f"{stem}-{stamp}{dest.suffix}"
    shutil.copy2(src, dest)
    return dest


def copy_selected_html_text(
    content: str,
    name: str,
    root: Path | None = None,
) -> Path:
    """Write selected HTML body into personal_ws/selected/ (user-chosen only)."""
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
    key_path = _find_key_path(hub)
    sel = selected_dir(hub)
    sel_n = 0
    if sel.is_dir():
        sel_n = sum(
            1 for p in sel.iterdir() if p.is_file() and p.suffix.lower() in (".html", ".htm")
        )

    hub_ok = hub.is_dir()
    user_ok = ud.is_dir()
    key_ok = key_path is not None and key_path.is_file()
    db_ok = db_path.is_file() and db_path.stat().st_size > 0
    has_ds = _has_real_deepseek_key(key_path)

    warnings: list[str] = []
    if not hub_ok:
        warnings.append("hub root missing")
    if not pws.is_dir():
        warnings.append("personal WS missing")
    if not user_ok:
        warnings.append("User/ folder missing")
    if not key_ok:
        warnings.append("User/Key.txt missing")
    elif not has_ds:
        warnings.append("User/Key.txt has no real DEEPSEEK_API_KEY yet")
    if not db_ok:
        warnings.append("User/user.db missing")

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
    Ensure personal WS exists next to hub (or under tmp root in tests).
    Live Key + DB under WS/User/. Backup latest user.db. selected/ empty until you copy.
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
            warnings=["hub root missing — cannot bootstrap personal WS"],
        )

    pws = personal_workspace(hub)
    if not pws.is_dir():
        pws.mkdir(parents=True, exist_ok=True)
        actions.append(f"created personal WS {pws}")

    ud = user_dir(hub)
    if not ud.is_dir():
        ud.mkdir(parents=True, exist_ok=True)
        actions.append("created User/")

    sel = selected_dir(hub)
    if not sel.is_dir():
        sel.mkdir(parents=True, exist_ok=True)
        actions.append("created selected/ (only chosen HTML)")

    bdir = backups_dir(hub)
    bdir.mkdir(parents=True, exist_ok=True)

    # Prefer WS key; seed from hub User/Key if needed
    resolve_key_txt_path(hub)

    key_path: Path | None = ud / "Key.txt"
    if not key_path.is_file():
        if seed_key:
            key_path = _seed_key_txt(ud, hub, actions, warnings)
        else:
            key_path = None
            warnings.append("User/Key.txt missing")

    key_ok = key_path is not None and key_path.is_file()
    has_ds = _has_real_deepseek_key(key_path)
    if key_ok and not has_ds:
        warnings.append("User/Key.txt has no real DEEPSEEK_API_KEY yet")

    db_path = ud / "user.db"
    if is_real_hub_root(hub):
        _seed_db_from_hub(db_path, hub, actions)

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
                actions.append("created User/user.db")
            elif db_ok:
                actions.append("User/user.db ready (live in personal WS)")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"user.db open failed: {exc}")
            db_ok = db_path.is_file()
    else:
        db_ok = db_path.is_file() and db_path.stat().st_size > 0

    backup = backup_user_db(hub)
    if backup:
        actions.append(f"backup → {backup}")

    sel_n = (
        sum(1 for p in sel.iterdir() if p.is_file() and p.suffix.lower() in (".html", ".htm"))
        if sel.is_dir()
        else 0
    )

    ready = hub.is_dir() and ud.is_dir() and key_ok and db_ok
    return UserWorkspaceStatus(
        hub_root=str(hub.resolve()),
        personal_ws=str(pws.resolve()),
        workspace_ok=True,
        user_dir=str(ud.resolve()),
        user_dir_ok=ud.is_dir(),
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
        key_seeded=any("Key.txt" in a and ("seeded" in a or "created empty" in a) for a in actions),
        actions=actions,
        warnings=warnings,
        ready=ready,
    )


def format_user_workspace_report(status: UserWorkspaceStatus) -> str:
    where = "USB" if status.on_usb else "local disk"
    lines = [
        "Hub vs personal WS",
        f"  hub (work):  {status.hub_root}",
        f"  personal:    {'OK' if status.workspace_ok else 'MISSING'}  {status.personal_ws}  ({where})",
        f"  User/Key:    {'OK' if status.key_ok else 'MISSING'}"
        + (f"  deepseek={'yes' if status.key_has_deepseek else 'no'}" if status.key_ok else ""),
        f"  User/DB:     {'OK' if status.db_ok else 'MISSING'}  {status.db_path}",
        f"  selected/:   {status.selected_count} HTML (only what you copy)",
        f"  backup:      {status.backup_path or '(none yet)'}",
    ]
    if status.actions:
        for a in status.actions:
            lines.append(f"  + {a}")
    if status.warnings:
        for w in status.warnings:
            lines.append(f"  ! {w}")
    lines.append(f"  ready:       {'yes' if status.ready else 'no'}")
    return "\n".join(lines)
