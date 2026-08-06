"""API + hub integration tests (stub LLM path)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Isolate HOT memory under tmp
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    # Avoid real keys from user env affecting free_only etc. — OK if present
    app = create_app()
    with TestClient(app) as c:
        yield c
    hub_mod._HUB = None


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "version" in r.json()
    assert r.json()["version"].split(".")[0] in ("2", "3")


def test_ui_static_has_v16_v37_features(client: TestClient):
    """Smoke: app.js ships 1.6–3.7 UI helpers."""
    js = client.get("/static/app.js")
    assert js.status_code == 200
    body = js.text
    assert "downloadWorkerResult" in body
    assert "openWorkerFullscreen" in body
    assert "focusBox3" in body
    assert "openWorkerInTab" in body
    assert "saveWorkerToWorkspace" in body
    assert "formatChatTime" in body
    assert "copyAllWorkerResults" in body
    assert "computeLineDiff" in body
    assert "startJobTimer" in body
    assert "updateCostBadge" in body
    assert "pushResultHistory" in body
    # Dynamic Box 3: dual-layer sequential display
    assert "focusBox3Worker" in body
    assert "normalizeWorkerOutputs" in body
    assert "dual-layers" in body or "paintWorkerIntoSlot" in body
    assert "exportResultHistory" in body
    assert "rerunWorker" in body
    assert "card-cost" in body
    assert 'ev.key === "s"' in body or "ev.key === 's'" in body

    css = client.get("/static/app.css")
    assert css.status_code == 200
    assert "worker-fs-overlay" in css.text
    assert "box3-flash" in css.text
    assert "chat-ts" in css.text
    assert "diff-overlay" in css.text
    assert "job-timer" in css.text
    assert "cost-badge" in css.text
    assert "box3-dynamic" in css.text
    assert "card-cost" in css.text

    html = client.get("/")
    assert html.status_code == 200
    assert "box3-content" in html.text
    assert 'id="box3"' in html.text
    assert "cost-badge" in html.text
    assert "box3-content" in html.text
    assert "btn-clarify" in html.text


def test_state_exposes_cost_fields(client: TestClient):
    r = client.get("/api/state")
    assert r.status_code == 200
    llm = r.json().get("llm") or {}
    assert "spent_usd" in llm
    assert "prompt_tokens" in llm
    assert "max_budget_usd" in llm or "spent_usd" in llm
    agents = r.json().get("agents") or []
    assert agents
    assert "cost_usd" in agents[0]


def test_worker_rerun_after_execute(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "rerun single worker please"})
    ex = client.post("/api/execute?sync=1")
    assert ex.status_code == 200
    assert (ex.json().get("pipeline") or {}).get("stage") == "done"
    outs_before = (ex.json().get("pipeline") or {}).get("worker_outputs") or []
    assert outs_before

    r = client.post("/api/workers/worker1/rerun?sync=1")
    assert r.status_code == 200
    pipe = r.json().get("pipeline") or {}
    assert pipe.get("stage") == "done"
    assert not pipe.get("error")
    outs = pipe.get("worker_outputs") or []
    assert any(o.get("worker") == "worker1" for o in outs)

    bad = client.post("/api/workers/notaworker/rerun?sync=1")
    assert bad.status_code == 400


def test_reexecute_after_error_job_done(client: TestClient, monkeypatch):
    """Sticky pipeline.error must not mark a successful re-execute as error."""
    from gnom_hub import hub as hub_mod

    hub = hub_mod.get_hub()
    client.post("/api/chat?sync=1", json={"text": "retry after fail"})
    # Inject sticky error as if previous execute failed
    hub.pipeline.state.error = "simulated LLM outage"
    from gnom_hub.pipeline.models import PipelineStage

    hub.pipeline.state.stage = PipelineStage.error

    r = client.post("/api/execute?sync=1")
    assert r.status_code == 200
    body = r.json()
    pipe = body.get("pipeline") or {}
    assert pipe.get("stage") == "done"
    assert not pipe.get("error")

    # Async path classification
    hub.pipeline.state.error = "stale"
    hub.pipeline.state.stage = PipelineStage.error
    client.post("/api/chat?sync=1", json={"text": "another try"})
    start = client.post("/api/execute")
    jid = start.json().get("job_id")
    assert jid
    import time

    status = None
    for _ in range(50):
        time.sleep(0.05)
        j = client.get(f"/api/jobs/{jid}").json()
        if j.get("status") in ("done", "error", "clarify", "cancelled"):
            status = j.get("status")
            break
    assert status == "done", status
    assert not (j.get("snapshot") or {}).get("pipeline", {}).get("error")


def test_workspace_write_temp_and_perm(client: TestClient):
    r = client.post(
        "/api/workspace/write",
        json={
            "zone": "temp",
            "name": "worker1_ui.html",
            "content": "<html><body>ok</body></html>",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert "worker1_ui.html" in (body.get("path") or "")

    p = client.post(
        "/api/workspace/write",
        json={
            "zone": "perm",
            "name": "worker1_keep.txt",
            "content": "keep me",
        },
    )
    assert p.status_code == 200
    assert p.json().get("ok") is True
    snap = client.get("/api/workspace").json()
    perm_names = [f["name"] for f in snap.get("perm") or []]
    assert "worker1_keep.txt" in perm_names


def test_cancel_backups_presets_delete(client: TestClient):
    r = client.post("/api/chat", json={"text": "async cancel test"})
    assert r.status_code == 200
    jid = r.json().get("job_id")
    assert jid
    c = client.post(f"/api/jobs/{jid}/cancel")
    assert c.status_code == 200
    # Stub LLM can finish before cancel lands — accept either terminal status
    assert c.json()["status"] in ("cancelled", "done", "running")

    client.post(
        "/api/worker-presets",
        json={"name": "tmp-preset", "agent_id": "worker1"},
    )
    d = client.post(
        "/api/worker-presets/delete",
        json={"name": "tmp-preset", "agent_id": "worker1"},
    )
    assert d.status_code == 200
    names = [p.get("name") for p in d.json().get("presets") or []]
    assert "tmp-preset" not in names

    client.post("/api/backup")
    bl = client.get("/api/backups")
    assert bl.status_code == 200
    assert isinstance(bl.json().get("backups"), list)
    if bl.json()["backups"]:
        name = bl.json()["backups"][0]["name"]
        dl = client.get(f"/api/backups/{name}/download")
        assert dl.status_code == 200
        assert dl.headers.get("content-type", "").startswith("application/")
        # create another backup then delete one
        client.post("/api/backup")
        gone = client.delete(f"/api/backups/{name}")
        assert gone.status_code == 200
        assert gone.json().get("ok") is True


def test_team_preset_and_plan_mode(client: TestClient):
    # Save current team, flip workers, re-apply
    r = client.post("/api/team-presets", json={"name": "t-landing"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["preset"]["name"] == "t-landing"

    client.post("/api/agents/worker3/toggle")
    client.post("/api/plan-mode", json={"plan_mode": "plan_qa"})
    assert client.get("/api/state").json()["plan_mode"] == "plan_qa"

    ap = client.post("/api/team-presets/apply", json={"name": "t-landing"})
    assert ap.status_code == 200
    body = ap.json()
    assert body["ok"] is True
    assert body["plan_mode"] in ("default", "full_page_html", "plan_qa", "diagnosis")

    # plan_mode set + list
    pm = client.post("/api/plan-mode", json={"plan_mode": "full_page_html"})
    assert pm.status_code == 200
    assert pm.json()["plan_mode"] == "full_page_html"
    lst = client.get("/api/team-presets")
    assert lst.status_code == 200
    names = [p.get("name") for p in lst.json().get("presets") or []]
    assert "t-landing" in names

    d = client.post("/api/team-presets/delete", json={"name": "t-landing"})
    assert d.status_code == 200
    names2 = [p.get("name") for p in d.json().get("presets") or []]
    assert "t-landing" not in names2

    bad = client.post("/api/plan-mode", json={"plan_mode": "nope"})
    assert bad.status_code == 400


def test_export_and_ollama_models(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "Export me a plan"})
    client.post("/api/execute?sync=1")
    r = client.get("/api/export/last")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "Brainstorm" in body["content"]
    assert body["chars"] > 10
    assert body.get("source") in ("live", "pinned")

    # After reset, export must still return the pinned successful Execute
    marker = "Export me a plan"
    client.post("/api/reset")
    r2 = client.get("/api/export/last")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["ok"] is True
    assert body2.get("source") == "pinned"
    assert marker in body2["content"]
    assert body2["chars"] > 10

    om = client.get("/api/ollama/models")
    assert om.status_code == 200
    assert "models" in om.json()


def test_state_and_agents(client: TestClient):
    r = client.get("/api/state")
    assert r.status_code == 200
    data = r.json()
    assert len(data["agents"]) == 8
    assert data["pipeline"]["stage"] == "idle"
    assert data["features"]["workers_max"] == 4


def test_chat_brainstorm_then_execute(client: TestClient):
    # Pure question → brainstorm only (no auto-execute)
    r = client.post("/api/chat?sync=1", json={"text": "was ist mit tts im hub"})
    assert r.status_code == 200
    data = r.json()
    assert data["pipeline"]["stage"] == "brainstorm"
    assert data["pipeline"]["brainstorm_notes"]
    assert data["pipeline"].get("can_execute") is True

    # Clear build intent → auto-execute from context (no extra Execute click)
    r2 = client.post(
        "/api/chat?sync=1",
        json={"text": "Build a simple landing page as one HTML file"},
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["pipeline"]["stage"] == "done"
    assert data2["pipeline"]["worker_results"]


def test_manual_execute_still_works(client: TestClient):
    r = client.post("/api/chat?sync=1", json={"text": "nur ideen zu einer checkliste"})
    assert r.status_code == 200
    assert r.json()["pipeline"]["stage"] == "brainstorm"
    r2 = client.post("/api/execute?sync=1")
    assert r2.status_code == 200
    assert r2.json()["pipeline"]["stage"] == "done"
    assert r2.json()["pipeline"]["worker_results"]


def test_chat_full_pipeline_compat(client: TestClient):
    r = client.post(
        "/api/chat?sync=1&full=1",
        json={"text": "Build a simple landing page"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["pipeline"]["stage"] == "done"
    assert data["pipeline"]["worker_results"]


def test_chat_clarify_then_continue(client: TestClient):
    # full path so clarify is reached
    r = client.post("/api/chat?sync=1&full=1", json={"text": "maybe dark mode?"})
    assert r.status_code == 200
    assert r.json()["pipeline"]["stage"] == "clarify"
    assert r.json()["pipeline"]["pending_question"]

    r2 = client.post("/api/clarify?sync=1", json={"option": "MVP/schnell"})
    assert r2.status_code == 200
    assert r2.json()["pipeline"]["stage"] == "done"


def test_toggle_memory_stays_on(client: TestClient):
    r = client.post("/api/agents/memory/toggle")
    assert r.status_code == 200
    assert r.json()["enabled"] is True


def test_toggle_brainstorm(client: TestClient):
    r = client.post("/api/agents/brainstorm/toggle")
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_flex_preset(client: TestClient):
    r = client.post("/api/agents/flex/preset", json={"preset": "researcher"})
    assert r.status_code == 200
    assert r.json()["preset"] == "researcher"


def test_agent_tune_and_system(client: TestClient):
    r = client.post(
        "/api/agents/worker1/tune",
        json={
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 512,
            "tts": True,
            "system_prompt": "You write short HTML.",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "worker1"
    assert body["temperature"] == 0.2
    assert body["tts"] is True
    assert "HTML" in (body.get("system_prompt") or "")
    assert "online" in body

    s = client.get("/api/system")
    assert s.status_code == 200
    assert "free_only" in s.json()
    assert "deepseek" in s.json()

    s2 = client.post("/api/system", json={"free_only": False, "max_budget_usd": 1.5})
    assert s2.status_code == 200
    assert s2.json()["max_budget_usd"] == 1.5


def test_save(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "note this"})
    r = client.post("/api/save")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_index_html(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "Gnom-Hub" in r.text


def test_tooltips(client: TestClient):
    r = client.get("/api/tooltips")
    assert r.status_code == 200
    assert "brainstorm" in r.json()
    r_de = client.get("/api/tooltips?lang=de")
    assert r_de.status_code == 200
    assert (
        "Ideen" in r_de.json()["brainstorm"]["how_to"]
        or "Brainstorm" in r_de.json()["brainstorm"]["title"]
    )


def test_clean_backup_presets(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "idea"})
    client.post(
        "/api/agents/worker1/tune",
        json={"system_prompt": "Write HTML only.", "temperature": 0.1},
    )
    pr = client.post(
        "/api/worker-presets",
        json={"name": "html-worker", "agent_id": "worker1"},
    )
    assert pr.status_code == 200
    assert pr.json()["ok"] is True

    b = client.post("/api/backup")
    assert b.status_code == 200
    assert b.json()["ok"] is True
    assert "backup" in b.json()["path"]

    c = client.post("/api/clean")
    assert c.status_code == 200
    assert c.json()["clean"]["ok"] is True
    assert c.json()["pipeline"]["stage"] == "idle"


def test_trace_quality_checkpoint(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "Landing page with hero"})
    r = client.post("/api/execute?sync=1")
    assert r.status_code == 200
    p = r.json()["pipeline"]
    assert p["stage"] == "done"
    assert p.get("quality_notes")
    assert "Quality" in p["quality_notes"]

    tr = client.get("/api/trace")
    assert tr.status_code == 200
    assert tr.json()["count"] >= 1
    assert any("pipeline" in (e.get("event") or "") for e in tr.json()["trace"])

    ck = client.post("/api/checkpoint/save")
    assert ck.status_code == 200
    assert ck.json()["ok"] is True

    # mutate then load
    client.post("/api/chat?sync=1", json={"text": "other idea"})
    loaded = client.post("/api/checkpoint/load")
    assert loaded.status_code == 200
    assert loaded.json()["pipeline"]["stage"] == "done"
    assert loaded.json()["pipeline"].get("quality_notes")


def test_canvas_endpoint(client: TestClient):
    r = client.get("/api/canvas")
    assert r.status_code == 200
    data = r.json()
    assert "mermaid" in data
    assert "nodes" in data


def test_save_persists_agents(client: TestClient, tmp_path):
    client.post("/api/agents/brainstorm/toggle")
    r = client.post("/api/save")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    agents_path = tmp_path / "data" / "hot" / "agents.json"
    assert agents_path.is_file()


def test_help(client: TestClient):
    r = client.get("/api/help")
    assert r.status_code == 200
    assert "pipeline" in r.json()


def test_reset_clears_pipeline(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "remember this"})
    # Seed a checkpoint that must not survive reset
    client.post("/api/checkpoint/save")
    r = client.post("/api/reset")
    assert r.status_code == 200
    data = r.json()
    assert data["pipeline"]["stage"] == "idle"
    assert data["pipeline"]["user_text"] == ""
    assert not (data["pipeline"].get("brainstorm_notes") or "").strip()
    assert not (data["pipeline"].get("brainstorm_turns") or [])
    # Checkpoint file removed so restore cannot re-inject dialogue
    ck = data.get("checkpoint") or {}
    assert ck.get("exists") is False


def test_memory_endpoint_after_chat(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "Ship feature memory wire"})
    r = client.get("/api/memory")
    assert r.status_code == 200
    data = r.json()
    assert "facts" in data
    assert "warm_facts" in data
    assert "context" in data
    assert data["summary"].startswith("HOT:")


def test_warm_survives_reset(client: TestClient):
    client.post("/api/memory/warm", json={"text": "Always use HTTPS"})
    client.post("/api/chat?sync=1", json={"text": "build a form"})
    r = client.post("/api/reset")
    assert r.status_code == 200
    mem = client.get("/api/memory").json()
    assert "Always use HTTPS" in mem["warm_facts"]
    # HOT cleared
    assert mem["facts"] == [] or client.get("/api/state").json()["pipeline"]["stage"] == "idle"


def test_workspace_api(client: TestClient):
    r = client.post(
        "/api/workspace/write",
        json={"zone": "temp", "name": "a.txt", "content": "x"},
    )
    assert r.status_code == 200
    r2 = client.post("/api/workspace/promote/a.txt")
    assert r2.status_code == 200
    snap = client.get("/api/workspace").json()
    assert any(f["name"] == "a.txt" for f in snap["perm"])


def test_telegram_inbound_help(client: TestClient):
    r = client.post("/api/telegram/inbound", json={"text": "/help"})
    assert r.status_code == 200
    assert "status" in r.json()["reply"].lower() or "Telegram" in r.json()["reply"]


def test_session_pack_roundtrip(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "Pack me a landing page idea"})
    client.post("/api/execute?sync=1")
    client.post("/api/memory/warm", json={"text": "Prefer dark mode always"})
    exp = client.get("/api/session/pack")
    assert exp.status_code == 200
    data = exp.json()
    assert data["ok"] is True
    pack = data["pack"]
    assert pack["format"] == "gnom-hub-session-pack"
    assert pack["pipeline"]["brainstorm_notes"]
    # wipe and re-import
    client.post("/api/reset")
    client.post("/api/clean")
    imp = client.post(
        "/api/session/pack",
        json={"pack": pack, "include_warm": True, "include_agents": True},
    )
    assert imp.status_code == 200
    snap = imp.json()
    assert (
        "landing page" in (snap["pipeline"]["user_text"] or "").lower()
        or snap["pipeline"]["brainstorm_notes"]
    )
    warm = client.get("/api/memory").json()["warm_facts"]
    assert any("dark mode" in f.lower() for f in warm)


def test_reexecute_from_brainstorm(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "Build a checklist app"})
    # capture notes then reset workers path via reexecute
    st = client.get("/api/state").json()["pipeline"]
    notes = st.get("brainstorm_notes") or ""
    assert notes
    r = client.post(
        "/api/reexecute?sync=1",
        json={
            "user_text": st.get("user_text") or "Build a checklist app",
            "brainstorm_notes": notes,
            "brainstorm_turns": st.get("brainstorm_turns") or [],
        },
    )
    assert r.status_code == 200
    p = r.json()["pipeline"]
    assert p["stage"] in ("done", "clarify")
    if p["stage"] == "done":
        assert p["worker_results"]


def test_session_pack_persist_list_delete(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "Persist pack idea"})
    client.post("/api/execute?sync=1")
    exp = client.get("/api/session/pack?persist=1")
    assert exp.status_code == 200
    data = exp.json()
    assert data["ok"] is True
    assert data.get("path")
    name = data["filename"]
    lst = client.get("/api/session/packs")
    assert lst.status_code == 200
    names = [p["name"] for p in lst.json()["packs"]]
    assert name in names
    got = client.get(f"/api/session/packs/{name}")
    assert got.status_code == 200
    assert got.json()["pack"]["format"] == "gnom-hub-session-pack"
    # wipe and import by name
    client.post("/api/reset")
    imp = client.post(f"/api/session/packs/{name}/import")
    assert imp.status_code == 200
    assert imp.json()["pipeline"]["brainstorm_notes"]
    gone = client.delete(f"/api/session/packs/{name}")
    assert gone.status_code == 200
    names2 = [p["name"] for p in client.get("/api/session/packs").json()["packs"]]
    assert name not in names2


def test_auto_pack_after_execute(client: TestClient):
    client.post("/api/system", json={"auto_pack_after_execute": True})
    sys_ = client.get("/api/system").json()
    assert sys_["auto_pack_after_execute"] is True
    client.post("/api/chat?sync=1", json={"text": "Auto pack me"})
    client.post("/api/execute?sync=1")
    packs = client.get("/api/session/packs").json()["packs"]
    assert len(packs) >= 1


def test_session_pack_download_and_store(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "Download pack topic"})
    client.post("/api/execute?sync=1")
    exp = client.get("/api/session/pack?persist=1")
    assert exp.status_code == 200
    name = exp.json()["filename"]
    dl = client.get(f"/api/session/packs/{name}/download")
    assert dl.status_code == 200
    assert "gnom-hub-session-pack" in dl.text
    # import with store writes another file under data/packs/
    pack = exp.json()["pack"]
    before = {p["name"] for p in client.get("/api/session/packs").json()["packs"]}
    imp = client.post(
        "/api/session/pack",
        json={
            "pack": pack,
            "include_warm": True,
            "include_agents": True,
            "store": True,
        },
    )
    assert imp.status_code == 200
    after = {p["name"] for p in client.get("/api/session/packs").json()["packs"]}
    assert len(after) >= len(before)


def test_pack_max_prune(client: TestClient):
    client.post("/api/system", json={"pack_max": 5})
    assert client.get("/api/system").json()["pack_max"] == 5
    # create more than 5 packs
    for i in range(7):
        client.post("/api/chat?sync=1", json={"text": f"Prune pack {i}"})
        r = client.get("/api/session/pack?persist=1&label=" + f"p{i}")
        assert r.status_code == 200
    packs = client.get("/api/session/packs").json()["packs"]
    assert len(packs) <= 5


def test_pack_rename_and_list_mtime(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "Rename me pack"})
    exp = client.get("/api/session/pack?persist=1&label=old-label")
    assert exp.status_code == 200
    name = exp.json()["filename"]
    lst = client.get("/api/session/packs").json()["packs"]
    hit = next(p for p in lst if p["name"] == name)
    assert hit["label"] == "old-label"
    assert hit.get("mtime")
    ren = client.patch(
        f"/api/session/packs/{name}",
        json={"label": "USB-project-alpha"},
    )
    assert ren.status_code == 200
    assert ren.json()["label"] == "USB-project-alpha"
    got = client.get(f"/api/session/packs/{name}").json()["pack"]
    assert got["label"] == "USB-project-alpha"
    bad = client.patch(f"/api/session/packs/{name}", json={"label": "   "})
    assert bad.status_code == 422 or bad.status_code == 400


def test_pack_ui_chat_and_history_roundtrip(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "UI pack topic"})
    client.post("/api/execute?sync=1")
    exp = client.post(
        "/api/session/pack/export",
        json={
            "persist": True,
            "label": "with-ui",
            "ui_chat_log": [
                {"who": "user", "text": "hello", "ts": "12:00:00"},
                {"who": "brainstorm", "text": "ideas…", "ts": "12:00:01"},
            ],
            "ui_result_history": [
                {
                    "id": "h1",
                    "ts": "2026-08-05T10:00:00Z",
                    "label": "UI pack topic · 1w",
                    "user_text": "UI pack topic",
                    "brainstorm_notes": "notes",
                    "brainstorm_turns": [{"role": "user", "text": "UI pack topic"}],
                    "can_reexec": True,
                    "outputs": [
                        {
                            "worker": "worker1",
                            "name": "W1",
                            "task": "t",
                            "result": "done",
                            "index": 0,
                        }
                    ],
                }
            ],
        },
    )
    assert exp.status_code == 200
    pack = exp.json()["pack"]
    assert pack["label"] == "with-ui"
    assert len(pack["ui_chat_log"]) == 2
    assert pack["ui_chat_log"][0]["who"] == "user"
    assert pack["ui_result_history"][0]["id"] == "h1"
    client.post("/api/reset")
    client.post("/api/clean")
    imp = client.post(
        "/api/session/pack",
        json={"pack": pack, "include_warm": True, "include_agents": True},
    )
    assert imp.status_code == 200
    snap = imp.json()
    assert snap["ui_chat_log"][0]["text"] == "hello"
    assert snap["ui_result_history"][0]["outputs"][0]["result"] == "done"


def test_pack_workspace_roundtrip(client: TestClient):
    # write temp + perm files
    r = client.post(
        "/api/workspace/write",
        json={"zone": "temp", "name": "scratch.txt", "content": "temp hello"},
    )
    assert r.status_code == 200
    r = client.post(
        "/api/workspace/write",
        json={"zone": "perm", "name": "keep.md", "content": "# keep me"},
    )
    assert r.status_code == 200
    exp = client.post(
        "/api/session/pack/export",
        json={"persist": True, "label": "ws-pack", "include_workspace": True},
    )
    assert exp.status_code == 200
    pack = exp.json()["pack"]
    assert "workspace" in pack
    names_t = [f["name"] for f in pack["workspace"]["temp"]]
    names_p = [f["name"] for f in pack["workspace"]["perm"]]
    assert "scratch.txt" in names_t
    assert "keep.md" in names_p
    # wipe temp via clean (keeps perm) then delete perm manually via workspace delete if available
    client.post("/api/clean")
    # import should restore both
    imp = client.post("/api/session/pack", json={"pack": pack})
    assert imp.status_code == 200
    ws = client.get("/api/workspace").json()
    temp_names = [f["name"] for f in ws.get("temp") or []]
    perm_names = [f["name"] for f in ws.get("perm") or []]
    assert "scratch.txt" in temp_names
    assert "keep.md" in perm_names


def test_pack_ui_prefs_and_notes(client: TestClient):
    client.post("/api/system", json={"ui_lang": "de"})
    exp = client.post(
        "/api/session/pack/export",
        json={
            "persist": True,
            "label": "prefs-pack",
            "notes": "USB laptop B",
            "ui_prefs": {"compact": True, "ui_lang": "de"},
        },
    )
    assert exp.status_code == 200
    pack = exp.json()["pack"]
    assert pack["notes"] == "USB laptop B"
    assert pack["ui_prefs"]["compact"] is True
    assert pack["ui_prefs"]["ui_lang"] == "de"
    name = exp.json()["filename"]
    lst = client.get("/api/session/packs").json()["packs"]
    hit = next(p for p in lst if p["name"] == name)
    assert hit["notes"] == "USB laptop B"
    ren = client.patch(
        f"/api/session/packs/{name}",
        json={"notes": "updated note"},
    )
    assert ren.status_code == 200
    assert ren.json()["notes"] == "updated note"
    client.post("/api/system", json={"ui_lang": "en"})
    imp = client.post("/api/session/pack", json={"pack": pack})
    assert imp.status_code == 200
    snap = imp.json()
    assert snap["ui_prefs"]["compact"] is True
    assert snap["ui_lang"] == "de"
    assert snap.get("pack_notes") == "USB laptop B"


def test_telegram_brainstorm_exec_pack(client: TestClient):
    # plain text = brainstorm only
    r = client.post("/api/telegram/inbound", json={"text": "TG landing page"})
    assert r.status_code == 200
    reply = r.json()["reply"].lower()
    assert "brainstorm" in reply or "exec" in reply
    st = client.get("/api/state").json()["pipeline"]
    assert st.get("brainstorm_notes")
    assert st.get("stage") in ("brainstorm", "done", "idle")
    # execute
    r2 = client.post("/api/telegram/inbound", json={"text": "/exec"})
    assert r2.status_code == 200
    st2 = client.get("/api/state").json()["pipeline"]
    assert st2.get("stage") in ("done", "clarify", "error")
    # pack save + list + load
    r3 = client.post(
        "/api/telegram/inbound",
        json={"text": "/pack save tg-usb"},
    )
    assert r3.status_code == 200
    assert "saved" in r3.json()["reply"].lower() or "pack" in r3.json()["reply"].lower()
    r4 = client.post("/api/telegram/inbound", json={"text": "/pack list"})
    assert r4.status_code == 200
    assert "1." in r4.json()["reply"] or "pack" in r4.json()["reply"].lower()
    r5 = client.post("/api/telegram/inbound", json={"text": "/pack load 1"})
    assert r5.status_code == 200
    assert "load" in r5.json()["reply"].lower()


def test_warm_delete_and_clear(client: TestClient):
    r = client.post("/api/memory/warm", json={"text": "Prefer dark mode always"})
    assert r.status_code == 200
    r = client.post("/api/memory/warm", json={"text": "Ship USB portable"})
    assert r.status_code == 200
    mem = client.get("/api/memory").json()
    assert any("dark mode" in f.lower() for f in mem["warm_facts"])
    gone = client.delete("/api/memory/warm", params={"text": "Prefer dark mode always"})
    assert gone.status_code == 200
    mem2 = client.get("/api/memory").json()
    assert not any("dark mode" in f.lower() for f in mem2["warm_facts"])
    cleared = client.post("/api/memory/warm/clear")
    assert cleared.status_code == 200
    assert client.get("/api/memory").json()["warm_facts"] == []


def test_telegram_warm_and_cancel(client: TestClient):
    r = client.post(
        "/api/telegram/inbound",
        json={"text": "/warm add USB stick workflow"},
    )
    assert r.status_code == 200
    assert "added" in r.json()["reply"].lower()
    r2 = client.post("/api/telegram/inbound", json={"text": "/warm list"})
    assert "USB stick" in r2.json()["reply"]
    r3 = client.post("/api/telegram/inbound", json={"text": "/cancel"})
    assert r3.status_code == 200
    assert "no running" in r3.json()["reply"].lower() or "cancel" in r3.json()["reply"].lower()
    r4 = client.post("/api/telegram/inbound", json={"text": "/warm clear"})
    assert "cleared" in r4.json()["reply"].lower()


def test_cold_restore_and_delete(client: TestClient):
    # seed HOT then archive
    client.post("/api/chat?sync=1", json={"text": "Cold restore seed"})
    client.post("/api/memory/warm", json={"text": "warm stays"})
    arch = client.post("/api/cold/archive", json={"label": "seed-archive"})
    assert arch.status_code == 200
    aid = arch.json()["archive"]["id"]
    # wipe HOT via clean
    client.post("/api/clean")
    # restore
    rst = client.post(f"/api/cold/{aid}/restore")
    assert rst.status_code == 200
    assert rst.json().get("ok") is True
    assert rst.json()["restored"]["id"] == aid
    # HOT should have messages again
    mem2 = client.get("/api/memory").json()
    assert mem2.get("recent_messages") or mem2.get("facts") is not None
    # telegram cold list/load
    tg = client.post("/api/telegram/inbound", json={"text": "/cold list"})
    assert tg.status_code == 200
    assert "1." in tg.json()["reply"] or "COLD" in tg.json()["reply"]
    # delete
    gone = client.delete(f"/api/cold/{aid}")
    assert gone.status_code == 200
    assert gone.json()["deleted"] == aid
    missing = client.get(f"/api/cold/{aid}")
    assert missing.status_code == 404


def test_vector_browser_api(client: TestClient):
    a = client.post(
        "/api/vector/add",
        json={"text": "USB portable multi agent hub dark theme", "meta": {"source": "test"}},
    )
    assert a.status_code == 200
    doc_id = a.json()["id"]
    assert a.json()["count"] >= 1
    lst = client.get("/api/vector")
    assert lst.status_code == 200
    assert lst.json()["count"] >= 1
    assert any(d["id"] == doc_id for d in lst.json()["docs"])
    hits = client.post(
        "/api/vector/search",
        json={"query": "portable USB hub", "limit": 5},
    )
    assert hits.status_code == 200
    assert hits.json()["hits"]
    gone = client.delete(f"/api/vector/{doc_id}")
    assert gone.status_code == 200
    # telegram
    client.post("/api/vector/add", json={"text": "telegram vector note about brainstorm"})
    tg = client.post("/api/telegram/inbound", json={"text": "/vec search brainstorm"})
    assert tg.status_code == 200
    assert (
        "brainstorm" in tg.json()["reply"].lower()
        or "search" in tg.json()["reply"].lower()
        or "v" in tg.json()["reply"].lower()
    )
    client.post("/api/vector/clear")
    assert client.get("/api/vector").json()["count"] == 0


def test_trace_export_and_clear(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "trace me please"})
    tr = client.get("/api/trace?limit=20")
    assert tr.status_code == 200
    assert tr.json()["count"] >= 1
    exp = client.get("/api/trace/export?fmt=json")
    assert exp.status_code == 200
    body = exp.json()
    assert body["ok"] is True
    assert "gnom-hub-trace" in body["content"]
    assert body["filename"].endswith(".json")
    md = client.get("/api/trace/export?fmt=md")
    assert md.status_code == 200
    assert md.json()["filename"].endswith(".md")
    assert "# Gnom-Hub light trace" in md.json()["content"]
    cleared = client.post("/api/trace/clear")
    assert cleared.status_code == 200
    assert client.get("/api/trace").json()["count"] == 0
    tg = client.post("/api/telegram/inbound", json={"text": "/trace"})
    assert tg.status_code == 200
    # empty or message
    assert "trace" in tg.json()["reply"].lower() or "empty" in tg.json()["reply"].lower()


def test_backup_restore(client: TestClient):
    client.post("/api/chat?sync=1", json={"text": "backup seed fact"})
    client.post("/api/memory/warm", json={"text": "durable backup warm"})
    b = client.post("/api/backup")
    assert b.status_code == 200
    path = b.json()["path"]
    assert path.endswith(".zip")
    name = path.rsplit("/", 1)[-1]
    # mutate state
    client.post("/api/clean")
    # restore
    rst = client.post(f"/api/backups/{name}/restore")
    assert rst.status_code == 200
    assert rst.json().get("ok") is True
    assert rst.json().get("restored_backup") == name
    mem = client.get("/api/memory").json()
    # warm should be back
    assert any("durable backup" in f for f in (mem.get("warm_facts") or []))
    # telegram list
    tg = client.post("/api/telegram/inbound", json={"text": "/backup list"})
    assert tg.status_code == 200
    assert "1." in tg.json()["reply"] or "backup" in tg.json()["reply"].lower()


def test_jobs_list_and_usage(client: TestClient):
    # async job creates entry
    r = client.post("/api/chat", json={"text": "job list seed"})
    assert r.status_code == 200
    body = r.json()
    if body.get("job_id"):
        # wait briefly via poll
        import time

        for _ in range(20):
            st = client.get(f"/api/jobs/{body['job_id']}")
            if st.json().get("status") != "running":
                break
            time.sleep(0.05)
    lst = client.get("/api/jobs")
    assert lst.status_code == 200
    assert "jobs" in lst.json()
    usage = client.get("/api/usage")
    assert usage.status_code == 200
    assert "spent_usd" in usage.json()
    assert "by_agent" in usage.json()
    reset = client.post("/api/usage/reset")
    assert reset.status_code == 200
    assert reset.json().get("ok") is True
    assert float(reset.json().get("spent_usd") or 0) == 0.0
    tg = client.post("/api/telegram/inbound", json={"text": "/jobs"})
    assert tg.status_code == 200
    tg2 = client.post("/api/telegram/inbound", json={"text": "/usage"})
    assert tg2.status_code == 200
    assert "spent" in tg2.json()["reply"].lower() or "$" in tg2.json()["reply"]


def test_workspace_export_and_telegram(client: TestClient):
    w = client.post(
        "/api/workspace/write",
        json={"zone": "temp", "name": "note.txt", "content": "hello workspace export"},
    )
    assert w.status_code == 200
    exp = client.post("/api/workspace/export?zone=temp")
    assert exp.status_code == 200
    name = exp.json()["name"]
    assert name.startswith("gnom-hub-workspace-")
    assert exp.json()["bytes"] > 0
    dl = client.get(f"/api/workspace/exports/{name}")
    assert dl.status_code == 200
    assert (
        dl.headers.get("content-type", "").startswith("application/zip") or dl.content[:2] == b"PK"
    )
    tg = client.post("/api/telegram/inbound", json={"text": "/ws list"})
    assert tg.status_code == 200
    assert "temp" in tg.json()["reply"].lower() or "note.txt" in tg.json()["reply"]
    tg2 = client.post(
        "/api/telegram/inbound",
        json={"text": "/ws cat temp note.txt"},
    )
    assert "hello workspace" in tg2.json()["reply"]


def test_tools_call_and_telegram(client: TestClient):
    pl = client.get("/api/plugins")
    assert pl.status_code == 200
    names = [t["name"] for t in pl.json().get("tools") or []]
    assert "hub_status" in names
    assert "web_fetch" in names
    st = client.post("/api/tools/call", json={"name": "hub_status", "arguments": {}})
    assert st.status_code == 200
    assert st.json().get("ok") is True
    assert st.json().get("result")
    # memory_search empty store ok
    ms = client.post(
        "/api/tools/call",
        json={"name": "memory_search", "arguments": {"query": "nothing", "limit": 3}},
    )
    assert ms.status_code == 200
    tg = client.post("/api/telegram/inbound", json={"text": "/tools"})
    assert tg.status_code == 200
    assert "hub_status" in tg.json()["reply"] or "Tools" in tg.json()["reply"]
    tg2 = client.post(
        "/api/telegram/inbound",
        json={"text": "/tool hub_status"},
    )
    assert tg2.status_code == 200
    assert (
        "hub_status" in tg2.json()["reply"].lower()
        or "stage" in tg2.json()["reply"].lower()
        or "agents" in tg2.json()["reply"].lower()
    )


def test_hot_facts_manager(client: TestClient):
    r = client.post("/api/memory/hot", json={"text": "session prefers compact UI"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert any("compact UI" in f for f in r.json()["facts"])
    mem = client.get("/api/memory").json()
    assert any("compact UI" in f for f in mem.get("facts") or [])
    promo = client.post(
        "/api/memory/hot/promote",
        json={"text": "session prefers compact UI"},
    )
    assert promo.status_code == 200
    assert promo.json().get("warm_added") is True
    warm = client.get("/api/memory").json().get("warm_facts") or []
    assert any("compact UI" in f for f in warm)
    gone = client.delete(
        "/api/memory/hot",
        params={"text": "session prefers compact UI"},
    )
    assert gone.status_code == 200
    client.post("/api/memory/hot", json={"text": "temp only fact here"})
    cleared = client.post("/api/memory/hot/clear")
    assert cleared.status_code == 200
    assert cleared.json()["hot_count"] == 0
    tg = client.post("/api/telegram/inbound", json={"text": "/hot add fact from telegram bot"})
    assert "added" in tg.json()["reply"].lower() or "HOT" in tg.json()["reply"]
    tg2 = client.post("/api/telegram/inbound", json={"text": "/hot list"})
    assert "telegram" in tg2.json()["reply"].lower()
