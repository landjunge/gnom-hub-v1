"""G2: Gnom writes envelope JSONL, never a ThreadDesk database."""

from __future__ import annotations

import json
from pathlib import Path

from gnom_hub.authority_emit import emit, events_path
from gnom_hub.core.event_bus import EventBus
from gnom_hub.pipeline import Pipeline


def test_emit_writes_jsonl_not_sqlite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS", "1")
    out = tmp_path / "authority-events.jsonl"
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS_PATH", str(out))
    monkeypatch.setenv("GNOM_RUN_ID", "ho-test-1")
    started = emit(
        "work.started", actor="coordinator", action="execute", resource="pipeline:execute"
    )
    finished = emit(
        "work.finished",
        actor="coordinator",
        result_ref="UNGEPRÜFT",
        resource="pipeline:execute",
    )
    assert started is not None
    assert finished is not None
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    a, b = (json.loads(x) for x in lines)
    assert a["source_tool"] == "gnom-hub-v1"
    assert a["event_type"] == "work.started"
    assert a["workflow_id"] == "ho-test-1"
    assert a["trace_id"] == "ho-test-1"
    assert b["previous_event_hash"] == a["event_hash"]
    assert not list(tmp_path.glob("*.sqlite"))
    assert events_path() == out


def test_emit_disabled_under_pytest_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GNOM_AUTHORITY_EVENTS", raising=False)
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS_PATH", str(tmp_path / "x.jsonl"))
    assert emit("work.started") is None
    assert not (tmp_path / "x.jsonl").exists()


def test_emit_ignores_unknown_event_type(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS", "1")
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS_PATH", str(tmp_path / "x.jsonl"))
    assert emit("work.cancelled") is None
    assert not (tmp_path / "x.jsonl").exists()


def test_emit_reuses_threaddesk_handoff_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS", "1")
    out = tmp_path / "authority-events.jsonl"
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS_PATH", str(out))
    monkeypatch.setattr(
        "gnom_hub.threaddesk_ops.existing_handoff",
        lambda: {"handoff_id": "td-ho-42", "task_id": "ignored"},
    )
    event = emit("work.started")
    assert event is not None
    assert event["workflow_id"] == "td-ho-42"
    assert event["trace_id"] == "td-ho-42"


def test_emit_falls_back_to_task_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS", "1")
    out = tmp_path / "authority-events.jsonl"
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS_PATH", str(out))
    monkeypatch.setattr(
        "gnom_hub.threaddesk_ops.existing_handoff",
        lambda: {"task_id": "td-task-9"},
    )
    event = emit("work.started")
    assert event is not None
    assert event["workflow_id"] == "td-task-9"
    assert event["trace_id"] == "td-task-9"


def _events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return [json.loads(line) for line in text.splitlines()]


def test_execute_emits_started_invoked_finished(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS", "1")
    out = tmp_path / "authority-events.jsonl"
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS_PATH", str(out))
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path / "td"))
    pipe = Pipeline(EventBus())
    pipe.brainstorm_turn("Build a small dashboard")
    pipe.execute()
    events = _events(out)
    types = [e["event_type"] for e in events]
    assert types
    assert types[0] == "work.started"
    assert types[-1] == "work.finished"
    assert "agent.invoked" in types
    finished = events[-1]
    assert finished.get("result_ref") in {"GELIEFERT", "UNGEPRÜFT", "FEHLER", "NACHBESSERUNG"}
    assert finished.get("actor", {}).get("agent_id") == "coordinator"
    assert not list(tmp_path.glob("*.sqlite"))
    assert not list(tmp_path.glob("*.db"))


def test_execute_writes_no_jsonl_under_pytest_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GNOM_AUTHORITY_EVENTS", raising=False)
    out = tmp_path / "authority-events.jsonl"
    monkeypatch.setenv("GNOM_AUTHORITY_EVENTS_PATH", str(out))
    monkeypatch.setenv("THREADDESK_ROOT", str(tmp_path / "td"))
    pipe = Pipeline(EventBus())
    pipe.brainstorm_turn("Build a small dashboard")
    pipe.execute()
    assert not out.exists()
