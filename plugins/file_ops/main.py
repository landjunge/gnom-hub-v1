"""Plugin: file list/read/write with path jail under hub root."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _root() -> Path:
    try:
        from gnom_hub.config.paths import project_root

        return project_root().resolve()
    except Exception:  # noqa: BLE001
        return Path.cwd().resolve()


def _jail_bases() -> list[Path]:
    root = _root()
    return [
        root,
        (root / "data").resolve(),
        (root / "gnom_workspace").resolve(),
        (root / "plugins").resolve(),
    ]


def _resolve_in_jail(path: str, *, write: bool = False) -> tuple[Path | None, str]:
    raw = (path or "").strip()
    if not raw or ".." in Path(raw).parts:
        return None, "path empty or contains .."
    root = _root()
    p = Path(raw)
    resolved = p.resolve() if p.is_absolute() else (root / raw).resolve()
    bases = _jail_bases()
    if write:
        # writes only under data/ or gnom_workspace/
        bases = [b for b in bases if b.name in ("data", "gnom_workspace") or "data" in str(b)]
        bases = [(root / "data").resolve(), (root / "gnom_workspace").resolve()]
    for base in bases:
        try:
            resolved.relative_to(base)
            return resolved, ""
        except ValueError:
            continue
    return None, f"path outside jail: {resolved}"


def file_list(path: str = ".") -> dict[str, Any]:
    target, err = _resolve_in_jail(path or ".")
    if target is None:
        return {"ok": False, "error": err}
    if not target.exists():
        return {"ok": False, "error": f"not found: {target}"}
    if not target.is_dir():
        return {"ok": False, "error": "not a directory"}
    entries = []
    for child in sorted(target.iterdir())[:200]:
        entries.append(
            {
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            }
        )
    return {"ok": True, "path": str(target), "entries": entries, "count": len(entries)}


def file_read(path: str = "", max_chars: int = 50000) -> dict[str, Any]:
    target, err = _resolve_in_jail(path)
    if target is None:
        return {"ok": False, "error": err}
    if not target.is_file():
        return {"ok": False, "error": f"not a file: {target}"}
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    lim = max(100, min(200_000, int(max_chars or 50_000)))
    return {
        "ok": True,
        "path": str(target),
        "chars": len(text),
        "text": text[:lim],
        "truncated": len(text) > lim,
    }


def file_write(path: str = "", content: str = "") -> dict[str, Any]:
    target, err = _resolve_in_jail(path, write=True)
    if target is None:
        return {"ok": False, "error": err}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content or ""), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "path": str(target), "bytes": len(str(content or "").encode("utf-8"))}
