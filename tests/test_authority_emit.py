"""G2: Gnom writes envelope JSONL, never a ThreadDesk database."""

from __future__ import annotations

import json
from pathlib import Path

from gnom_hub.authority_emit import emit, events_path


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
