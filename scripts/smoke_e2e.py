#!/usr/bin/env python3
"""In-process E2E smoke: hub + API + stub pipeline (no live LLM required)."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running without install: PYTHONPATH=src
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app


def main() -> int:
    # Isolate runtime data under repo data/smoke-run (relative, USB-ok)
    smoke_root = ROOT / "data" / "smoke-run"
    smoke_root.mkdir(parents=True, exist_ok=True)
    hub_mod._HUB = None
    hub_mod.project_root = lambda: smoke_root  # type: ignore[method-assign]

    app = create_app()
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "ok"

        r = client.get("/")
        assert r.status_code == 200
        assert "Gnom-Hub" in r.text

        r = client.post("/api/chat?sync=1", json={"text": "Smoke plan a tiny checklist app"})
        assert r.status_code == 200, r.text
        snap = r.json()
        stage = snap["pipeline"]["stage"]
        assert stage in ("done", "clarify"), stage
        assert snap["agents"], "agents missing"
        assert "memory" in snap

        if stage == "clarify":
            r = client.post("/api/clarify?sync=1", json={"option": "Yes"})
            assert r.status_code == 200, r.text
            assert r.json()["pipeline"]["stage"] == "done"

        r = client.post("/api/save")
        assert r.status_code == 200
        assert r.json().get("ok") is True

        r = client.get("/api/memory")
        assert r.status_code == 200
        assert "summary" in r.json()

        r = client.get("/api/help")
        assert r.status_code == 200

        r = client.post("/api/memory/warm", json={"text": "Smoke warm durable fact"})
        assert r.status_code == 200

        r = client.post(
            "/api/workspace/write",
            json={"zone": "temp", "name": "smoke.txt", "content": "ok"},
        )
        assert r.status_code == 200

        r = client.post("/api/telegram/inbound", json={"text": "/status"})
        assert r.status_code == 200
        assert "stage=" in r.json()["reply"]

        r = client.post("/api/cold/archive", json={"label": "smoke"})
        assert r.status_code == 200 and r.json().get("ok")

        r = client.post("/api/vector/search", json={"query": "checklist", "limit": 3})
        assert r.status_code == 200

        r = client.post("/api/god-mode", json={"enabled": True, "reason": "smoke"})
        assert r.json().get("enabled") is True
        r = client.post("/api/god-mode", json={"enabled": False})
        assert r.json().get("enabled") is False

        r = client.post("/api/computer-use/inspect")
        assert r.status_code == 200

        r = client.get("/api/mcp/tools")
        assert r.status_code == 200 and "tools" in r.json()

        r = client.post("/api/tools/call", json={"name": "hub_status", "arguments": {}})
        assert r.status_code == 200

        r = client.post("/api/reset")
        assert r.status_code == 200
        assert r.json()["pipeline"]["stage"] == "idle"
        # WARM survives HOT reset
        mem = client.get("/api/memory").json()
        assert "Smoke warm durable fact" in mem.get("warm_facts", [])

    print("SMOKE E2E OK")
    print(f"  root={smoke_root}")
    print("  health…warm…cold…vector…god…computer…mcp…reset")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SMOKE E2E FAIL: {exc}", file=sys.stderr)
        raise
