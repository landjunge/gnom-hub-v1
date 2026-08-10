"""Snapshot exposes DoD validation checklist for UI (Slice D)."""

from __future__ import annotations

from gnom_hub.hub import Hub
from gnom_hub.pipeline.dod_gate import run_dod_check
from gnom_hub.snapshot_ops import _worst_validation


def test_worst_validation_picks_failed_gate():
    outs = [
        {
            "worker": "worker_a",
            "validation": {
                "ok": True,
                "score": 100,
                "issues": [],
                "checklist": [{"id": "too_short", "pass": True}],
            },
        },
        {
            "worker": "worker_b",
            "result": "<html>",
            "validation": {
                "ok": False,
                "score": 20,
                "retryable": True,
                "issues": ["incomplete_html"],
                "soft_issues": [],
                "hints": ["fix html"],
                "checklist": [
                    {
                        "id": "incomplete_html",
                        "label": "HTML incomplete",
                        "severity": "must",
                        "pass": False,
                    }
                ],
            },
        },
    ]
    v = _worst_validation(outs)
    assert v is not None
    assert v["ok"] is False
    assert v["worker"] == "worker_b"
    assert "incomplete_html" in v["issues"]
    assert any(c.get("id") == "incomplete_html" for c in v["checklist"])


def test_snapshot_pipeline_validation_has_checklist():
    """After a broken HTML execute path, snapshot.pipeline.validation is UI-ready."""
    h = Hub()
    # Inject fake worker output with real gate shape
    gate = run_dod_check(
        "<!DOCTYPE html><html><body>x</body>",
        user_text="Build a landing page HTML with dark theme",
        task="landing HTML",
        requirements=["User: dark theme"],
    )
    assert gate.get("ok") is False
    assert gate.get("checklist")
    h.pipeline.state.worker_outputs = [
        {
            "worker": "worker_1",
            "name": "Worker 1",
            "result": "<!DOCTYPE html><html><body>x</body>",
            "validation": gate,
        }
    ]
    h.pipeline.state.stage = type(h.pipeline.state.stage).done  # enum
    snap = h.snapshot()
    pipe = snap["pipeline"]
    val = pipe.get("validation")
    assert val is not None
    assert val["ok"] is False
    assert isinstance(val.get("checklist"), list)
    assert val["checklist"]
    assert "score" in val
    assert "retryable" in val


def test_gate_checklist_items_have_pass_flag():
    gate = run_dod_check(
        "FEHLER - kein Deliverable\nKey missing",
        user_text="anything",
        task="t",
        requirements=[],
    )
    assert gate.get("ok") is False
    assert any(c.get("pass") is False for c in (gate.get("checklist") or []))
