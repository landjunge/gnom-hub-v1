"""Gnom does not own a second cloud-provider stack."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app
from gnom_hub.stack import stack_snapshot


def test_default_owner_is_tollgate(monkeypatch, tmp_path):
    monkeypatch.delenv("GNOM_TOLLGATE_LLM", raising=False)
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    got = stack_snapshot()
    assert got["roles"]["tollgate"] == "providers"
    assert got["roles"]["gnom"] == "desk"
    assert got["roles"]["threaddesk"] == "prepare"
    assert got["providers_owner"] == "tollgate"
    assert got["via_tollgate"] is True
    assert "ollama" in got["local_only"]


def test_legacy_opt_out(monkeypatch, tmp_path):
    monkeypatch.setenv("GNOM_TOLLGATE_LLM", "0")
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    assert stack_snapshot()["providers_owner"] == "gnom-legacy"


def test_health_exposes_stack(tmp_path, monkeypatch):
    monkeypatch.delenv("GNOM_TOLLGATE_LLM", raising=False)
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        stack = r.json()["stack"]
        assert stack["providers_owner"] == "tollgate"
        assert stack["roles"]["threaddesk"] == "prepare"
    hub_mod._HUB = None


def test_manager_remembers_tollgate_route(monkeypatch):
    import sys
    import types

    from gnom_hub.llm.manager import LLMManager
    from gnom_hub.llm.types import LLMMessage

    fake = types.ModuleType("tollgate")

    def routed_chat(*_a, **_k):
        return {
            "ok": True,
            "content": "hi",
            "model": "zen-free",
            "routing": {"route": {"provider": "opencode_zen", "model": "zen-free"}},
        }

    fake.routed_chat = routed_chat
    monkeypatch.setitem(sys.modules, "tollgate", fake)
    monkeypatch.delenv("TOLLGATE_URL", raising=False)
    m = LLMManager(keys={})
    m._chat_via_tollgate(
        [LLMMessage(role="user", content="hi")],
        model="",
        provider=None,
        agent="brainstorm",
        temperature=0.2,
        max_tokens=16,
        prefer_free=True,
    )
    route = m.usage_snapshot()["last_route"]
    assert route["provider"] == "opencode_zen"
    assert route["via"] == "tollgate"


def test_extract_tollgate_route_from_payload():
    from gnom_hub.stack import extract_tollgate_route

    got = extract_tollgate_route(
        {
            "ok": True,
            "model": "deepseek-v4-flash",
            "routing": {"route": {"provider": "deepseek", "model": "deepseek-v4-flash"}},
        }
    )
    assert got["via"] == "tollgate"
    assert got["provider"] == "deepseek"
    assert got["model"] == "deepseek-v4-flash"
    empty = extract_tollgate_route({})
    assert empty["provider"] == ""


def test_gnom_has_no_openai_anthropic_clients():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "gnom_hub"
    hits: list[str] = []
    for p in root.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        if "import openai" in text or "from openai" in text:
            hits.append(str(p))
        if "import anthropic" in text or "from anthropic" in text:
            hits.append(str(p))
    assert hits == []
