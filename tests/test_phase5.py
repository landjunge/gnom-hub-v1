from pathlib import Path

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app
from gnom_hub.memory.cold import ColdArchive
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.plugins.loader import PluginLoader
from gnom_hub.plugins.registry import ToolRegistry
from gnom_hub.security.god_mode import GodMode


def test_cold_archive(tmp_path: Path):
    cold = ColdArchive(tmp_path)
    meta = cold.archive_hot(
        session={"messages": [{"role": "user", "content": "hi"}], "facts": ["a"]},
        canvas_mmd="flowchart TD\n",
        label="t1",
    )
    assert meta["id"]
    listed = cold.list_archives()
    assert listed and listed[0]["id"] == meta["id"]
    got = cold.get(meta["id"])
    assert got and got["session"]["facts"] == ["a"]


def test_vector_search(tmp_path: Path):
    vs = VectorStore(tmp_path)
    vs.add("dark theme preference for UI", meta={"k": 1})
    vs.add("usb portable installation path", meta={"k": 2})
    hits = vs.search("dark theme UI", limit=3)
    assert hits
    assert "dark" in hits[0]["text"].lower() or hits[0]["score"] > 0


def test_god_mode_paths():
    gm = GodMode()
    assert not gm.allow_path("/etc/passwd")
    assert gm.allow_path("data/hot/session.json")
    gm.enable("test")
    assert gm.allow_path("/etc/passwd")
    gm.disable("test")
    assert not gm.allow_path("/etc/passwd")


def test_plugin_echo_loads(tmp_path: Path):
    # use real plugins dir from repo
    from gnom_hub.config.paths import project_root

    reg = ToolRegistry()
    loader = PluginLoader(project_root() / "plugins", reg)
    loaded = loader.discover_and_load()
    assert any(p["id"] == "echo" for p in loaded)
    out = reg.call("echo", {"text": "hi"})
    assert out["echo"] == "hi"


def test_api_phase5(tmp_path, monkeypatch):
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    # copy plugins into tmp? loader uses project_root - monkeypatch project_root
    # PluginLoader uses hub.root which is tmp - no plugins. register via API tools from core only.
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/chat", json={"text": "archive me later"})
        assert r.status_code == 200
        r = c.post("/api/cold/archive", json={"label": "api-test"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        r = c.get("/api/cold")
        assert r.status_code == 200
        assert r.json()["archives"]

        r = c.post("/api/vector/add", json={"text": "portable usb stick workflow"})
        assert r.status_code == 200
        r = c.post("/api/vector/search", json={"query": "usb portable", "limit": 3})
        assert r.status_code == 200
        assert r.json()["hits"]

        r = c.post("/api/god-mode", json={"enabled": True, "reason": "test"})
        assert r.status_code == 200
        assert r.json()["enabled"] is True
        r = c.post("/api/god-mode", json={"enabled": False})
        assert r.json()["enabled"] is False

        r = c.post("/api/computer-use/inspect")
        assert r.status_code == 200
        assert "capture" in r.json()

        r = c.post("/api/computer-use/click", json={"x": 1, "y": 2})
        assert r.status_code == 200
        assert r.json()["dry_run"] is True

        r = c.get("/api/mcp/tools")
        assert r.status_code == 200
        assert "tools" in r.json()

        r = c.post("/api/tools/call", json={"name": "hub_status", "arguments": {}})
        assert r.status_code == 200
        assert r.json()["ok"] is True
    hub_mod._HUB = None
