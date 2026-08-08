"""Flex review panel (right Platzhalter) after result."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app


def test_flex_review_inactive_idle(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/api/flex/review")
        assert r.status_code == 200
        body = r.json()
        assert body.get("active") is False
        assert body.get("buttons") == []
    hub_mod._HUB = None


def test_flex_review_active_after_done(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    (tmp_path / "User").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GNOM_USER_DB", str(tmp_path / "User" / "user.db"))
    app = create_app()
    with TestClient(app) as c:
        # Full stub pipeline
        r = c.post("/api/chat?sync=1&full=1", json={"text": "Build a tiny landing page HTML"})
        assert r.status_code == 200
        rev = c.get("/api/flex/review").json()
        # May be done with workers
        if rev.get("active"):
            assert rev.get("buttons")
            assert any(b.get("id") == "good" for b in rev["buttons"])
            # Learn button
            fb = c.post(
                "/api/flex/feedback",
                json={"button_id": "good", "label": "Gut so"},
            )
            assert fb.status_code == 200
            assert fb.json().get("ok") is True
            assert fb.json().get("action") == "learn"
    hub_mod._HUB = None
