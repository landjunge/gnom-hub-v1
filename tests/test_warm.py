from pathlib import Path

from gnom_hub.memory.facade import MemoryFacade
from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.warm import WarmMemory


def test_warm_survives_hot_clear(tmp_path: Path):
    warm = WarmMemory(tmp_path)
    hot = HotMemory(tmp_path, auto_load=False)
    warm.add_fact("Prefer dark theme always")
    hot.add_fact("session only fact")
    hot.clear(save=True)
    warm2 = WarmMemory(tmp_path)
    assert "Prefer dark theme always" in warm2.all_facts()
    hot2 = HotMemory(tmp_path)
    assert hot2.recent_facts() == []


def test_facade_merges_warm_into_context(tmp_path: Path):
    warm = WarmMemory(tmp_path)
    hot = HotMemory(tmp_path, auto_load=False)
    warm.add_fact("USB portable mode")
    hot.add_message("user", "hi")
    fac = MemoryFacade(hot, warm)
    ctx = fac.pipeline_context()
    assert "USB portable mode" in ctx
    assert "WARM facts" in ctx


def test_warm_rejects_garbage_and_persists_in_user_db(tmp_path: Path):
    warm = WarmMemory(tmp_path)
    assert warm.add_fact("<!DOCTYPE html>") is False
    assert warm.add_fact("(no durable facts to store)") is False
    assert warm.add_fact("Prefer portable single-file HTML exports.") is True
    assert warm.add_fact("Worker produced partial HTML") is False
    # Reload from same tmp user.db — durable personal store
    warm2 = WarmMemory(tmp_path)
    facts = warm2.all_facts()
    assert "Prefer portable single-file HTML exports." in facts
    assert not any("<html" in f.lower() for f in facts)
    assert not any("worker produced" in f.lower() for f in facts)
    from gnom_hub.db.sqlite_store import get_db

    info = get_db(tmp_path).snapshot_info()
    assert info["path"].endswith("user.db")
    assert info["warm_facts"] >= 1
