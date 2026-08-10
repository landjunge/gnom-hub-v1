"""Export pin deep-copy + plan_html_score contracts."""

from __future__ import annotations

from gnom_hub.export_ops import ExportOpsMixin
from gnom_hub.pipeline.models import PipelineStage, PipelineState


class _ExportHost(ExportOpsMixin):
    def __init__(self) -> None:
        self.pipeline = type("P", (), {})()
        self.pipeline.state = PipelineState()
        self._last_execute_export = None


def test_remember_execute_export_deep_copy_and_score():
    h = _ExportHost()
    st = h.pipeline.state
    st.stage = PipelineStage.done
    st.user_text = "Build a landing page"
    st.brainstorm_notes = "ideas"
    st.distilled_requirements = ["req-a"]
    st.worker_outputs = [
        {"worker": "worker1", "result": "<!DOCTYPE html><html></html>", "task": "page"}
    ]
    st.resolved_plan_mode = "full_page_html"
    st.plan_html_score = 6

    h._remember_execute_export()
    pin = h._last_execute_export
    assert pin is not None
    assert pin["plan_html_score"] == 6
    assert pin["resolved_plan_mode"] == "full_page_html"

    # Mutate live pipeline after pin — pin must stay stable
    st.worker_outputs[0]["result"] = "MUTATED"
    st.distilled_requirements.append("req-b")
    assert pin["worker_outputs"][0]["result"] == "<!DOCTYPE html><html></html>"
    assert pin["distilled_requirements"] == ["req-a"]


def test_build_export_last_includes_html_score():
    h = _ExportHost()
    st = h.pipeline.state
    st.stage = PipelineStage.done
    st.user_text = "landing"
    st.brainstorm_notes = "notes"
    st.worker_outputs = [{"worker": "worker1", "result": "x", "task": "t"}]
    st.resolved_plan_mode = "full_page_html"
    st.plan_html_score = 4

    exp = h.build_export_last()
    assert exp["ok"] is True
    assert "html_score=4" in exp["content"]
    assert "plan_mode=full_page_html" in exp["content"]
