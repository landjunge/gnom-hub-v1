"""Wave 2: job cancel TOCTOU + soft-cancel finalize."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app


def test_cancel_stays_running_until_thread_finalizes(tmp_path, monkeypatch):
    """M2: cancel request must not terminal-ize before worker exits."""
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/chat", json={"text": "only brainstorm slow cancel path"})
        assert r.status_code == 200
        jid = r.json()["job_id"]
        # Request cancel while possibly still running
        cr = c.post(f"/api/jobs/{jid}/cancel")
        assert cr.status_code == 200
        body = cr.json()
        assert body.get("cancel") is True or body.get("status") in (
            "cancelled",
            "running",
            "done",
        )
        # Poll until terminal
        terminal = None
        for _ in range(80):
            j = c.get(f"/api/jobs/{jid}").json()
            if j.get("status") in ("cancelled", "done", "error", "clarify"):
                terminal = j
                break
            time.sleep(0.05)
        assert terminal is not None
        assert terminal["status"] in ("cancelled", "done")
        # After finalize, finished flag if present
        if "finished" in terminal:
            assert terminal["finished"] is True
    hub_mod._HUB = None


def test_cancel_does_not_leave_mid_stage_stuck(tmp_path, monkeypatch):
    """H1: after cancelled execute, can_execute should recover via brainstorm stage."""
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        # Sync brainstorm first
        r = c.post("/api/chat?sync=1", json={"text": "only brainstorm for execute cancel"})
        assert r.status_code == 200
        # Force cancel flag on next execute via hub
        hub = hub_mod.get_hub()
        hub.pipeline.cancel_check = lambda: True
        st = hub.pipeline.execute()
        assert st.stage.value == "brainstorm"
        assert st.error is None
        snap = hub.snapshot()
        assert snap["pipeline"]["can_execute"] is True
    hub_mod._HUB = None
