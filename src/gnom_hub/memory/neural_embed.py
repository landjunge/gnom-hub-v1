"""Optional neural embedder factories (fastembed / sentence-transformers).

Imported only when user switches backend — keeps default bow path light.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_CACHE: dict[str, Any] = {}
EmbedFn = Callable[[str], dict[str, float]]


def probe_neural() -> dict[str, bool]:
    out = {"fastembed": False, "sentence_transformers": False}
    try:
        import fastembed  # noqa: F401

        out["fastembed"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        import sentence_transformers  # noqa: F401

        out["sentence_transformers"] = True
    except Exception:  # noqa: BLE001
        pass
    return out


def make_neural_embedder(backend: str) -> tuple[str, EmbedFn]:
    """Return (name, embed_fn) or raise ValueError / ImportError."""
    b = (backend or "").strip().lower()
    available = probe_neural()
    if b in ("fastembed", "fe", "neural"):
        if not available["fastembed"]:
            raise ValueError(
                "fastembed not installed — pip install 'gnom-hub[embeddings]' or fastembed"
            )
        return "fastembed", _make_fastembed()
    if b in ("sbert", "sentence_transformers", "st", "minilm"):
        if not available["sentence_transformers"]:
            raise ValueError(
                "sentence-transformers not installed — pip install sentence-transformers"
            )
        return "sbert", _make_sbert()
    raise ValueError(f"unknown neural backend: {backend!r}")


def _make_fastembed() -> EmbedFn:
    from fastembed import TextEmbedding

    if "fe_model" not in _CACHE:
        _CACHE["fe_model"] = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    model = _CACHE["fe_model"]

    def embed(text: str) -> dict[str, float]:
        vectors = list(model.embed([text or ""]))
        if not vectors:
            return {}
        vec = vectors[0]
        return {str(i): float(v) for i, v in enumerate(vec) if abs(float(v)) > 1e-8}

    return embed


def _make_sbert() -> EmbedFn:
    from sentence_transformers import SentenceTransformer

    if "sbert_model" not in _CACHE:
        _CACHE["sbert_model"] = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    model = _CACHE["sbert_model"]

    def embed(text: str) -> dict[str, float]:
        vec = model.encode(text or "", normalize_embeddings=True)
        return {str(i): float(v) for i, v in enumerate(vec) if abs(float(v)) > 1e-8}

    return embed
