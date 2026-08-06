"""
New-install bootstrap for the personal User/ unit.

User/ is the portable personal unit next to the code:
  {workspace}/User/Key.txt   — keys (you update)
  {workspace}/User/user.db   — memory (hub updates; you sync the folder)

If the workspace is on a USB stick, User/ is created and kept there.
Home (~/.local/…) is never the live store — only a one-shot legacy seed.

On install / hub start:
  1. Check workspace (project root) is present
  2. Ensure User/ exists (on that volume: disk / USB)
  3. Ensure Key.txt is inside User/ (seed from example if missing)
  4. Ensure user.db is inside User/ (create empty schema if missing)
"""

from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gnom_hub.config.keys import parse_key_file, resolve_key_txt_path
from gnom_hub.config.paths import is_usb_root, project_root, user_dir


def _find_key_path(base: Path) -> Path | None:
    """Locate Key.txt without side effects (no copy)."""
    preferred = user_dir(base) / "Key.txt"
    if preferred.is_file():
        return preferred
    legacy = base / "Key.txt"
    if legacy.is_file():
        return legacy
    return None


@dataclass
class UserWorkspaceStatus:
    """Result of inspecting / ensuring the personal User/ folder."""

    root: str
    workspace_ok: bool
    user_dir: str
    user_dir_ok: bool
    key_path: str | None
    key_ok: bool
    key_has_deepseek: bool
    db_path: str
    db_ok: bool
    on_usb: bool = False
    sync_unit: str = "User/"  # portable unit to update/sync (not home)
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
    # placeholder values from example template
    low = val.lower()
    if low in ("sk-your-system-deepseek-key", "sk-...", "your-key", "changeme"):
        return False
    return not ("your-" in low and "key" in low)


def _seed_key_txt(ud: Path, root: Path, actions: list[str], warnings: list[str]) -> Path | None:
    """Create User/Key.txt from example or empty template if missing."""
    target = ud / "Key.txt"
    if target.is_file():
        return target

    # Prefer User/Key.txt.example, then root Key.txt.example, then empty skeleton
    candidates = [
        ud / "Key.txt.example",
        root / "Key.txt.example",
        root / "User" / "Key.txt.example",
    ]
    for src in candidates:
        if src.is_file():
            try:
                shutil.copy2(src, target)
                actions.append(f"seeded Key.txt from {src.name}")
                warnings.append("User/Key.txt created from example — set DEEPSEEK_API_KEY")
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


def inspect_user_workspace(root: Path | None = None) -> UserWorkspaceStatus:
    """Read-only check: workspace + User/ + Key.txt + user.db (no seeding)."""
    base = Path(root) if root is not None else project_root()
    ud = user_dir(base)
    db_path = ud / "user.db"
    key_path = _find_key_path(base)

    workspace_ok = base.is_dir()
    user_ok = ud.is_dir()
    key_ok = key_path is not None and key_path.is_file()
    db_ok = db_path.is_file() and db_path.stat().st_size > 0
    has_ds = _has_real_deepseek_key(key_path)

    warnings: list[str] = []
    if not workspace_ok:
        warnings.append("workspace root missing")
    if not user_ok:
        warnings.append("User/ folder missing")
    if not key_ok:
        warnings.append("User/Key.txt missing")
    elif not has_ds:
        warnings.append("User/Key.txt has no real DEEPSEEK_API_KEY yet")
    if not db_ok:
        warnings.append("User/user.db missing (will be created on first open)")

    ready = workspace_ok and user_ok and key_ok and db_ok
    return UserWorkspaceStatus(
        root=str(base.resolve()),
        workspace_ok=workspace_ok,
        user_dir=str(ud),
        user_dir_ok=user_ok,
        key_path=str(key_path) if key_path else None,
        key_ok=key_ok,
        key_has_deepseek=has_ds,
        db_path=str(db_path),
        db_ok=db_ok,
        on_usb=is_usb_root(base),
        sync_unit="User/",
        ready=ready,
        warnings=warnings,
    )


def ensure_user_workspace(
    root: Path | None = None,
    *,
    seed_key: bool = True,
    ensure_db: bool = True,
) -> UserWorkspaceStatus:
    """
    New-install / start bootstrap.

    - Ensures project root is a directory
    - Creates User/ if missing
    - Seeds User/Key.txt from example when missing (if seed_key)
    - Creates User/user.db schema when missing (if ensure_db)
    """
    base = Path(root) if root is not None else project_root()
    actions: list[str] = []
    warnings: list[str] = []

    workspace_ok = base.is_dir()
    if not workspace_ok:
        return UserWorkspaceStatus(
            root=str(base),
            workspace_ok=False,
            user_dir=str(user_dir(base)),
            user_dir_ok=False,
            key_path=None,
            key_ok=False,
            key_has_deepseek=False,
            db_path=str(user_dir(base) / "user.db"),
            db_ok=False,
            on_usb=False,
            ready=False,
            warnings=["workspace root missing — cannot bootstrap User/"],
        )

    ud = user_dir(base)
    if not ud.is_dir():
        ud.mkdir(parents=True, exist_ok=True)
        actions.append("created User/")

    # Migrate root Key.txt → User/ if needed
    resolve_key_txt_path(base)

    key_path: Path | None = ud / "Key.txt"
    if not key_path.is_file():
        if seed_key:
            key_path = _seed_key_txt(ud, base, actions, warnings)
        else:
            key_path = None
            warnings.append("User/Key.txt missing")
    else:
        key_path = ud / "Key.txt"

    key_ok = key_path is not None and key_path.is_file()
    has_ds = _has_real_deepseek_key(key_path)
    if key_ok and not has_ds and "DEEPSEEK_API_KEY" not in " ".join(warnings):
        warnings.append("User/Key.txt has no real DEEPSEEK_API_KEY yet")

    db_path = ud / "user.db"
    db_created = False
    db_ok = False
    if ensure_db:
        try:
            from gnom_hub.db.sqlite_store import get_db

            existed = db_path.is_file() and db_path.stat().st_size > 0
            db = get_db(base)
            db_ok = db.path.is_file()
            if not existed and db_ok:
                db_created = True
                actions.append("created User/user.db")
            elif db_ok:
                actions.append("User/user.db ready")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"user.db open failed: {exc}")
            db_ok = db_path.is_file()
    else:
        db_ok = db_path.is_file() and db_path.stat().st_size > 0

    ready = workspace_ok and ud.is_dir() and key_ok and db_ok
    return UserWorkspaceStatus(
        root=str(base.resolve()),
        workspace_ok=workspace_ok,
        user_dir=str(ud.resolve()),
        user_dir_ok=ud.is_dir(),
        key_path=str(key_path.resolve()) if key_path and key_path.is_file() else None,
        key_ok=key_ok,
        key_has_deepseek=has_ds,
        db_path=str(db_path.resolve()),
        db_ok=db_ok,
        on_usb=is_usb_root(base),
        sync_unit="User/",
        db_created=db_created,
        key_seeded=any("Key.txt" in a and ("seeded" in a or "created empty" in a) for a in actions),
        actions=actions,
        warnings=warnings,
        ready=ready,
    )


def format_user_workspace_report(status: UserWorkspaceStatus) -> str:
    """Human-readable install/start report."""
    where = "USB mount" if status.on_usb else "local disk"
    lines = [
        "User/ unit (portable — update & sync this folder)",
        f"  workspace: {'OK' if status.workspace_ok else 'MISSING'}  {status.root}  ({where})",
        f"  User/:     {'OK' if status.user_dir_ok else 'MISSING'}  {status.user_dir}",
        f"  Key.txt:   {'OK' if status.key_ok else 'MISSING'}"
        + (f"  (deepseek={'yes' if status.key_has_deepseek else 'no'})" if status.key_ok else ""),
        f"  user.db:   {'OK' if status.db_ok else 'MISSING'}  {status.db_path}",
        "  live store: User/user.db only (not ~/.local)",
        "  sync:      copy/update whole User/ with the workspace (USB ok)",
    ]
    if status.actions:
        for a in status.actions:
            lines.append(f"  + {a}")
    if status.warnings:
        for w in status.warnings:
            lines.append(f"  ! {w}")
    lines.append(f"  ready:     {'yes' if status.ready else 'no'}")
    return "\n".join(lines)
