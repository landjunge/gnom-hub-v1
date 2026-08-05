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
    r = client.post("/api/chat", json={"text": "Build a simple landing page"})
    assert r.status_code == 200
    data = r.json()
    assert data["pipeline"]["stage"] == "done"
    assert data["pipeline"]["brainstorm_notes"]
    assert data["pipeline"]["worker_results"]


def test_chat_clarify_then_continue(client: TestClient):
    r = client.post("/api/chat", json={"text": "maybe dark mode?"})
    assert r.status_code == 200
    assert r.json()["pipeline"]["stage"] == "clarify"
    assert r.json()["pipeline"]["pending_question"]

    r2 = client.post("/api/clarify", json={"option": "Yes"})
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


def test_save(client: TestClient):
    client.post("/api/chat", json={"text": "note this"})
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
    client.post("/api/chat", json={"text": "remember this"})
    r = client.post("/api/reset")
    assert r.status_code == 200
    data = r.json()
    assert data["pipeline"]["stage"] == "idle"
    assert data["pipeline"]["user_text"] == ""


def test_memory_endpoint_after_chat(client: TestClient):
    client.post("/api/chat", json={"text": "Ship feature memory wire"})
    r = client.get("/api/memory")
    assert r.status_code == 200
    data = r.json()
    assert "facts" in data
    assert "context" in data
    assert data["summary"].startswith("HOT:")
