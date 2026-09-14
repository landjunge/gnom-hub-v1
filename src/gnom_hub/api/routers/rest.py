"""HTTP routes: rest."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from gnom_hub.api.models import (
    FlexAnswerBody,
    FlexAskBody,
    FlexFeedbackBody,
    PackExportBody,
    PackRenameBody,
    SessionPackBody,
    TelegramInBody,
    TtsPrepareBody,
)
from gnom_hub.hub import get_hub

router = APIRouter()


@router.get("/api/threaddesk")
def threaddesk_peek() -> dict[str, Any]:
    """Last ThreadDesk packet. Fills chat only — never Send/Execute."""
    from gnom_hub.threaddesk_ops import peek

    return peek()


@router.get("/api/ollama/models")
def ollama_models() -> dict[str, Any]:
    hub = get_hub()
    # Force probe so System modal reflects current Ollama process state
    ok = (
        hub.llm.ollama_available(force=True)
        if hasattr(hub.llm, "ollama_available")
        else hub.llm.has_provider("ollama")
    )
    models = hub.llm.list_ollama_models() if ok else []
    snap = hub.llm.providers_snapshot() if hasattr(hub.llm, "providers_snapshot") else {}
    return {
        "ok": bool(ok),
        "host": snap.get("ollama_host"),
        "models": models,
    }


@router.get("/api/export/last")
def export_last() -> dict[str, Any]:
    """Export last Execute (live pipeline, or pinned if reset/new chat)."""
    return get_hub().build_export_last()


@router.get("/api/state")
def state() -> dict[str, Any]:
    return get_hub().snapshot()


@router.post("/api/tts/prepare")
def tts_prepare(body: TtsPrepareBody) -> dict[str, Any]:
    """Translate agent thoughts to German before browser TTS speaks."""
    return get_hub().prepare_tts_text(body.text or "", lang=body.lang or "de")


@router.get("/api/flex/review")
def flex_review() -> dict[str, Any]:
    """Right Platzhalter panel: Flex feedback after result."""
    return get_hub().flex_review_panel()


@router.post("/api/flex/feedback")
def flex_feedback(body: FlexFeedbackBody) -> dict[str, Any]:
    """Learn from user click; rebuild asks Box 1 (Flex has no execute authority)."""
    try:
        return get_hub().apply_flex_feedback(
            body.button_id or "",
            label=body.label or "",
            note=body.note or "",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/api/flex/ask")
def flex_ask(body: FlexAskBody) -> dict[str, Any]:
    """Worker/Coordinator structured question → Flex Box 1."""
    return get_hub().flex_ask(
        agent_id=body.agent_id,
        text=body.text,
        job_id=body.job_id,
        task_id=body.task_id,
        component=body.component,
        options=body.options,
    )


@router.post("/api/flex/answer")
def flex_answer(body: FlexAnswerBody, sync: bool = Query(False)) -> dict[str, Any]:
    """User answer in Box 1. Start-work confirmation may run central execute()."""
    out = get_hub().flex_answer(
        body.question_id,
        body.value,
        job_id=body.job_id,
        sync=sync,
    )
    ans = out.get("flex_answer") if isinstance(out, dict) else None
    if isinstance(ans, dict) and ans.get("ok") is False:
        raise HTTPException(status_code=400, detail=ans.get("error") or "flex answer failed")
    return out


@router.get("/api/session/pack")
def session_pack_export(
    persist: bool = Query(True),
    label: str | None = Query(None),
) -> dict[str, Any]:
    """Downloadable portable session pack (HOT + WARM + agents + pipeline)."""
    return get_hub().export_session_pack(label=label, persist=persist)


@router.post("/api/session/pack/export")
def session_pack_export_post(body: PackExportBody) -> dict[str, Any]:
    """Export pack; optional UI chat log + result history for USB hop."""
    return get_hub().export_session_pack(
        label=body.label,
        persist=body.persist,
        include_workspace=body.include_workspace,
        ui_chat_log=body.ui_chat_log,
        ui_result_history=body.ui_result_history,
        ui_prefs=body.ui_prefs,
        notes=body.notes,
    )


@router.post("/api/session/pack")
def session_pack_import(body: SessionPackBody) -> dict[str, Any]:
    try:
        return get_hub().import_session_pack(
            body.pack,
            include_warm=body.include_warm,
            include_agents=body.include_agents,
            store=body.store,
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/api/session/packs")
def session_packs_list() -> dict[str, Any]:
    return {"packs": get_hub().list_session_packs()}


@router.get("/api/session/packs/{name}")
def session_pack_get(name: str) -> dict[str, Any]:
    try:
        return get_hub().load_session_pack_file(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/api/session/packs/{name}/download")
def session_pack_download(name: str) -> FileResponse:
    """Download a stored pack file (USB copy)."""
    try:
        path = get_hub()._pack_path(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return FileResponse(
        path,
        media_type="application/json",
        filename=path.name,
    )


@router.post("/api/session/packs/{name}/import")
def session_pack_import_named(
    name: str,
    include_warm: bool = Query(True),
    include_agents: bool = Query(True),
) -> dict[str, Any]:
    try:
        return get_hub().import_session_pack_file(
            name, include_warm=include_warm, include_agents=include_agents
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except TypeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/api/session/packs/{name}")
def session_pack_rename(name: str, body: PackRenameBody) -> dict[str, Any]:
    try:
        return get_hub().rename_session_pack(name, label=body.label, notes=body.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/api/session/packs/{name}")
def session_pack_delete(name: str) -> dict[str, Any]:
    try:
        return get_hub().delete_session_pack(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/api/telegram/start")
def telegram_start() -> dict[str, Any]:
    return get_hub().telegram_start()


@router.post("/api/telegram/stop")
def telegram_stop() -> dict[str, Any]:
    return get_hub().telegram_stop()


@router.post("/api/telegram/inbound")
def telegram_inbound(body: TelegramInBody) -> dict[str, Any]:
    """Test hook / webhook-style without Telegram servers."""
    return get_hub().telegram_inbound(body.text, body.chat_id)


@router.get("/api/docs")
def docs_catalog(limit: int = Query(200, ge=1, le=500)) -> dict[str, Any]:
    """List documentation catalog (from generated index)."""
    import json

    hub = get_hub()
    cat = hub.root / "docs" / "generated" / "docs_catalog.json"
    if cat.is_file():
        try:
            data = json.loads(cat.read_text(encoding="utf-8"))
            docs = list(data.get("docs") or [])[:limit]
            return {
                "ok": True,
                "count": len(docs),
                "version": data.get("version"),
                "docs": docs,
            }
        except Exception:  # noqa: BLE001
            pass
    # live fallback
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_docs_index",
        str(hub.root / "scripts" / "build_docs_index.py"),
    )
    if spec and spec.loader:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rows = mod.collect()[:limit]
        return {"ok": True, "count": len(rows), "docs": rows, "version": "live"}
    return {"ok": False, "count": 0, "docs": []}


@router.get("/api/docs/search")
def docs_search(
    q: str = Query("", min_length=0, max_length=200),
    limit: int = Query(12, ge=1, le=40),
) -> dict[str, Any]:
    """Local docs search engine (markdown catalog — no external service)."""
    import importlib.util

    hub = get_hub()
    script = hub.root / "scripts" / "build_docs_index.py"
    if not script.is_file():
        raise HTTPException(status_code=501, detail="docs index script missing")
    spec = importlib.util.spec_from_file_location("build_docs_index", str(script))
    if not spec or not spec.loader:
        raise HTTPException(status_code=501, detail="docs index load failed")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rows = mod.collect()
    query = (q or "").strip()
    if not query:
        return {"ok": True, "query": "", "hits": [], "count": 0}
    hits = mod.search(rows, query, limit=limit)
    return {"ok": True, "query": query, "hits": hits, "count": len(hits)}


@router.get("/api/tooltips")
def tooltips(lang: str = "en") -> dict[str, Any]:
    return get_hub().tooltips(lang)
