"""R6.1: Memory proposes WARM; Box 1 Behalten writes, Verwerfen does not."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.core.event_bus import EventBus
from gnom_hub.flex_desk import FlexDesk
from gnom_hub.memory.facade import MemoryFacade
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.secrets import looks_like_secret
from gnom_hub.memory.warm import WarmMemory
from gnom_hub.pipeline.orchestrator import Pipeline


def test_secrets_are_detected():
    assert looks_like_secret("api_key=sk-abc")
    assert looks_like_secret("sk-1234567890abcdef")
    assert looks_like_secret("Bearer abcdefghijklmnop")
    assert not looks_like_secret("Marke ist Bean und Bloom")


def test_proposal_strips_secrets_and_reject_skips_warm(tmp_path: Path):
    bus = EventBus()
    hot = HotMemory(tmp_path, auto_load=False)
    warm = WarmMemory(tmp_path)
    pipe = Pipeline(bus, memory=MemoryFacade(hot, warm))
    pipe._offer_memory_keep(["Marke ist Bean und Bloom", "sk-SECRETKEY99xxxx"])
    assert pipe.state.memory_proposals == ["Marke ist Bean und Bloom"]
    qs = pipe.flex_desk.open_questions()
    assert len(qs) == 1
    assert qs[0].component == "memory_keep"
    assert qs[0].agent_id == "memory"
    assert "Behalten" in qs[0].options
    assert warm.all_facts() == []
    pipe.apply_memory_keep(False)
    assert pipe.state.memory_proposals == []
    assert warm.all_facts() == []


def test_behalten_writes_warm_not_execute(tmp_path: Path):
    bus = EventBus()
    hot = HotMemory(tmp_path, auto_load=False)
    warm = WarmMemory(tmp_path)
    pipe = Pipeline(bus, memory=MemoryFacade(hot, warm))
    pipe._offer_memory_keep(["Immer deutsch antworten"])
    q = pipe.flex_desk.open_questions()[0]
    out = pipe.flex_desk.answer(q.question_id, "Behalten")
    assert out["ok"] is True
    assert out["wants_start_work"] is False
    assert out["keep_memory"] is True
    pipe.apply_memory_keep(True)
    assert "Immer deutsch antworten" in warm.all_facts()
    assert pipe.state.worker_results == []


def test_verwerfen_answer_does_not_start_work(tmp_path: Path):
    bus = EventBus()
    pipe = Pipeline(
        bus, memory=MemoryFacade(HotMemory(tmp_path, auto_load=False), WarmMemory(tmp_path))
    )
    pipe._offer_memory_keep(["Marke bleibt privat"])
    q = pipe.flex_desk.open_questions()[0]
    out = pipe.flex_desk.answer(q.question_id, "Verwerfen")
    assert out["wants_start_work"] is False
    assert out["keep_memory"] is False


def test_flex_answer_behalten_via_hub(tmp_path: Path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.config import paths
    from gnom_hub.hub import Hub

    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    hub = Hub()
    try:
        hub.pipeline._offer_memory_keep(["Café heißt Bean"])
        qid = hub.pipeline.flex_desk.open_questions()[0].question_id
        before = list(hub.warm.all_facts())
        snap = hub.flex_answer(qid, "Behalten", sync=True)
        ans = snap.get("flex_answer") or {}
        assert ans.get("wants_start_work") is False
        assert "Café heißt Bean" in hub.warm.all_facts()
        assert "Café heißt Bean" not in before
    finally:
        hub_mod._HUB = None


def test_curated_event_does_not_write_warm(tmp_path: Path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.config import paths
    from gnom_hub.hub import Hub

    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    hub_mod._HUB = None
    hub = Hub()
    try:
        before = list(hub.warm.all_facts())
        hub.bus.emit("pipeline.memory_curated", {"facts": ["Silent WARM would be wrong"]})
        assert "Silent WARM would be wrong" not in hub.warm.all_facts()
        assert hub.warm.all_facts() == before
    finally:
        hub_mod._HUB = None


def test_memory_keep_component_is_registered():
    desk = FlexDesk()
    out = desk.ask(
        agent_id="memory",
        text="Memory schlägt vor, das dauerhaft zu behalten:\n• x\nSoll genau das nach WARM?",
        component="memory_keep",
    )
    assert out["ok"] is True
    assert out["component"] == "memory_keep"
