"""Stage done with FEHLER must not look like a successful deliverable."""

from types import SimpleNamespace

from gnom_hub.pipeline.dod_gate import run_dod_check
from gnom_hub.snapshot_ops import _deliverable_ok


def test_deliverable_ok_false_on_worker_fehler():
    body = (
        "Worker 1 FEHLER - kein Deliverable\n"
        "LLM-Fehler (worker1): tollgate package not installed\n"
        "Kein Stub-Ersatz. Key pruefen, Budget pruefen, dann erneut ausfuehren."
    )
    gate = run_dod_check(body, user_text="Build a landing page HTML", task="landing HTML")
    st = SimpleNamespace(
        worker_outputs=[
            {
                "worker": "worker1",
                "name": "Worker 1",
                "result": body,
                "validation": gate,
            }
        ],
        worker_results=[body],
    )
    assert gate.get("ok") is False
    assert _deliverable_ok(st) is False


def test_deliverable_ok_true_on_complete_html():
    html = (
        "<!DOCTYPE html><html><head><title>Bean</title></head>"
        "<body>"
        + ("<p>coffee shop landing with hero footer and cards.</p>" * 20)
        + "</body></html>"
    )
    gate = run_dod_check(
        html,
        user_text="Build a landing page HTML for Bean & Bloom coffee",
        task="landing HTML",
        requirements=["User: hero", "User: footer"],
    )
    st = SimpleNamespace(
        worker_outputs=[{"worker": "worker1", "result": html, "validation": gate}],
        worker_results=[html],
    )
    assert _deliverable_ok(st) is True


def test_snapshot_exposes_deliverable_ok():
    from gnom_hub.hub import Hub
    from gnom_hub.pipeline.models import PipelineStage

    h = Hub()
    body = "Worker 1 FEHLER - kein Deliverable\nLLM-Fehler"
    gate = run_dod_check(body, user_text="Build HTML landing", task="page")
    h.pipeline.state.worker_outputs = [{"worker": "worker1", "result": body, "validation": gate}]
    h.pipeline.state.worker_results = [body]
    h.pipeline.state.stage = PipelineStage.done
    snap = h.snapshot()
    assert snap["pipeline"]["stage"] == "done"
    assert snap["pipeline"]["deliverable_ok"] is False
    assert snap["pipeline"]["validation"]["ok"] is False
    rev = snap.get("flex_review") or {}
    ids = [b.get("id") for b in (rev.get("buttons") or [])]
    assert rev.get("active") is True
    assert rev.get("deliverable_ok") is False
    assert "good" not in ids
    assert "rebuild" in ids
    assert "Wie war" not in (rev.get("question") or "")
