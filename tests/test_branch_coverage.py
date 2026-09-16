"""Hit untested branches in jobs, errors, pipeline API, export, skills."""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app
from gnom_hub.core.errors import (
    ErrorCode,
    classify_generic_exception,
    classify_tool_exception,
    envelope_http,
    error_envelope,
    http_status_for_code,
    is_retryable_envelope,
    sanitize_message,
)
from gnom_hub.core.event_bus import EventBus
from gnom_hub.export_ops import _extract_html_document
from gnom_hub.jobs import JobsMixin, _job_timeout_s
from gnom_hub.pipeline.models import PipelineStage, PipelineState
from gnom_hub.pipeline.pipeline import Pipeline
from gnom_hub.pipeline_api import PipelineApiMixin
from gnom_hub.plugins.retry import ToolFailed, ToolRetry


class FakeJobs(JobsMixin):
    def __init__(self) -> None:
        self._jobs: dict = {}
        self._active_job_id = None
        self.last_error = None
        self.plan_mode = "default"
        self.bus = EventBus()
        self.pipeline = SimpleNamespace(
            state=SimpleNamespace(error=None, stage=SimpleNamespace(value="brainstorm")),
            cancel_check=None,
            plan_mode="default",
            start=lambda _t: None,
            chat_turn=lambda _t, target="brainstorm": None,
            execute=lambda: None,
            rerun_worker=lambda _w: None,
        )
        self.memory = SimpleNamespace(set_query_hint=lambda _t: None)
        self._lock = threading.Lock()
        self.traces: list = []

    def _pipeline_lock_obj(self):
        return self._lock

    def snapshot(self):
        return {"ok": True}

    def _capture_workspace_outputs(self):
        return None

    def _remember_execute_export(self):
        return None

    def maybe_auto_pack(self):
        return None

    def _append_trace(self, name: str, data=None):
        self.traces.append((name, data))


class FakeApi(PipelineApiMixin):
    def __init__(self) -> None:
        self.last_error = None
        self.plan_mode = "default"
        self._lock = threading.Lock()
        self.pipeline = SimpleNamespace(
            flex_desk=None,
            state=PipelineState(),
            answer_clarify=lambda _o: None,
            apply_flex_answer=None,
            apply_memory_keep=None,
            apply_td_handoff=None,
            continue_after_flex_ask=None,
            _sync_flex_state=None,
            resume_deferred_clarify=None,
        )

    def _pipeline_lock_obj(self):
        return self._lock

    def snapshot(self):
        return {"stage": self.pipeline.state.stage.value}

    def _append_trace(self, *_a, **_k):
        return None


def test_job_timeout_env_branches(monkeypatch):
    monkeypatch.setenv("GNOM_JOB_TIMEOUT_S", "nope")
    assert _job_timeout_s() == 600.0
    monkeypatch.setenv("GNOM_JOB_TIMEOUT_S", "5")
    assert _job_timeout_s() == 30.0
    monkeypatch.setenv("GNOM_JOB_TIMEOUT_S", "99999")
    assert _job_timeout_s() == 3600.0
    monkeypatch.setenv("GNOM_JOB_TIMEOUT_S", "120")
    assert _job_timeout_s() == 120.0


def test_find_busy_job_status_branches():
    h = FakeJobs()
    assert h._find_busy_job() is None
    h._jobs["x"] = "nope"
    h._jobs["fin"] = {"id": "fin", "finished": True, "status": "running"}
    h._jobs["can"] = {"id": "can", "status": "cancelled", "finished": False}
    assert h._find_busy_job() is None
    h._jobs["q"] = {"id": "q", "status": "queued"}
    assert h._find_busy_job()["id"] == "q"
    h2 = FakeJobs()
    h2._active_job_id = "a"
    h2._jobs["a"] = {"id": "a", "status": "cancelling", "finished": False}
    assert h2._find_busy_job()["id"] == "a"


def test_start_job_busy_and_get_job():
    h = FakeJobs()
    h._jobs["b"] = {"id": "b", "status": "running", "finished": False, "name": "execute"}
    out = h._start_job("execute", lambda: None)
    assert out["busy"] is True
    assert out["busy_job_id"] == "b"
    assert h.get_job("missing") is None
    h._active_job_id = "b"
    got = h.get_job("b")
    assert got is not None
    assert got["id"] == "b"
    assert got["snapshot"] is None or isinstance(got["snapshot"], dict)


def test_cancel_job_unknown_finished_and_idle_busy():
    h = FakeJobs()
    with pytest.raises(FileNotFoundError):
        h.cancel_job("nope")
    h._jobs["done"] = {
        "id": "done",
        "status": "done",
        "finished": True,
        "stage": "done",
        "error": None,
        "name": "execute",
    }
    fin = h.cancel_job("done")
    assert fin["finished"] is True
    idle = h.cancel_busy_job()
    assert idle["busy"] is False
    h._jobs["run"] = {
        "id": "run",
        "status": "running",
        "finished": False,
        "stage": "running",
        "name": "execute",
        "error": None,
    }
    busy = h.cancel_busy_job()
    assert busy["busy"] is True
    assert h._jobs["run"]["cancel"] is True


def test_chat_async_rejects_bad_target():
    h = FakeJobs()
    with pytest.raises(ValueError, match="invalid send target"):
        h.chat_async("hi", target="not-an-agent")


def test_error_http_and_classify_branches():
    assert http_status_for_code("not_a_code") == 500
    assert http_status_for_code(ErrorCode.RATE_LIMIT) == 429
    env = error_envelope(
        message="x",
        code="validation",
        layer="validation",
        detail={"n": 1},
        extra={"tool": "echo", "ok": False},
    )
    assert env["detail"] == {"n": 1}
    assert env["tool"] == "echo"
    assert env["ok"] is False
    assert envelope_http(env)[0] == 422
    assert is_retryable_envelope(None) is False
    assert is_retryable_envelope({"retryable": True}) is True
    assert sanitize_message("sk-short") == "sk-short"
    assert sanitize_message("") == ""
    assert sanitize_message("a" * 50, limit=10).endswith("…")

    bad = ToolFailed("x", code="not-a-real-code")
    assert classify_tool_exception(bad, tool_name="t")["code"] == "tool_failed"
    retry_ex = ToolFailed("exceeded retries for t")
    assert classify_tool_exception(retry_ex, tool_name="t")["code"] == "tool_retry_exhausted"
    tr = classify_tool_exception(ToolRetry("again"), tool_name="t")
    assert tr["retryable"] is True
    assert classify_tool_exception(ValueError("bad args"), tool_name="t")["code"] == "validation"
    assert classify_tool_exception(RuntimeError("boom"), tool_name="t")["code"] == "internal"

    assert classify_generic_exception(Exception("cancelled by user"))["code"] == "cancelled"
    assert classify_generic_exception(KeyError("k"))["code"] == "not_found"
    assert classify_generic_exception(TypeError("t"))["code"] == "validation"
    assert classify_generic_exception(RuntimeError("other"))["code"] == "internal"


def test_extract_html_document_branches():
    assert _extract_html_document("") is None
    assert _extract_html_document("just text") is None
    fenced = "```html\n<!DOCTYPE html><html><body>a</body></html>\n```"
    assert "<!DOCTYPE" in (_extract_html_document(fenced) or "")
    raw = "<html><body>b</body></html>"
    assert _extract_html_document("note " + raw).endswith("</html>")
    assert _extract_html_document("<!DOCTYPE html><html></html>").startswith("<!DOCTYPE")


def test_pipeline_api_missing_desk_and_restore():
    api = FakeApi()
    with pytest.raises(TypeError, match="flex desk"):
        api.flex_ask(agent_id="flex", text="?")
    with pytest.raises(TypeError, match="flex desk"):
        api.flex_answer("q1", "ja")
    with pytest.raises(TypeError, match="resume deferred"):
        api.resume_deferred_clarify()
    with pytest.raises(ValueError, match="nothing to re-execute"):
        api.restore_for_reexecute(user_text="", brainstorm_notes="")
    snap = api.restore_for_reexecute(
        user_text="mach seite",
        brainstorm_notes="",
        brainstorm_turns=[
            {"role": "user", "text": "mach seite"},
            {"role": "brainstorm", "text": "ok"},
            {"role": "user", "text": ""},
        ],
    )
    assert "stage" in snap
    snap2 = api.restore_for_reexecute(
        user_text="",
        brainstorm_notes="bereits notizen",
        brainstorm_turns=[{"role": "user", "text": "nochmal"}],
    )
    assert "stage" in snap2


def test_legacy_pipeline_empty_and_clarify_guard():
    pipe = Pipeline(EventBus())
    with pytest.raises(ValueError, match="No pending"):
        pipe.answer_clarify("ja")
    st = pipe.start("   ")
    assert st.error
    assert st.stage in (PipelineStage.error, PipelineStage.idle, PipelineStage.brainstorm)


def test_skills_enable_unknown_and_install_bad(tmp_path, monkeypatch):
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/skills/missing-skill/enable", json={"enabled": False})
        assert r.status_code in (404, 501)
        r2 = c.post("/api/skills/install", json={"path": str(tmp_path / "no-such-pack")})
        assert r2.status_code in (400, 501)
    hub_mod._HUB = None
