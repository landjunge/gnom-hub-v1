"""SQLite storage management: trim, clear keep_flex, indexes, maintain."""

from __future__ import annotations

from pathlib import Path

import pytest

from gnom_hub.db.sqlite_store import GnomDatabase
from gnom_hub.memory.warm import WarmMemory


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GnomDatabase:
    monkeypatch.setenv("GNOM_USER_DB", str(tmp_path / "User" / "user.db"))
    (tmp_path / "User").mkdir(parents=True, exist_ok=True)
    return GnomDatabase(tmp_path, db_path=tmp_path / "User" / "user.db")


def test_hot_add_fact_dedupes(db: GnomDatabase) -> None:
    assert db.hot_add_fact("Prefer dark theme") is True
    assert db.hot_add_fact("Prefer dark theme") is False
    assert db.hot_fact_count() == 1


def test_hot_trim_messages_keeps_newest(db: GnomDatabase) -> None:
    for i in range(10):
        db.hot_add_message("user", f"m{i}")
    deleted = db.hot_trim_messages(4)
    assert deleted == 6
    assert db.hot_message_count() == 4
    msgs = db.hot_messages()
    assert msgs[0]["content"] == "m6"
    assert msgs[-1]["content"] == "m9"


def test_hot_trim_facts_keeps_newest(db: GnomDatabase) -> None:
    for i in range(8):
        assert db.hot_add_fact(f"fact {i}") is True
    deleted = db.hot_trim_facts(3)
    assert deleted == 5
    assert db.hot_fact_count() == 3
    facts = db.hot_facts()
    assert facts[0] == "fact 5"
    assert facts[-1] == "fact 7"


def test_warm_clear_keeps_flex_by_default(tmp_path: Path) -> None:
    warm = WarmMemory(tmp_path)
    warm.add_fact("User: stay forever", source="flex")
    warm.add_fact("ephemeral preference", source="warm")
    n = warm.clear(keep_flex=True)
    assert n >= 1
    left = warm.all_facts()
    assert "User: stay forever" in left
    assert "ephemeral preference" not in left


def test_warm_clear_all_when_keep_flex_false(tmp_path: Path) -> None:
    warm = WarmMemory(tmp_path)
    warm.add_fact("User: wipe me", source="flex")
    warm.add_fact("other", source="warm")
    warm.clear(keep_flex=False)
    assert warm.all_facts() == []


def test_maintain_analyze_and_snapshot(db: GnomDatabase) -> None:
    db.warm_add("User: a", source="flex")
    db.hot_add_message("user", "hi")
    info = db.maintain(vacuum=False)
    assert info["analyze"] is True
    assert "page_count" in info
    snap = db.snapshot_info()
    assert snap["warm_flex"] == 1
    assert snap["hot_messages"] == 1
    assert snap["bytes"] >= 0


def test_maintain_vacuum_flag(db: GnomDatabase) -> None:
    for i in range(20):
        db.warm_add(f"noise {i}", source="warm")
    db.warm_clear(keep_flex=False)
    info = db.maintain(vacuum=True)
    assert info["vacuum"] is True
    assert info["freelist"] == 0 or info["page_count"] >= 0


def test_hot_replace_session_atomic(db: GnomDatabase) -> None:
    """C2: replace is one transaction — full new session visible after call."""
    db.hot_add_message("user", "old")
    db.hot_add_fact("old fact")
    db.hot_replace_session(
        [{"role": "assistant", "content": "new msg"}],
        ["new fact a", "new fact b", "new fact a"],  # de-dupe
        updated_at="2026-01-01T00:00:00",
    )
    assert db.hot_message_count() == 1
    assert db.hot_messages()[0]["content"] == "new msg"
    assert db.hot_facts() == ["new fact a", "new fact b"]
    assert db.kv_get("hot_updated_at") == "2026-01-01T00:00:00"


def test_close_removes_instance_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """M10: close() must drop dead entry from _instances."""
    from gnom_hub.db import sqlite_store as store

    monkeypatch.setenv("GNOM_USER_DB", str(tmp_path / "User" / "user.db"))
    (tmp_path / "User").mkdir(parents=True, exist_ok=True)
    # Clear cache for this test path
    with store._lock:
        store._instances.clear()
    d1 = store.get_db(tmp_path)
    key = str(d1.path)
    assert key in store._instances or str(d1.path.resolve()) in {
        str(Path(k).resolve()) for k in store._instances
    }
    d1.close()
    with store._lock:
        assert d1 not in store._instances.values()
    d2 = store.get_db(tmp_path)
    assert d2 is not d1


def test_export_consistent_copy(db: GnomDatabase, tmp_path: Path) -> None:
    """H11 helper: online backup produces a readable independent file."""
    db.hot_add_message("user", "export me")
    db.hot_add_fact("export fact")
    dest = tmp_path / "snap" / "copy.db"
    out = db.export_consistent_copy(dest)
    assert out.is_file()
    assert out.stat().st_size > 0
    other = GnomDatabase(tmp_path, db_path=out)
    try:
        assert other.hot_message_count() == 1
        assert "export fact" in other.hot_facts()
    finally:
        other.close()


def test_compress_mirrors_hot_trim_caps(tmp_path: Path) -> None:
    """DB hard caps fire even when session was loaded over limit without collapse path."""
    from gnom_hub.memory.hot import HotMemory

    hot = HotMemory(tmp_path, auto_load=False)
    # Fill only via DB (session empty) then load
    for i in range(30):
        hot.db.hot_add_message("user", f"msg {i}")
    for i in range(20):
        hot.db.hot_add_fact(f"hf {i}")
    hot.load()
    assert len(hot.session["messages"]) == 30
    hot.compress_if_needed(max_facts=24, max_messages=40)
    # session collapse should have run for facts (20 <= 24? no collapse for facts)
    # messages 30 <= 40 → no session collapse; DB trim also no-op under max
    assert hot.db.hot_message_count() == 30
    # force over hard caps
    for i in range(40, 60):
        hot.db.hot_add_message("user", f"extra {i}")
    assert hot.db.hot_message_count() == 50
    stats2 = hot.compress_if_needed(max_facts=10, max_messages=12)
    assert stats2["db_messages_trimmed"] >= 1 or stats2["messages_collapsed"] >= 1
    assert hot.db.hot_message_count() <= 12
    assert len(hot.session["messages"]) <= 12
    assert hot.db.hot_fact_count() <= 10
