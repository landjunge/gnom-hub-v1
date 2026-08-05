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


def test_state_and_agents(client: TestClient):
    r = client.get("/api/state")
    assert r.status_code == 200
    data = r.json()
    assert len(data["agents"]) == 6
    assert data["pipeline"]["stage"] == "idle"


def test_chat_pipeline_done(client: TestClient):
    r = client.post("/api/chat?sync=1", json={"text": "Build a simple landing page"})
    assert r.status_code == 200
    data = r.json()
    assert data["pipeline"]["stage"] == "done"
    assert data["pipeline"]["brainstorm_notes"]
    assert data["pipeline"]["worker_results"]


def test_chat_clarify_then_continue(client: TestClient):
    r = client.post("/api/chat?sync=1", json={"text": "maybe dark mode?"})
    assert r.status_code == 200
    assert r.json()["pipeline"]["stage"] == "clarify"
    assert r.json()["pipeline"]["pending_question"]

    r2 = client.post("/api/clarify?sync=1", json={"option": "Yes"})
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
    r = client.post("/api/reset")
    assert r.status_code == 200
    data = r.json()
    assert data["pipeline"]["stage"] == "idle"
    assert data["pipeline"]["user_text"] == ""


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
