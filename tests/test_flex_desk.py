"""Flex Box 1 desk: questions, routing, no execute authority."""

from __future__ import annotations

import pytest

from gnom_hub.core.event_bus import EventBus
from gnom_hub.flex_desk import FlexDesk, parse_flex_ask, plain_german, sanitize_box1_text
from gnom_hub.pipeline import Pipeline, PipelineStage


def test_worker_question_appears_in_box1_snapshot():
    desk = FlexDesk(job_id="job-a")
    out = desk.ask(
        agent_id="worker1",
        job_id="job-a",
        task_id="html-hero",
        text="Soll die Hero-Zeile kürzer sein?",
        component="yes_no",
    )
    assert out["ok"] is True
    snap = desk.snapshot()
    assert snap["owner"] == "flex"
    assert snap["title"] == "Rückfragen und Entscheidungen"
    assert len(snap["questions"]) == 1
    q = snap["questions"][0]
    assert q["agent_id"] == "worker1"
    assert q["task_id"] == "html-hero"
    assert q["job_id"] == "job-a"
    assert q["question_id"] == out["question_id"]
    assert "Kopfbereich" in q["text"]


def test_answer_routes_only_to_asking_worker():
    desk = FlexDesk(job_id="job-a")
    q1 = desk.ask(agent_id="worker1", job_id="job-a", task_id="t1", text="Farbe dunkler?")
    q2 = desk.ask(agent_id="worker2", job_id="job-a", task_id="t2", text="Footer mit Impressum?")
    r = desk.answer(q1["question_id"], "Ja", job_id="job-a")
    assert r["ok"] is True
    assert r["agent_id"] == "worker1"
    assert r["task_id"] == "t1"
    assert r["value"] == "Ja"
    open_ids = {q.agent_id: q.question_id for q in desk.open_questions()}
    assert "worker1" not in open_ids
    assert open_ids["worker2"] == q2["question_id"]


def test_stale_question_id_is_rejected():
    desk = FlexDesk(job_id="job-a")
    q = desk.ask(agent_id="worker1", job_id="job-a", task_id="t1", text="Kurz bestätigen?")
    desk.answer(q["question_id"], "Ja", job_id="job-a")
    again = desk.answer(q["question_id"], "Nein", job_id="job-a")
    assert again["ok"] is False
    assert again["error"] == "stale_question"
    missing = desk.answer("q-does-not-exist", "Ja", job_id="job-a")
    assert missing["ok"] is False
    assert missing["error"] == "stale_question"


def test_two_workers_questions_stay_separated():
    desk = FlexDesk(job_id="job-a")
    a = desk.ask(agent_id="worker1", job_id="job-a", task_id="hero", text="Hero mit Foto?")
    b = desk.ask(agent_id="worker2", job_id="job-a", task_id="footer", text="Hero mit Foto?")
    assert a["question_id"] != b["question_id"]
    ids = {q.agent_id: q.task_id for q in desk.open_questions()}
    assert ids["worker1"] == "hero"
    assert ids["worker2"] == "footer"


def test_send_does_not_execute_via_flex_or_build_language():
    bus = EventBus()
    pipe = Pipeline(bus)
    st = pipe.brainstorm_turn("Build a landing page for Bean Shop. Full HTML with hero and footer.")
    assert st.stage == PipelineStage.brainstorm
    assert not st.worker_results
    assert st.mode != "execute" or st.stage == PipelineStage.brainstorm
    qs = pipe.flex_desk.open_questions()
    assert any(q.component == "start_work" for q in qs)
    start = next(q for q in qs if q.component == "start_work")
    assert "Arbeit jetzt starten" in start.text


def test_start_work_yes_calls_hub_execute_not_flex(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.config import paths
    from gnom_hub.hub import Hub

    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    hub = Hub()
    try:
        hub.pipeline.brainstorm_turn(
            "Build a landing page for Bean Shop. Full HTML with hero and footer."
        )
        start = next(
            q for q in hub.pipeline.flex_desk.open_questions() if q.component == "start_work"
        )
        called: list[str] = []
        hub.execute_sync = lambda: called.append("sync") or {"ok": True}  # type: ignore[method-assign]
        hub.execute_async = lambda: called.append("async") or {"ok": True}  # type: ignore[method-assign]
        out = hub.flex_answer(start.question_id, "Ja", job_id=start.job_id, sync=True)
        assert called == ["sync"]
        assert out["flex_answer"]["wants_start_work"] is True
        with pytest.raises(PermissionError):
            hub.pipeline.flex_desk.start_execute()
    finally:
        hub_mod._HUB = None


def test_flex_cannot_mark_success_or_start_execute():
    desk = FlexDesk(job_id="job-a")
    with pytest.raises(PermissionError):
        desk.mark_done()
    with pytest.raises(PermissionError):
        desk.start_execute()
    with pytest.raises(PermissionError):
        desk.set_god_mode(True)
    with pytest.raises(PermissionError):
        desk.grant_tools()
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn("Ideen zu einer Checklisten-App, nur Brainstorm bitte")
    assert pipe.state.stage == PipelineStage.brainstorm
    assert pipe.state.stage != PipelineStage.done


def test_worker_html_and_javascript_are_not_kept_as_markup():
    desk = FlexDesk(job_id="job-a")
    raw = (
        '<script>alert(1)</script><img src=x onerror="steal()">'
        "Bitte Farbe wählen javascript:void(0)"
    )
    out = desk.ask(
        agent_id="worker1",
        job_id="job-a",
        task_id="t1",
        text=raw,
        component="unsafe_html",
    )
    assert out["ok"] is True
    assert out["component"] == "text"
    assert "<" not in out["text"]
    assert "script" not in out["text"].lower()
    assert "javascript:" not in out["text"].lower()
    assert "onerror" not in out["text"].lower()
    snap_text = desk.snapshot()["questions"][0]["text"]
    assert "<script" not in snap_text
    assert sanitize_box1_text("<b>Ja</b>") == "Ja"


def test_reload_keeps_question_bound_to_job():
    desk = FlexDesk(job_id="job-a")
    q = desk.ask(
        agent_id="worker3",
        job_id="job-a",
        task_id="nav",
        text="Mobile Menü oben halten?",
        component="yes_no",
    )
    payload = desk.to_list()
    restored = FlexDesk.from_list(payload, job_id="job-a")
    snap = restored.snapshot()
    assert snap["job_id"] == "job-a"
    assert len(snap["questions"]) == 1
    rq = snap["questions"][0]
    assert rq["question_id"] == q["question_id"]
    assert rq["agent_id"] == "worker3"
    assert rq["task_id"] == "nav"
    assert rq["job_id"] == "job-a"
    bad = restored.answer(q["question_id"], "Ja", job_id="job-OTHER")
    assert bad["ok"] is False
    assert bad["error"] == "job_mismatch"


def test_plain_german_maps_hero_not_html():
    out = plain_german("Soll der Hero mit CTA bleiben?")
    assert "Kopfbereich" in out
    assert "Button zum Handeln" in out
    assert "<" not in out


def test_parse_flex_ask_block():
    parsed = parse_flex_ask("FLEX_ASK yes_no task=hero\nSoll der Kopfbereich kürzer sein?")
    assert parsed is not None
    assert parsed["component"] == "yes_no"
    assert parsed["task_id"] == "hero"
    assert "Kopfbereich" in parsed["text"]
    assert parse_flex_ask("<html>page</html>") is None


def test_coordinator_clarify_appears_in_flex_desk():
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn("Maybe build something cool with dark mode, not sure yet")
    st = pipe.execute()
    assert st.stage == PipelineStage.clarify
    qs = [q for q in pipe.flex_desk.open_questions() if q.agent_id == "coordinator"]
    assert qs
    assert qs[0].component == "single_select"
    assert qs[0].options


def test_worker_flex_ask_pauses_and_routes_answer():
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn("Ideen zu einer Checklisten-App, nur Brainstorm bitte")
    pipe._clarified_once = True
    pipe.worker1.run = (  # type: ignore[method-assign]
        lambda *a, **k: "FLEX_ASK yes_no task=hero\nSoll der Hero kürzer sein?"
    )
    st = pipe.execute()
    assert st.stage == PipelineStage.clarify
    qs = [q for q in pipe.flex_desk.open_questions() if q.agent_id == "worker1"]
    assert len(qs) == 1
    assert "Kopfbereich" in qs[0].text
    assert not any("FLEX_ASK" in str(r) for r in (st.worker_results or []))
    pipe.state.memory_context = "User: always enable dark theme\n"
    r = pipe.apply_flex_answer(
        {
            "agent_id": "worker1",
            "task_id": "hero",
            "question_id": qs[0].question_id,
            "value": "Ja",
        }
    )
    assert r is None
    joined = "\n".join(pipe.state.distilled_requirements)
    assert "User→worker1" in joined
    assert "worker2" not in joined.split("User→")[-1] if "User→" in joined else True
    assert "Flex-Erinnerung für worker1" in joined
    assert "dark theme" in joined.lower() or "dunkles" in joined.lower()


def test_restore_flex_from_pipeline_state():
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.flex_desk.bind_job("job-reload")
    q = pipe.flex_desk.ask(
        agent_id="worker2",
        job_id="job-reload",
        task_id="nav",
        text="Menü links lassen?",
    )
    pipe._sync_flex_state()
    other = Pipeline(EventBus())
    other._state.flex_job_id = pipe.state.flex_job_id
    other._state.flex_questions = list(pipe.state.flex_questions)
    other.restore_flex_from_state()
    got = other.flex_desk.open_questions()
    assert len(got) == 1
    assert got[0].question_id == q["question_id"]
    assert got[0].job_id == "job-reload"
    assert got[0].agent_id == "worker2"


def test_remaining_workers_continue_after_flex_ask():
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn("Ideen zu einer Checklisten-App, nur Brainstorm bitte")
    pipe._clarified_once = True
    pipe.coordinator.plan = lambda *_a, **_k: [  # type: ignore[method-assign]
        ("worker1", "alpha"),
        ("worker2", "beta"),
    ]
    pipe.worker1.run = (  # type: ignore[method-assign]
        lambda *_a, **_k: "FLEX_ASK yes_no task=hero\nSoll der Kopfbereich kürzer sein?"
    )
    seen: list[str] = []

    def w2(*_a: object, **_k: object) -> str:
        seen.append("w2")
        return "Worker2 Ergebnis " + ("ok " * 20)

    pipe.worker2.run = w2  # type: ignore[method-assign]
    st = pipe.execute()
    assert st.stage == PipelineStage.clarify
    assert not any(o.get("worker") == "worker2" for o in (st.worker_outputs or []))
    assert st.flex_wait_remaining
    pipe.continue_after_flex_ask()
    assert "w2" in seen
    assert any(o.get("worker") == "worker2" for o in (pipe.state.worker_outputs or []))


def test_session_pack_flex_questions_roundtrip(tmp_path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.config import paths
    from gnom_hub.hub import Hub

    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    hub = Hub()
    try:
        hub.pipeline.flex_desk.bind_job("job-pack")
        asked = hub.pipeline.flex_desk.ask(
            agent_id="worker1",
            job_id="job-pack",
            task_id="hero",
            text="Soll der Kopfbereich kürzer sein?",
        )
        hub.pipeline._sync_flex_state()
        hub.pipeline._state.flex_wait_agent = "worker1"
        hub.pipeline._state.flex_wait_task = "hero"
        hub.pipeline._state.flex_wait_remaining = [{"worker": "worker2", "task": "beta"}]
        pack = hub.export_session_pack(label="flex-pack")
        body = pack.get("pack") if isinstance(pack.get("pack"), dict) else pack
        pipe = body["pipeline"]
        assert pipe["flex_job_id"] == "job-pack"
        assert pipe["flex_wait_agent"] == "worker1"
        assert pipe["flex_wait_task"] == "hero"
        assert pipe["flex_wait_remaining"][0]["worker"] == "worker2"
        assert pipe["flex_questions"][0]["question_id"] == asked["question_id"]
        hub.pipeline.flex_desk = FlexDesk()
        hub.pipeline._state.flex_questions = []
        hub.pipeline._state.flex_wait_agent = ""
        hub.import_session_pack(body)
        assert hub.pipeline.state.flex_job_id == "job-pack"
        assert hub.pipeline.state.flex_wait_agent == "worker1"
        qs = hub.pipeline.flex_desk.open_questions()
        assert len(qs) == 1
        assert qs[0].question_id == asked["question_id"]
        assert qs[0].agent_id == "worker1"
        assert "Kopfbereich" in qs[0].text
    finally:
        hub_mod._HUB = None


def test_nudge_posts_box1_nachbesserung():
    bus = EventBus()
    pipe = Pipeline(bus)
    pipe.brainstorm_turn("Ideen zu einer Checklisten-App, nur Brainstorm bitte")
    pipe._clarified_once = True
    pipe.flex.nudge_gaps = lambda *_a, **_k: [  # type: ignore[method-assign]
        {"agent": "worker1", "message": "dunkles Erscheinungsbild fehlt", "reason": "flex_gap"}
    ]
    pipe.execute()
    qs = [q for q in pipe.flex_desk.open_questions() if q.task_id == "nachbesserung"]
    assert qs
    assert "fehlt" in qs[0].text.lower()
