"""R6.2: ThreadDesk handoff.json after Behalten. Never a DB, never Execute."""

from __future__ import annotations

import json
from pathlib import Path

from gnom_hub.core.event_bus import EventBus
from gnom_hub.flex_desk import FlexDesk
from gnom_hub.memory.facade import MemoryFacade
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.warm import WarmMemory
from gnom_hub.pipeline.orchestrator import Pipeline
from gnom_hub.threaddesk_ops import peek, write_handoff


def test_write_handoff_packet_fields(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    out = write_handoff(["Marke ist Bean und Bloom", "sk-SECRET99999999"])
    assert out["ok"] is True
    assert out["ran"] is False
    path = Path(out["path"])
    assert path.name == "handoff.json"
    packet = json.loads(path.read_text(encoding="utf-8"))
    for key in (
        "sender",
        "recipient",
        "project_id",
        "run_id",
        "purpose",
        "data_refs",
        "valid_until",
        "approval",
        "result",
        "kind",
        "ran",
    ):
        assert key in packet
    assert packet["sender"] == "gnom-hub-v1"
    assert packet["recipient"] == "threaddesk"
    assert packet["ran"] is False
    assert packet["kind"] == "threaddesk.handoff"
    texts = [r["text"] for r in packet["data_refs"]]
    assert "Marke ist Bean und Bloom" in texts
    assert not any("sk-" in t for t in texts)
    assert list(tmp_path.glob("*.db")) == []
    assert list(tmp_path.glob("*.sqlite*")) == []
    seen = peek()
    assert seen["ran"] is False
    assert seen["present"] is True
    assert "Bean" in seen["text"]


def test_conflict_without_overwrite(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    first = write_handoff(["Erste Marke"])
    assert first["ok"] is True
    second = write_handoff(["Zweite Marke"], overwrite=False)
    assert second["ok"] is False
    assert second["error"] == "conflict"
    assert second["ran"] is False
    packet = json.loads((tmp_path / "handoff.json").read_text(encoding="utf-8"))
    assert "Erste Marke" in packet["notes"]
    assert "Zweite Marke" not in packet["notes"]


def test_overwrite_replaces(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    write_handoff(["Alte Marke"])
    out = write_handoff(["Neue Marke"], overwrite=True)
    assert out["ok"] is True
    packet = json.loads((tmp_path / "handoff.json").read_text(encoding="utf-8"))
    assert "Neue Marke" in packet["notes"]
    assert packet["ran"] is False


def test_box1_uebergeben_writes(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    bus = EventBus()
    pipe = Pipeline(
        bus, memory=MemoryFacade(HotMemory(tmp_path, auto_load=False), WarmMemory(tmp_path))
    )
    pipe._offer_td_handoff(["Immer deutsch"])
    q = pipe.flex_desk.open_questions()[0]
    assert q.component == "td_handoff"
    ans = pipe.flex_desk.answer(q.question_id, "Übergeben")
    assert ans["wants_start_work"] is False
    assert ans["handoff_write"] is True
    out = pipe.apply_td_handoff(True)
    assert out["ok"] is True
    assert out["ran"] is False
    assert (tmp_path / "handoff.json").is_file()
    assert pipe.state.worker_results == []


def test_nicht_uebergeben_writes_nothing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    pipe = Pipeline(
        EventBus(),
        memory=MemoryFacade(HotMemory(tmp_path, auto_load=False), WarmMemory(tmp_path)),
    )
    pipe._offer_td_handoff(["Nicht schreiben"])
    pipe.apply_td_handoff(False)
    assert not (tmp_path / "handoff.json").is_file()


def test_conflict_then_keep_existing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path))
    write_handoff(["Bestehendes Paket"])
    pipe = Pipeline(
        EventBus(),
        memory=MemoryFacade(HotMemory(tmp_path, auto_load=False), WarmMemory(tmp_path)),
    )
    pipe._offer_td_handoff(["Neuer Versuch"])
    out = pipe.apply_td_handoff(True, overwrite=False)
    assert out.get("error") == "conflict"
    qs = [q for q in pipe.flex_desk.open_questions() if q.component == "td_replace"]
    assert qs
    keep = pipe.flex_desk.answer(qs[0].question_id, "Bestehendes behalten")
    assert keep["handoff_replace"] is False
    assert keep["wants_start_work"] is False
    pipe.apply_td_handoff(False, overwrite=True)
    packet = json.loads((tmp_path / "handoff.json").read_text(encoding="utf-8"))
    assert "Bestehendes Paket" in packet["notes"]


def test_td_handoff_component_registered():
    desk = FlexDesk()
    out = desk.ask(
        agent_id="memory",
        text="An ThreadDesk übergeben?\n• x\nNur ein Paket.",
        component="td_handoff",
    )
    assert out["ok"] is True
    assert out["component"] == "td_handoff"
    assert "Übergeben" in out["options"]
