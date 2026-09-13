"""HTTP routes: memory."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from gnom_hub.api.models import (
    ColdLabelBody,
    HotFactBody,
    VectorAddBody,
    VectorEmbedderBody,
    VectorSearchBody,
    WarmFactBody,
)
from gnom_hub.hub import get_hub

router = APIRouter()


@router.get("/api/canvas")
def canvas() -> dict[str, Any]:
    return get_hub().canvas()


@router.get("/api/memory")
def memory() -> dict[str, Any]:
    return get_hub().memory_dict()


@router.post("/api/memory/hot")
def hot_add(body: HotFactBody) -> dict[str, Any]:
    return get_hub().add_hot_fact(body.text.strip())


@router.delete("/api/memory/hot")
def hot_delete(
    text: str | None = Query(None),
    index: int | None = Query(None),
) -> dict[str, Any]:
    try:
        return get_hub().delete_hot_fact(text=text, index=index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/api/memory/hot/clear")
def hot_clear() -> dict[str, Any]:
    return get_hub().clear_hot_facts()


@router.post("/api/memory/hot/promote")
def hot_promote(body: HotFactBody) -> dict[str, Any]:
    try:
        return get_hub().promote_hot_fact(body.text.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/api/memory/warm")
def warm_add(body: WarmFactBody) -> dict[str, Any]:
    hub = get_hub()
    text = body.text.strip()
    ok = hub.warm.add_fact(text)
    if ok and hasattr(hub, "index_durable_fact"):
        hub.index_durable_fact(text, source="warm_api")
    return {"ok": ok, "warm_facts": get_hub().warm.all_facts()[-12:]}


@router.delete("/api/memory/warm")
def warm_delete(
    text: str | None = Query(None),
    index: int | None = Query(None),
) -> dict[str, Any]:
    """Delete WARM fact by exact text or 1-based index."""
    hub = get_hub()
    if index is not None:
        removed = hub.warm.remove_at(int(index))
        if removed is None:
            raise HTTPException(status_code=404, detail="index out of range")
        return {
            "ok": True,
            "removed": removed,
            "warm_facts": hub.warm.all_facts()[-12:],
        }
    if text and text.strip():
        ok = hub.warm.remove_fact(text.strip())
        if not ok:
            raise HTTPException(status_code=404, detail="fact not found")
        return {"ok": True, "removed": text.strip(), "warm_facts": hub.warm.all_facts()[-12:]}
    raise HTTPException(status_code=400, detail="text or index required")


@router.post("/api/memory/warm/clear")
def warm_clear() -> dict[str, Any]:
    """Clear WARM facts; Flex wishes (source=flex) kept by default (M9)."""
    hub = get_hub()
    before = len(hub.warm.all_facts())
    removed = hub.warm.clear(keep_flex=True)
    remaining = hub.warm.all_facts()
    return {
        "ok": True,
        "cleared": removed,
        "before": before,
        "kept_flex": len(remaining),
        "keep_flex": True,
        "warm_facts": remaining[-12:],
    }


@router.post("/api/cold/archive")
def cold_archive(body: ColdLabelBody | None = None) -> dict[str, Any]:
    label = body.label if body else ""
    return get_hub().archive_cold(label=label or "")


@router.get("/api/cold")
def cold_list() -> dict[str, Any]:
    return {"archives": get_hub().cold.list_archives()}


@router.get("/api/cold/{archive_id}")
def cold_get(archive_id: str) -> dict[str, Any]:
    data = get_hub().cold.get(archive_id)
    if not data:
        raise HTTPException(status_code=404, detail="archive not found")
    return data


@router.post("/api/cold/{archive_id}/restore")
def cold_restore(
    archive_id: str,
    archive_current: bool = Query(True),
) -> dict[str, Any]:
    """Restore COLD archive into HOT session."""
    try:
        return get_hub().restore_cold(archive_id, archive_current=archive_current)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/api/cold/{archive_id}")
def cold_delete(archive_id: str) -> dict[str, Any]:
    try:
        return get_hub().delete_cold(archive_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/api/vector")
def vector_list(limit: int = Query(40, ge=1, le=200)) -> dict[str, Any]:
    hub = get_hub()
    emb = (
        hub.vectors.embedder_status()
        if hasattr(hub.vectors, "embedder_status")
        else {"active": getattr(hub.vectors, "embedder_name", "bow")}
    )
    if isinstance(emb, dict):
        try:
            from gnom_hub.memory.neural_embed import probe_neural

            emb = {**emb, "neural_available": probe_neural()}
        except Exception:  # noqa: BLE001
            pass
    return {
        "count": hub.vectors.count(),
        "docs": hub.vectors.list_docs(limit),
        "embedder": emb,
    }


@router.post("/api/vector/embedder/install")
def vector_embedder_install() -> dict[str, Any]:
    """One-shot: pip install fastembed into the running env."""
    try:
        # prefer plugin handler if loaded
        hub = get_hub()
        if hasattr(hub.tools, "call"):
            try:
                out = hub.tools.call("embeddings_neural_install", {})
                if isinstance(out, dict):
                    return out
            except Exception:  # noqa: BLE001
                pass
        import subprocess
        import sys

        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "fastembed>=0.4.0"],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if r.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=(r.stderr or r.stdout or "pip failed")[-500:],
            )
        from gnom_hub.memory.neural_embed import probe_neural

        return {"ok": True, "available": probe_neural(), "next": "select fastembed + Apply"}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/vector/embedder")
def vector_embedder(body: VectorEmbedderBody) -> dict[str, Any]:
    """Switch embedder: bow | char_ngram | hashing | fastembed | sbert."""
    hub = get_hub()
    if not hasattr(hub.vectors, "set_embedder"):
        raise HTTPException(status_code=501, detail="embedder switch not supported")
    backend = (body.backend or "bow").strip().lower()
    try:
        if backend in (
            "fastembed",
            "fe",
            "neural",
            "sbert",
            "sentence_transformers",
            "st",
            "minilm",
        ):
            from gnom_hub.memory.neural_embed import make_neural_embedder

            name, fn = make_neural_embedder(backend)
            out = hub.vectors.set_embedder(name, fn=fn, reindex=bool(body.reindex))
            # persist
            pref = hub.root / "data" / "hot" / "vector_embedder.json"
            pref.parent.mkdir(parents=True, exist_ok=True)
            import json

            pref.write_text(json.dumps({"embedder": name}, indent=2) + chr(10), encoding="utf-8")
        else:
            out = hub.vectors.set_embedder(backend, reindex=bool(body.reindex))
            pref = hub.root / "data" / "hot" / "vector_embedder.json"
            pref.parent.mkdir(parents=True, exist_ok=True)
            import json

            pref.write_text(json.dumps({"embedder": backend}, indent=2) + chr(10), encoding="utf-8")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    emb = (
        hub.vectors.embedder_status()
        if hasattr(hub.vectors, "embedder_status")
        else {"active": backend}
    )
    try:
        from gnom_hub.memory.neural_embed import probe_neural

        emb = {**emb, "neural_available": probe_neural()}
    except Exception:  # noqa: BLE001
        pass
    return {
        **(out if isinstance(out, dict) else {"ok": True}),
        "embedder": emb,
        "count": hub.vectors.count(),
    }


@router.post("/api/vector/add")
def vector_add(body: VectorAddBody) -> dict[str, Any]:
    doc_id = get_hub().vectors.add(body.text, meta=body.meta)
    return {
        "ok": True,
        "id": doc_id,
        "count": get_hub().vectors.count(),
        "docs": get_hub().vectors.list_docs(20),
    }


@router.post("/api/vector/search")
def vector_search(body: VectorSearchBody) -> dict[str, Any]:
    hub = get_hub()
    hits = hub.vectors.search(body.query, limit=body.limit)
    emb = getattr(hub.vectors, "embedder_name", "bow")
    return {"hits": hits, "count": hub.vectors.count(), "embedder": emb}


@router.delete("/api/vector/{doc_id}")
def vector_delete(doc_id: str) -> dict[str, Any]:
    ok = get_hub().vectors.delete(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="doc not found")
    return {
        "ok": True,
        "deleted": doc_id,
        "count": get_hub().vectors.count(),
        "docs": get_hub().vectors.list_docs(20),
    }


@router.post("/api/vector/clear")
def vector_clear() -> dict[str, Any]:
    n = get_hub().vectors.count()
    get_hub().vectors.clear()
    return {"ok": True, "cleared": n, "count": 0, "docs": []}
