"""R5.4: HTTP routes live in domain routers; URLs stay the same."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from gnom_hub.api.app import create_app

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "src/gnom_hub/api"
ROUTERS = API / "routers"
EXPECTED = [
    "agents.py",
    "chat.py",
    "execute.py",
    "jobs.py",
    "memory.py",
    "rest.py",
    "skills.py",
    "system.py",
    "tools.py",
    "workspace.py",
]


def test_router_files_exist():
    names = sorted(p.name for p in ROUTERS.glob("*.py") if p.name != "__init__.py")
    assert names == EXPECTED


def test_create_app_includes_routers_not_inline_chat():
    app_src = (API / "app.py").read_text(encoding="utf-8")
    assert "app.include_router(chat.router)" in app_src
    assert "app.include_router(execute.router)" in app_src
    assert '@app.post("/api/chat")' not in app_src
    assert '@app.post("/api/god-mode")' not in app_src
    assert (ROUTERS / "chat.py").read_text(encoding="utf-8").count('@router.post("/api/chat")') == 1
    assert (ROUTERS / "system.py").read_text(encoding="utf-8").count(
        '@router.post("/api/god-mode")'
    ) == 1


def test_openapi_keeps_contract_paths():
    client = TestClient(create_app())
    paths = set(client.get("/openapi.json").json()["paths"])
    for p in (
        "/api/chat",
        "/api/execute",
        "/api/jobs",
        "/api/jobs/busy",
        "/api/agents",
        "/api/god-mode",
        "/api/workspace",
        "/api/memory",
        "/api/skills",
        "/api/tools/call",
        "/api/help",
        "/",
    ):
        assert p in paths, p


def test_chat_still_does_not_start_workers_on_default_send():
    chat = (ROUTERS / "chat.py").read_text(encoding="utf-8")
    assert "chat_async" in chat
    assert "full=full" in chat
    execute = (ROUTERS / "execute.py").read_text(encoding="utf-8")
    assert '@router.post("/api/execute")' in execute
