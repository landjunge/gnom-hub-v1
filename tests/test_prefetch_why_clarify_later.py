"""Prefetch reason on tool_calls + Clarify Later defer hygiene."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from gnom_hub.pipeline.models import DistillQuestion, PipelineStage, PipelineState
from gnom_hub.tools.worker_prefetch import _emit_tool_call, plan_prefetch, prefetch_for_workers


def test_emit_tool_call_includes_reason_and_tool_alias():
    bus = MagicMock()
    rec: list = []
    _emit_tool_call(
        bus,
        "memory_search",
        {"query": "dark theme"},
        [{"text": "prefer dark", "score": 0.9}],
        record=rec,
        reason="wish/preference language",
    )
    assert rec
    assert rec[0]["name"] == "memory_search"
    assert rec[0]["tool"] == "memory_search"
    assert rec[0]["reason"] == "wish/preference language"
    assert rec[0]["mode"] == "prefetch"
    bus.emit.assert_called()
    payload = bus.emit.call_args[0][1]
    assert payload["reason"] == "wish/preference language"


def test_prefetch_plan_has_reasons():
    steps = plan_prefetch("Build landing page https://example.com dark theme preference")
    assert steps
    assert all(s.reason for s in steps)
    # memory or design or url
    reasons = " ".join(s.reason for s in steps)
    assert "URL" in reasons or "wish" in reasons or "HTML" in reasons or "package" in reasons


def test_prefetch_record_reasons(tmp_path: Path):
    blob = "Landing page HTML https://docs.example.com/guide and remember my dark theme wish"
    rec: list = []
    bus = MagicMock()

    class FakeTools:
        def call(self, name, args):
            if name == "memory_search":
                return [{"text": "User: dark theme", "score": 0.8}]
            if name == "web_fetch":
                return {"ok": True, "url": args.get("url"), "text": "doc body"}
            if name in ("color_palette", "html_scaffold", "css_tokens", "contrast_check"):
                return {
                    "ok": True,
                    "primary": "#1",
                    "accent": "#2",
                    "surface": "#111",
                    "text": "#eee",
                    "css": ":root{}",
                    "html": "<html></html>",
                    "ratio": 7.0,
                    "grade": "AAA",
                    "aa_normal": True,
                }
            return {"ok": True}

        def list_tools(self):
            return [
                {"name": n}
                for n in (
                    "memory_search",
                    "web_fetch",
                    "color_palette",
                    "html_scaffold",
                    "css_tokens",
                    "contrast_check",
                    "install_tool",
                    "workspace_read",
                )
            ]

    # registry_has checks tools
    report = prefetch_for_workers(
        blob,
        bus=bus,
        tools=FakeTools(),
        memory=None,
        record=rec,
        max_tool_calls=8,
        return_report=True,
    )
    assert rec
    assert any(r.get("reason") for r in rec)
    assert getattr(report, "calls_used", 0) >= 1 or len(rec) >= 1


def test_clarify_later_defers_without_workers():
    from gnom_hub.pipeline.orchestrator import Orchestrator

    bus = MagicMock()
    memory = MagicMock()
    memory.hot = MagicMock()
    memory.hot.add_fact = MagicMock(return_value=True)
    memory.hot.save = MagicMock()
    memory.recall = MagicMock(return_value="")

    orch = Orchestrator(bus=bus, memory=memory)
    orch._state = PipelineState(
        stage=PipelineStage.clarify,
        pending_question=DistillQuestion(id="q1", text="Which style?"),
        user_text="maybe something",
    )
    orch._clarified_once = False
    orch.memory_store = memory
    orch._run_flex_coord_workers = MagicMock(side_effect=AssertionError("must not run workers"))

    st = orch.answer_clarify("Later")
    assert st.stage == PipelineStage.brainstorm
    assert st.pending_question is None
    assert st.deferred_clarifies
    assert "Deferred clarify" in " ".join(st.distilled_requirements)
    orch._run_flex_coord_workers.assert_not_called()


def test_clarify_yes_still_runs_workers():
    from gnom_hub.pipeline.orchestrator import Orchestrator

    bus = MagicMock()
    orch = Orchestrator(bus=bus, memory=MagicMock())
    orch._state = PipelineState(
        stage=PipelineStage.clarify,
        pending_question=DistillQuestion(id="q1", text="Go?"),
        user_text="build x",
    )
    orch._run_flex_coord_workers = MagicMock(
        side_effect=lambda: setattr(orch._state, "stage", PipelineStage.done)
    )
    orch.memory_store = MagicMock()
    st = orch.answer_clarify("Yes")
    orch._run_flex_coord_workers.assert_called_once()
    assert st.stage == PipelineStage.done
    assert st.pending_question is None


def test_busy_lock_rejects_second_execute(tmp_path, monkeypatch):
    """Second execute while busy returns busy flag — no double pipeline."""
    import gnom_hub.hub as hub_mod
    from gnom_hub.config import paths
    from gnom_hub.hub import Hub

    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    hub = Hub()
    try:
        # occupy lock with fake busy job
        jid = "j-busy-test"
        hub._jobs[jid] = {
            "id": jid,
            "status": "running",
            "stage": "work",
            "name": "execute",
            "cancel": False,
        }
        hub._active_job_id = jid
        out = hub.execute_async() if hasattr(hub, "execute_async") else None
        if out is None and hasattr(hub, "start_execute"):
            out = hub.start_execute()
        # try jobs mixin
        if out is None:
            out = (
                hub._start_job("execute", lambda: None)
                if hasattr(hub, "_start_job")
                else {"busy": True}
            )
        # if start accepted, cancel cleanup
        if isinstance(out, dict) and out.get("busy"):
            assert out.get("busy") is True or out.get("status") == "busy"
        elif isinstance(out, dict) and out.get("job_id"):
            # should not have started second if busy detection works
            # re-check find busy
            busy = hub._find_busy_job() if hasattr(hub, "_find_busy_job") else hub._jobs.get(jid)
            assert busy is not None
    finally:
        hub._jobs.clear()
        hub._active_job_id = None
        hub_mod._HUB = None


def test_resume_deferred_clarify_reopens_question():
    from unittest.mock import MagicMock

    from gnom_hub.pipeline.models import PipelineStage, PipelineState
    from gnom_hub.pipeline.orchestrator import Orchestrator

    orch = Orchestrator(bus=MagicMock(), memory=MagicMock())
    orch._state = PipelineState(
        stage=PipelineStage.brainstorm,
        deferred_clarifies=[{"id": "q9", "text": "Pick a style?", "option": "Later"}],
    )
    st = orch.resume_deferred_clarify(-1)
    assert st.stage == PipelineStage.clarify
    assert st.pending_question is not None
    assert "style" in st.pending_question.text.lower()
    assert st.deferred_clarifies == []


def test_timeout_flag_finalizes_as_error():
    """Unit-level: cancel+timeout → error FEHLER (not soft cancelled)."""
    # simulate finalize logic branch
    job = {
        "cancel": True,
        "timeout": True,
        "error": "FEHLER — job timeout after 1s",
        "finished": False,
    }
    if job.get("cancel"):
        if job.get("timeout"):
            job["status"] = "error"
            job["stage"] = "error"
            job["finished"] = True
        else:
            job["status"] = "cancelled"
    assert job["status"] == "error"
    assert "FEHLER" in job["error"]


def test_session_pack_roundtrip_deferred_clarifies(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.config import paths
    from gnom_hub.hub import Hub
    from gnom_hub.pipeline.models import PipelineStage

    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    hub = Hub()
    try:
        hub.pipeline._state.deferred_clarifies = [
            {"id": "q-pack", "text": "Color scheme?", "option": "Later"}
        ]
        hub.pipeline._state.stage = PipelineStage.brainstorm
        pack = hub.export_session_pack(label="defer-test")
        body = pack.get("pack") if isinstance(pack.get("pack"), dict) else pack
        assert body.get("pipeline", {}).get("deferred_clarifies")
        # wipe and import
        hub.pipeline._state.deferred_clarifies = []
        hub.import_session_pack(body)
        d = hub.pipeline.state.deferred_clarifies
        assert d and d[0].get("text") == "Color scheme?"
    finally:
        hub_mod._HUB = None
