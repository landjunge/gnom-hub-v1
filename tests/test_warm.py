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


def test_warm_rejects_and_scrubs_garbage(tmp_path: Path):
    warm = WarmMemory(tmp_path)
    assert warm.add_fact("<!DOCTYPE html>") is False
    assert warm.add_fact("(no durable facts to store)") is False
    assert warm.add_fact("Prefer portable single-file HTML exports.") is True
    # Inject garbage on disk then reload
    path = warm.facts_path
    path.write_text(
        path.read_text(encoding="utf-8")
        + '{"text": "<html lang=\\"de\\">", "ts": "x"}\n'
        + '{"text": "Worker produced partial HTML", "ts": "x"}\n',
        encoding="utf-8",
    )
    warm2 = WarmMemory(tmp_path)
    facts = warm2.all_facts()
    assert "Prefer portable single-file HTML exports." in facts
    assert not any("<html" in f.lower() for f in facts)
    assert not any("worker produced" in f.lower() for f in facts)
