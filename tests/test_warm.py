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
