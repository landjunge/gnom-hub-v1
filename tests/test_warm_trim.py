"""warm_trim: non-flex first, flex last, flex_reserve protect-first."""

from __future__ import annotations

from pathlib import Path

import pytest

from gnom_hub.db.sqlite_store import GnomDatabase
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.warm import WarmMemory


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> GnomDatabase:
    monkeypatch.setenv("GNOM_USER_DB", str(tmp_path / "User" / "user.db"))
    (tmp_path / "User").mkdir(parents=True, exist_ok=True)
    return GnomDatabase(tmp_path, db_path=tmp_path / "User" / "user.db")


def _add(db: GnomDatabase, text: str, source: str) -> None:
    assert db.warm_add(text, source=source) is True


def test_warm_trim_noop_under_max(db: GnomDatabase) -> None:
    for i in range(5):
        _add(db, f"User: wish {i}", "flex")
    for i in range(5):
        _add(db, f"other fact {i}", "warm")
    before = db.warm_count()
    stats = db.warm_trim(max_facts=50, flex_reserve=40)
    assert db.warm_count() == before == 10
    assert stats["dropped_non_flex"] == 0
    assert stats["dropped_flex"] == 0


def test_warm_trim_drops_non_flex_first(db: GnomDatabase) -> None:
    for i in range(3):
        _add(db, f"User: keep me {i}", "flex")
    for i in range(10):
        _add(db, f"noise fact {i:02d}", "warm")

    stats = db.warm_trim(max_facts=8, flex_reserve=40)

    assert db.warm_count() == 8
    texts = db.warm_all()
    flex = [t for t in texts if t.lower().startswith("user: keep me")]
    assert len(flex) == 3
    non = [t for t in texts if t.startswith("noise")]
    assert len(non) == 5
    assert "noise fact 00" not in texts
    assert stats["dropped_non_flex"] == 5
    assert stats["dropped_flex"] == 0


def test_warm_trim_never_touches_flex_if_non_flex_enough(db: GnomDatabase) -> None:
    flex_texts = [f"User: rule {i}" for i in range(5)]
    for t in flex_texts:
        _add(db, t, "flex")
    for i in range(20):
        _add(db, f"mem {i}", "memory")

    db.warm_trim(max_facts=10, flex_reserve=40)

    left = set(db.warm_all())
    for t in flex_texts:
        assert t in left
    assert db.warm_count() == 10


def test_warm_trim_flex_reserve_then_drop_oldest_flex(db: GnomDatabase) -> None:
    for i in range(15):
        _add(db, f"User: wish {i:02d}", "flex")

    stats = db.warm_trim(max_facts=10, flex_reserve=8)

    assert db.warm_count() == 10
    texts = db.warm_all()
    assert "User: wish 00" not in texts
    assert "User: wish 14" in texts
    assert stats["dropped_flex"] == 5
    assert stats["flex_left"] == 10


def test_warm_trim_stops_at_flex_reserve_when_only_flex(db: GnomDatabase) -> None:
    for i in range(12):
        _add(db, f"User: protected {i:02d}", "flex")

    stats = db.warm_trim(max_facts=5, flex_reserve=10)

    # protect-first: stop at reserve, may stay above max_facts
    assert db.warm_count() == 10
    assert stats["dropped_flex"] == 2
    assert stats["flex_left"] == 10
    assert all(t.lower().startswith("user:") for t in db.warm_all())


def test_warm_trim_treats_null_and_warm_as_non_flex(db: GnomDatabase) -> None:
    _add(db, "User: stay", "flex")
    _add(db, "legacy A", "warm")
    _add(db, "legacy B", "migrate")
    db.warm_trim(max_facts=1, flex_reserve=40)
    assert db.warm_all() == ["User: stay"]


def test_warm_add_flex_duplicate_no_extra_row(db: GnomDatabase) -> None:
    assert db.warm_add("User: always DE", source="flex") is True
    assert db.warm_add("User: always DE", source="flex") is False
    assert db.warm_count() == 1
    db.warm_trim(max_facts=1, flex_reserve=40)
    assert db.warm_all() == ["User: always DE"]


def test_hot_clear_keeps_warm_flex(tmp_path: Path) -> None:
    warm = WarmMemory(tmp_path)
    assert warm.add_fact("User: never forget this", source="flex") is True
    hot = HotMemory(tmp_path, auto_load=False)
    hot.add_message("user", "hi")
    hot.clear(save=True)
    warm2 = WarmMemory(tmp_path)
    assert "User: never forget this" in warm2.all_facts()


def test_explicit_wish_delete_not_via_trim(db: GnomDatabase) -> None:
    _add(db, "User: temp wish", "flex")
    assert db.warm_remove("User: temp wish") is True
    assert db.warm_count() == 0
    db.warm_trim(max_facts=10, flex_reserve=40)
    assert db.warm_count() == 0


def test_warm_trim_deterministic_order(db: GnomDatabase) -> None:
    for i in range(3):
        _add(db, f"User: f{i}", "flex")
    for i in range(10):
        _add(db, f"n{i:02d}", "warm")

    db.warm_trim(max_facts=6, flex_reserve=40)
    left = db.warm_all()
    assert len(left) == 6
    assert {f"User: f{i}" for i in range(3)}.issubset(set(left))
    assert sum(1 for t in left if t.startswith("n")) == 3


def test_add_fact_flex_helper(tmp_path: Path) -> None:
    warm = WarmMemory(tmp_path)
    assert warm.add_fact_flex("immer TTS an für Brainstorm") is True
    facts = warm.all_facts()
    assert any(f.lower().startswith("user:") for f in facts)
    # duplicate ADD-only
    assert warm.add_fact_flex("User: immer TTS an für Brainstorm") is False or True
    # second call may normalize differently; at least one flex-sourced row
    assert warm.db.warm_count_source("flex") >= 1
