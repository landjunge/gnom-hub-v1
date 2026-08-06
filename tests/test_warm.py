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
    assert "/User/" in info["path"].replace("\\", "/") or info["path"].endswith("User/user.db")
    assert info["warm_facts"] >= 1


def test_facade_flex_wishes_first_and_protected(tmp_path: Path):
    warm = WarmMemory(tmp_path)
    hot = HotMemory(tmp_path, auto_load=False)
    warm.add_fact("User: always enable TTS for Flex", source="flex")
    warm.add_fact("User: never wipe wishes on clear", source="flex")
    warm.add_fact("Brand is Bean and Bloom", source="warm")
    # Flood HOT so naive truncation would cut the top
    for i in range(40):
        hot.add_message("user", f"noise message number {i} " + ("x" * 40))
    fac = MemoryFacade(hot, warm)
    ctx = fac.pipeline_context(max_chars=400)
    assert ctx.startswith("FLEX_WISHES")
    assert "always enable TTS for Flex" in ctx
    assert "never wipe wishes on clear" in ctx
    # flex block not only present but before HOT noise / truncated rest
    assert ctx.index("FLEX_WISHES") < ctx.find("noise") or "noise" not in ctx


def test_facade_flex_survives_hot_clear(tmp_path: Path):
    warm = WarmMemory(tmp_path)
    hot = HotMemory(tmp_path, auto_load=False)
    warm.add_fact_flex("immer Execute nur mit klarer Aufgabe")
    hot.add_message("user", "temp")
    hot.clear(save=True)
    fac = MemoryFacade(HotMemory(tmp_path, auto_load=False), WarmMemory(tmp_path))
    ctx = fac.pipeline_context()
    assert "FLEX_WISHES" in ctx
    assert "Execute" in ctx or "klare Aufgabe" in ctx
