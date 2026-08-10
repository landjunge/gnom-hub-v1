"""Plugin: switch VectorStore embedding backend (pure Python backends)."""

from __future__ import annotations

import os
from typing import Any

from gnom_hub.plugins.sdk import fail, ok


def _vectors():
    try:
        from gnom_hub.hub import get_hub

        return getattr(get_hub(), "vectors", None)
    except Exception:  # noqa: BLE001
        return None


def on_load(info: dict[str, Any]) -> None:
    """
    Optional auto-activate via env:
      GNOM_EMBEDDINGS=char_ngram|hashing|bow
      GNOM_EMBEDDINGS_REINDEX=1
    """
    backend = (os.environ.get("GNOM_EMBEDDINGS") or "").strip().lower()
    if not backend or backend == "bow":
        return
    vs = _vectors()
    if vs is None or not hasattr(vs, "set_embedder"):
        return
    reindex = (os.environ.get("GNOM_EMBEDDINGS_REINDEX") or "").strip() in (
        "1",
        "true",
        "yes",
        "on",
    )
    try:
        vs.set_embedder(backend, reindex=reindex)
    except Exception:  # noqa: BLE001
        pass


def status() -> dict[str, Any]:
    vs = _vectors()
    if vs is None:
        return fail("vector store not available")
    if hasattr(vs, "embedder_status"):
        return ok(**vs.embedder_status())
    return ok(active="bow", docs=vs.count() if hasattr(vs, "count") else 0)


def use_backend(backend: str = "bow", reindex: bool = False) -> dict[str, Any]:
    vs = _vectors()
    if vs is None:
        return fail("vector store not available")
    if not hasattr(vs, "set_embedder"):
        return fail("vector store has no set_embedder")
    try:
        out = vs.set_embedder(str(backend or "bow"), reindex=bool(reindex))
    except ValueError as exc:
        return fail(str(exc))
    except Exception as exc:  # noqa: BLE001
        return fail(f"set_embedder failed: {exc}")
    return ok(**out)


def reindex() -> dict[str, Any]:
    vs = _vectors()
    if vs is None:
        return fail("vector store not available")
    if not hasattr(vs, "reindex"):
        return fail("vector store has no reindex")
    n = vs.reindex()
    return ok(reindexed=n, embedder=getattr(vs, "embedder_name", "bow"), docs=vs.count())
