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


def test_execute_does_not_need_start_work_and_asks_judgment():
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn(_BUILD)
    assert _open_start_work(pipe) == []
    pipe.execute()
    assert _open_start_work(pipe) == []
    judge = [q for q in pipe.flex_desk.open_questions() if q.component == "judgment"]
    vis = pipe.flex_desk.visible_question()
    if pipe.state.worker_results:
        assert vis is not None
        assert vis.component in ("judgment", "yes_no")
        assert vis.text in (
            "Passt das?",
            "Key fehlt. In System einen echten Schlüssel eintragen, dann Arbeit starten.",
        )
        if vis.component == "judgment":
            assert judge
            assert judge[0].text == "Passt das?"


def test_flex_answer_after_execute_does_not_execute_again(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.hub import Hub

    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    hub = Hub()
    try:
        hub.pipeline.brainstorm_turn(_BUILD)
        assert _open_start_work(hub.pipeline) == []
        hub.pipeline.execute()
        called: list[str] = []
        hub.execute_sync = lambda: called.append("sync") or {"ok": True}  # type: ignore[method-assign]
        hub.execute_async = (  # type: ignore[method-assign]
            lambda: called.append("async") or {"ok": True}
        )
        judge = next(
            (q for q in hub.pipeline.flex_desk.open_questions() if q.component == "judgment"),
            None,
        )
        if judge is not None:
            out = hub.flex_answer(judge.question_id, "Gut", job_id=judge.job_id, sync=True)
            assert called == []
            assert out.get("judgment") == "Gut"
        assert _open_start_work(hub.pipeline) == []
    finally:
        hub_mod._HUB = None
