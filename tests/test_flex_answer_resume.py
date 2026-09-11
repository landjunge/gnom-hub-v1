"""Hub.flex_answer after a worker FLEX_ASK must resume the plan, not mark done."""

from __future__ import annotations

import pytest

from gnom_hub.pipeline.models import PipelineStage

_USER = "Ideen zu einer Checklisten-App, nur Brainstorm bitte"
_PLAN_W1 = "alpha-hero-plan"
_PLAN_W2 = "beta-footer-plan"
_ASK1 = "FLEX_ASK yes_no task=hero\nSoll der Kopfbereich kürzer sein?"
_ASK2 = "FLEX_ASK yes_no task=footer\nSoll die Fußzeile Impressum haben?"


def _ok(label: str) -> str:
    return f"{label} Ergebnis " + ("ok " * 20)


def _hub(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.config import paths
    from gnom_hub.hub import Hub

    monkeypatch.delenv("GNOM_WS", raising=False)
    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    return Hub()


def _wire_two_workers(hub, w1, w2) -> None:
    hub.pipeline.brainstorm_turn(_USER)
    hub.pipeline.coordinator.distill = (  # type: ignore[method-assign]
        lambda *_a, **_k: (["landing"], None)
    )
    hub.pipeline.coordinator.plan = lambda *_a, **_k: [  # type: ignore[method-assign]
        ("worker1", _PLAN_W1),
        ("worker2", _PLAN_W2),
    ]
    hub.pipeline.worker1.run = w1  # type: ignore[method-assign]
    hub.pipeline.worker2.run = w2  # type: ignore[method-assign]
    hub.pipeline.flex.nudge_gaps = lambda *_a, **_k: []  # type: ignore[method-assign]


def test_flex_answer_reruns_asker_with_plan_task_then_remaining(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod

    hub = _hub(tmp_path, monkeypatch)
    try:
        w1_calls: list[tuple[str, str]] = []
        w1_n = {"n": 0}
        done_before_w2: list[bool] = []

        def w1(task: str, user_text: str, *_a: object, **_k: object) -> str:
            w1_calls.append((task, user_text))
            w1_n["n"] += 1
            if w1_n["n"] == 1:
                return _ASK1
            return _ok("Worker1")

        def w2(task: str, user_text: str, *_a: object, **_k: object) -> str:
            done_before_w2.append(hub.pipeline.state.stage == PipelineStage.done)
            assert "beta-footer-plan" in task
            return _ok("Worker2")

        _wire_two_workers(hub, w1, w2)
        done_events: list[object] = []
        hub.pipeline.bus.on("pipeline.done", lambda d: done_events.append(d))

        st = hub.pipeline.execute()
        assert st.stage == PipelineStage.clarify
        remaining = list(st.flex_wait_remaining or [])
        assert remaining
        assert remaining[0]["worker"] == "worker1"
        assert remaining[0]["task"] == _PLAN_W1
        assert st.flex_wait_task == _PLAN_W1
        assert not any(o.get("worker") == "worker2" for o in (st.worker_outputs or []))

        qs = [q for q in hub.pipeline.flex_desk.open_questions() if q.agent_id == "worker1"]
        assert len(qs) == 1

        with pytest.raises(PermissionError):
            hub.pipeline.flex_desk.start_execute()

        out = hub.flex_answer(qs[0].question_id, "Ja", job_id=qs[0].job_id, sync=True)
        assert out.get("flex_answer", {}).get("ok") is True

        assert w1_n["n"] == 2
        resume_task, resume_user = w1_calls[1]
        assert _PLAN_W1 in resume_task
        assert resume_task != resume_user
        assert resume_user == hub.pipeline.state.user_text
        assert resume_task.strip().splitlines()[0] != "hero"

        workers = [o.get("worker") for o in (hub.pipeline.state.worker_outputs or [])]
        assert "worker1" in workers
        assert "worker2" in workers
        assert hub.pipeline.state.stage == PipelineStage.done
        assert done_before_w2 == [False]
        assert done_events
    finally:
        hub_mod._HUB = None


def test_flex_answer_second_flex_ask_still_pauses(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod

    hub = _hub(tmp_path, monkeypatch)
    try:
        w1_n = {"n": 0}

        def w1(task: str, *_a: object, **_k: object) -> str:
            w1_n["n"] += 1
            if w1_n["n"] == 1:
                return _ASK1
            assert _PLAN_W1 in task
            return _ok("Worker1")

        def w2(*_a: object, **_k: object) -> str:
            return _ASK2

        _wire_two_workers(hub, w1, w2)
        hub.pipeline.execute()
        qs = [q for q in hub.pipeline.flex_desk.open_questions() if q.agent_id == "worker1"]
        hub.flex_answer(qs[0].question_id, "Ja", job_id=qs[0].job_id, sync=True)

        st = hub.pipeline.state
        assert st.stage == PipelineStage.clarify
        assert st.stage != PipelineStage.done
        assert st.flex_wait_agent == "worker2"
        assert st.flex_wait_task == _PLAN_W2
        rem = list(st.flex_wait_remaining or [])
        assert rem
        assert rem[0]["worker"] == "worker2"
        assert rem[0]["task"] == _PLAN_W2
        assert not any(o.get("worker") == "worker2" for o in (st.worker_outputs or []))
        open2 = [q for q in hub.pipeline.flex_desk.open_questions() if q.agent_id == "worker2"]
        assert len(open2) == 1
        with pytest.raises(PermissionError):
            hub.pipeline.flex_desk.start_execute()
    finally:
        hub_mod._HUB = None


def test_flex_answer_asking_worker_second_ask_pauses_before_rest(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod

    hub = _hub(tmp_path, monkeypatch)
    try:
        w2_seen: list[str] = []

        def w1(*_a: object, **_k: object) -> str:
            return _ASK1

        def w2(*_a: object, **_k: object) -> str:
            w2_seen.append("w2")
            return _ok("Worker2")

        _wire_two_workers(hub, w1, w2)
        hub.pipeline.execute()
        qs = [q for q in hub.pipeline.flex_desk.open_questions() if q.agent_id == "worker1"]
        hub.flex_answer(qs[0].question_id, "Nein", job_id=qs[0].job_id, sync=True)

        st = hub.pipeline.state
        assert st.stage == PipelineStage.clarify
        assert st.stage != PipelineStage.done
        assert st.flex_wait_agent == "worker1"
        assert st.flex_wait_task == _PLAN_W1
        rem = list(st.flex_wait_remaining or [])
        assert rem[0]["worker"] == "worker1"
        assert rem[0]["task"] == _PLAN_W1
        assert any(r.get("worker") == "worker2" for r in rem)
        assert w2_seen == []
        assert not any(o.get("worker") == "worker2" for o in (st.worker_outputs or []))
    finally:
        hub_mod._HUB = None
