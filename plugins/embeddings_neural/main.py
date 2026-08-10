"""Optional neural embeddings — only if extra packages installed."""

from __future__ import annotations

from typing import Any

from gnom_hub.plugins.sdk import fail, ok

_CACHE: dict[str, Any] = {}


def _probe() -> dict[str, bool]:
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


def _vectors():
    try:
        from gnom_hub.hub import get_hub

        return getattr(get_hub(), "vectors", None)
    except Exception:  # noqa: BLE001
        return None


def _make_sbert_fn():
    from sentence_transformers import SentenceTransformer

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    if "sbert_model" not in _CACHE:
        _CACHE["sbert_model"] = SentenceTransformer(model_name)

    model = _CACHE["sbert_model"]

    def embed(text: str) -> dict[str, float]:
        vec = model.encode(text or "", normalize_embeddings=True)
        # sparse dict for JSON store compatibility
        return {str(i): float(v) for i, v in enumerate(vec) if abs(float(v)) > 1e-8}

    return embed


def _make_fastembed_fn():
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


def status() -> dict[str, Any]:
    probe = _probe()
    vs = _vectors()
    active = getattr(vs, "embedder_name", "bow") if vs else "n/a"
    return ok(
        available=probe,
        active=active,
        install_hint="pip install fastembed  OR  pip install sentence-transformers",
    )


def use_neural(backend: str = "fastembed", reindex: bool = False) -> dict[str, Any]:
    vs = _vectors()
    if vs is None or not hasattr(vs, "set_embedder"):
        return fail("vector store not available")
    b = (backend or "fastembed").strip().lower()
    probe = _probe()
    try:
        if b in ("fastembed", "fe") and probe["fastembed"]:
            fn = _make_fastembed_fn()
            name = "fastembed"
        elif b in ("sbert", "sentence_transformers", "st") and probe["sentence_transformers"]:
            fn = _make_sbert_fn()
            name = "sbert"
        else:
            return fail(
                f"backend {b!r} not importable. Available: {probe}. Install optional package first."
            )
        out = vs.set_embedder(name, fn=fn, reindex=bool(reindex))
        return ok(**out, available=probe)
    except Exception as exc:  # noqa: BLE001
        return fail(f"neural embedder failed: {exc}")
