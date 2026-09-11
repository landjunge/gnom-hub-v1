"""Execute click must close the Box 1 start_work question.

#btn-execute / Hub execute() is the same gate as Ja on start_work. Leaving the
question open lets a later Ja fire Execute a second time.
"""

from __future__ import annotations

from gnom_hub.config import paths
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline import Pipeline

_BUILD = "Build a landing page for Bean Shop. Full HTML with hero and footer."


def _open_start_work(pipe):
    return [q for q in pipe.flex_desk.open_questions() if q.component == "start_work"]


def test_execute_closes_open_start_work_question():
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn(_BUILD)
    qs = _open_start_work(pipe)
    assert qs, "brainstorm must offer start_work before Execute"
    qid = qs[0].question_id
    job_id = qs[0].job_id

    pipe.execute()

    assert _open_start_work(pipe) == []
    stored = pipe.flex_desk._questions.get(qid)
    assert stored is not None
    assert stored.status in ("answered", "stale")
    again = pipe.flex_desk.answer(qid, "Ja", job_id=job_id)
    assert again["ok"] is False
    assert again["error"] == "stale_question"


def test_flex_answer_after_execute_does_not_execute_again(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.hub import Hub

    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    hub = Hub()
    try:
        hub.pipeline.brainstorm_turn(_BUILD)
        start = next(
            q for q in hub.pipeline.flex_desk.open_questions() if q.component == "start_work"
        )
        hub.pipeline.execute()
        called: list[str] = []
        hub.execute_sync = lambda: called.append("sync") or {"ok": True}  # type: ignore[method-assign]
        hub.execute_async = (  # type: ignore[method-assign]
            lambda: called.append("async") or {"ok": True}
        )
        out = hub.flex_answer(start.question_id, "Ja", job_id=start.job_id, sync=True)
        assert called == []
        assert out["flex_answer"]["ok"] is False
        assert out["flex_answer"]["error"] == "stale_question"
        assert _open_start_work(hub.pipeline) == []
    finally:
        hub_mod._HUB = None
