"""Send is never Execute — desk chat must not start workers or tools."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline import Pipeline


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        yield c
    hub_mod._HUB = None


def test_build_language_send_stays_brainstorm(client: TestClient) -> None:
    r = client.post(
        "/api/chat?sync=1",
        json={"text": "Build a simple landing page as one HTML file"},
    )
    assert r.status_code == 200
    pipe = r.json()["pipeline"]
    assert pipe["stage"] == "brainstorm"
    assert not (pipe.get("worker_results") or [])
    assert not (pipe.get("worker_outputs") or [])


def test_chat_full_query_does_not_run_workers(client: TestClient) -> None:
    r = client.post(
        "/api/chat?sync=1&full=1",
        json={"text": "Build a simple landing page"},
    )
    assert r.status_code == 200
    pipe = r.json()["pipeline"]
    assert pipe["stage"] == "brainstorm"
    assert not (pipe.get("worker_results") or [])


def test_go_only_send_does_not_execute() -> None:
    pipe = Pipeline(EventBus())
    pipe.brainstorm_turn("nur ideen zu einer checkliste")
    st = pipe.brainstorm_turn("mach das")
    assert st.stage.value == "brainstorm"
    assert not (st.worker_results or [])


def test_execute_after_send_still_runs_workers(client: TestClient) -> None:
    r = client.post("/api/chat?sync=1", json={"text": "nur ideen zu einer checkliste"})
    assert r.status_code == 200
    assert r.json()["pipeline"]["stage"] == "brainstorm"
    r2 = client.post("/api/execute?sync=1")
    assert r2.status_code == 200
    assert r2.json()["pipeline"]["stage"] in ("done", "clarify", "error")
    assert r2.json()["pipeline"].get("worker_results") is not None
