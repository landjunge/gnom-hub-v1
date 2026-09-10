"""Snapshot must not expose pending_question when Flex Box 1 already shows it."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gnom_hub import hub as hub_mod
from gnom_hub.api.app import create_app
from gnom_hub.core.event_bus import EventBus
from gnom_hub.flex_desk import FlexDesk
from gnom_hub.pipeline import DistillQuestion, Pipeline, PipelineStage
from gnom_hub.snapshot_ops import SnapshotOpsMixin


class _Snap(SnapshotOpsMixin):
    def __init__(self, pipeline: object) -> None:
        self.pipeline = pipeline


def _clarify_question() -> DistillQuestion:
    return DistillQuestion(id="q-style", text="Wie soll ich vorgehen?")


def test_snapshot_nulls_pending_question_when_flex_box1_has_coordinator_clarify():
    pipe = Pipeline(EventBus())
    q = _clarify_question()
    pipe._post_coordinator_clarify(q)
    assert pipe.state.pending_question is q
    open_coord = [
        fq
        for fq in pipe.flex_desk.open_questions()
        if fq.agent_id == "coordinator" and fq.task_id == "clarify"
    ]
    assert len(open_coord) == 1

    snap = _Snap(pipe).pipeline_dict()
    assert snap["pending_question"] is None
    assert snap["stage"] == PipelineStage.clarify.value


def test_pipeline_state_keeps_pending_question_for_clarify_api():
    pipe = Pipeline(EventBus())
    q = _clarify_question()
    pipe._post_coordinator_clarify(q)
    assert pipe.state.pending_question is not None
    assert pipe.state.pending_question.id == "q-style"
    assert pipe.state.pending_question.text == q.text
    assert _Snap(pipe).pipeline_dict()["pending_question"] is None


def test_snapshot_keeps_pending_question_without_flex_clarify():
    pipe = Pipeline(EventBus())
    q = _clarify_question()
    pipe.state.pending_question = q
    pipe.state.stage = PipelineStage.clarify
    snap = _Snap(pipe).pipeline_dict()
    assert snap["pending_question"] is not None
    assert snap["pending_question"]["id"] == "q-style"
    assert snap["pending_question"]["text"] == q.text
    assert snap["pending_question"]["options"] == list(q.options)


def test_snapshot_keeps_pending_question_when_flex_only_has_worker_ask():
    pipe = Pipeline(EventBus())
    q = _clarify_question()
    pipe.state.pending_question = q
    pipe.state.stage = PipelineStage.clarify
    pipe.flex_desk.bind_job("job-a")
    pipe.flex_desk.ask(
        agent_id="worker1",
        job_id="job-a",
        task_id="hero",
        text="Soll der Kopfbereich kürzer sein?",
        component="yes_no",
    )
    snap = _Snap(pipe).pipeline_dict()
    assert snap["pending_question"] is not None
    assert snap["pending_question"]["id"] == "q-style"


def test_snapshot_keeps_pending_question_after_flex_clarify_answered():
    desk = FlexDesk(job_id="job-a")
    posted = desk.ask(
        agent_id="coordinator",
        job_id="job-a",
        task_id="clarify",
        text="Wie soll ich vorgehen?",
        component="single_select",
        options=["Schnell und einfach", "Gründlich und robust"],
    )
    desk.answer(posted["question_id"], "Schnell und einfach", job_id="job-a")
    pipe = Pipeline(EventBus())
    pipe.flex_desk = desk
    pipe.state.pending_question = _clarify_question()
    pipe.state.stage = PipelineStage.clarify
    snap = _Snap(pipe).pipeline_dict()
    assert snap["pending_question"] is not None
    assert snap["pending_question"]["id"] == "q-style"


def test_get_api_state_omits_pending_question_when_flex_box1_open(tmp_path, monkeypatch):
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as client:
        hub = hub_mod.get_hub()
        q = _clarify_question()
        hub.pipeline._post_coordinator_clarify(q)
        assert hub.pipeline.state.pending_question is not None

        r = client.get("/api/state")
        assert r.status_code == 200
        body = r.json()
        pipe = body["pipeline"]
        assert pipe["pending_question"] is None
        flex_qs = (body.get("flex_box1") or {}).get("questions") or []
        assert any(
            fq.get("agent_id") == "coordinator" and fq.get("task_id") == "clarify" for fq in flex_qs
        )

        r2 = client.post("/api/clarify?sync=1", json={"option": "Schnell und einfach"})
        assert r2.status_code == 200
        assert r2.json()["pipeline"]["stage"] == "done"
    hub_mod._HUB = None
