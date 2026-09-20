"""Stage done with FEHLER must not look like a successful deliverable."""

from pathlib import Path
from types import SimpleNamespace

from gnom_hub.pipeline.dod_gate import run_dod_check
from gnom_hub.snapshot_ops import _deliverable_ok

_REPO = Path(__file__).resolve().parents[1]


def _fehler_body(*, reason: str) -> str:
    return (
        "Worker 1 FEHLER - kein Deliverable\n"
        f"{reason}\n"
        "Kein Stub-Ersatz. Key pruefen, Budget pruefen, dann erneut ausfuehren.\n"
        + ("Hinweis: Worker liefert erst mit tigem Provider. " * 8)
    )


def test_deliverable_ok_false_on_worker_fehler():
    body = _fehler_body(reason="LLM-Fehler (worker1): tollgate package not installed")
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


def test_deliverable_ok_false_on_budget_fail_without_deliverable_word():
    body = (
        "Session-Budget überschritten (GNOM_MAX_BUDGET_USD).\n"
        "Budget exceeded: spent $1.0000 / max $0.5000\n"
        + ("padding-to-pass-length-threshold-of-four-hundred-chars. " * 8)
    )
    assert len(body) >= 400
    assert "Deliverable" not in body
    st = SimpleNamespace(
        worker_outputs=[{"worker": "worker1", "result": body}],
        worker_results=[body],
    )
    assert _deliverable_ok(st) is False


def test_deliverable_ok_false_on_tollgate_missing_without_deliverable_word():
    body = (
        "LLM-Fehler (worker1): tollgate package not installed\n"
        "Fix: pip install tollgate or set GNOM_TOLLGATE_LLM=0\n"
        + ("padding-to-pass-length-threshold-of-four-hundred-chars. " * 8)
    )
    assert len(body) >= 400
    assert "Deliverable" not in body
    st = SimpleNamespace(
        worker_outputs=[{"worker": "worker1", "result": body}],
        worker_results=[body],
    )
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


def test_finish_marks_fehler_not_success_on_tollgate_body():
    from gnom_hub.hub import Hub
    from gnom_hub.pipeline.models import PipelineStage

    h = Hub()
    body = _fehler_body(reason="LLM-Fehler (worker1): tollgate package not installed")
    gate = run_dod_check(body, user_text="Build a landing page HTML", task="landing HTML")
    st = h.pipeline.state
    st.user_text = "Build a landing page HTML"
    st.worker_outputs = [
        {"worker": "worker1", "name": "Worker 1", "result": body, "validation": gate}
    ]
    st.worker_results = [body]
    h.pipeline._finish()
    assert st.stage == PipelineStage.done
    assert st.result_status == "FEHLER"
    assert _deliverable_ok(st) is False
    snap = h.snapshot()
    assert snap["pipeline"]["result_status"] == "FEHLER"
    assert snap["pipeline"]["deliverable_ok"] is False
    rev = snap.get("flex_review") or {}
    assert "Wie war" not in (rev.get("question") or "")
    assert "good" not in [b.get("id") for b in (rev.get("buttons") or [])]
    desk = h.pipeline.flex_desk
    texts = []
    for q in desk.open_questions():
        texts.append(q.text if hasattr(q, "text") else str(q))
    assert not any("Passt das" in t for t in texts)


def test_finish_keeps_success_status_on_real_html():
    from gnom_hub.hub import Hub

    html = (
        "<!DOCTYPE html><html><head><title>Bean</title></head>"
        "<body>"
        + ("<p>coffee shop landing with hero footer and cards.</p>" * 20)
        + '<button onclick="alert(1)">ok</button></body></html>'
    )
    gate = run_dod_check(
        html,
        user_text="Build a landing page HTML for Bean & Bloom coffee",
        task="landing HTML",
        requirements=["User: hero", "User: footer"],
    )
    h = Hub()
    st = h.pipeline.state
    st.user_text = "Build a landing page HTML for Bean & Bloom coffee"
    st.worker_outputs = [{"worker": "worker1", "result": html, "validation": gate}]
    st.worker_results = [html]
    h.pipeline._finish()
    assert _deliverable_ok(st) is True
    assert st.result_status in ("GELIEFERT", "UNGEPRÜFT")
    if gate.get("ok"):
        assert st.result_status == "GELIEFERT"
    snap = h.snapshot()
    assert snap["pipeline"]["deliverable_ok"] is True
    rev = snap.get("flex_review") or {}
    assert rev.get("deliverable_ok") is True


def test_ui_success_toasts_are_gated_on_deliverable_ok():
    src = (_REPO / "src/gnom_hub/ui/static/parts/08-chat-jobs.js").read_text(encoding="utf-8")
    assert "snap.pipeline.deliverable_ok" in src
    for toast in (
        'toast("Umgesetzt · Box 3", "ok")',
        'toast("Fertig · " + formatDuration(dur), "ok")',
        'toast(wid + " re-run done", "ok")',
        'toast("Nochmal fertig", "ok")',
    ):
        pos = src.find(toast)
        assert pos != -1, toast
        gate = src.rfind("okDeliverable", 0, pos)
        assert gate != -1, toast
        assert pos - gate < 900, toast

    speech = (_REPO / "src/gnom_hub/ui/static/parts/02-speech.js").read_text(encoding="utf-8")
    assert "p.deliverable_ok === true" in speech
    core = (_REPO / "src/gnom_hub/ui/static/parts/00-core.js").read_text(encoding="utf-8")
    assert "pipe.deliverable_ok === true" in core
    assert 'result === "UNGEPRÜFT" || result)' not in core
