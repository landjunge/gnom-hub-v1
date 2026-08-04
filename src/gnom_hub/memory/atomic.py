"""Atomic file writes (tmp + replace)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path | str, content: str, encoding: str = "utf-8") -> None:
    """Write text atomically: same-dir temp file, fsync, then os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
