"""Context offload by node_id (long text → data/offload/{node_id}.txt)."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.memory.atomic import atomic_write_text

DEFAULT_THRESHOLD = 2000


def offload(
    text: str,
    node_id: str,
    offload_dir: Path | str,
    threshold: int = DEFAULT_THRESHOLD,
) -> str:
    """If text exceeds threshold, write full body and return a short stub; else return text."""
    if len(text) <= threshold:
        return text
    offload_dir = Path(offload_dir)
    offload_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(offload_dir / f"{node_id}.txt", text)
    return f"[offload:{node_id}]"


def recall(node_id: str, offload_dir: Path | str) -> str:
    """Read full text for a previously offloaded node_id."""
    path = Path(offload_dir) / f"{node_id}.txt"
    return path.read_text(encoding="utf-8")


def is_offload_stub(text: str) -> bool:
    return text.startswith("[offload:") and text.endswith("]")


def stub_node_id(text: str) -> str | None:
    if not is_offload_stub(text):
        return None
    return text[len("[offload:") : -1]
