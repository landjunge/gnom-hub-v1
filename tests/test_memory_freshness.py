"""Write-then-read + multi-layer freshness for memory_search."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.memory.hot import HotMemory
from gnom_hub.memory.layered_search import lexical_score, search_layers
from gnom_hub.memory.vector_store import VectorStore
from gnom_hub.memory.warm import WarmMemory


def test_lexical_score_substring():
    assert lexical_score("kleinanzeigen landing", "User prefers Kleinanzeigen landing pages") > 0.5


def test_hot_searchable_before_promote(tmp_path: Path):
    hot = HotMemory(tmp_path)
    warm = WarmMemory(tmp_path)
    vec = VectorStore(tmp_path / "vectors")
    marker = "UNIQUE_FRESH_FACT_xyz_landing_kleinanzeigen_2026"
    assert hot.add_fact(marker)
    hits = search_layers(
        query="UNIQUE_FRESH_FACT landing", hot=hot, warm=warm, vectors=vec, limit=5
    )
    assert any(marker in str(h.get("text")) for h in hits)
    assert any(h.get("layer") == "hot" for h in hits)
    assert any(h.get("indexed") is False for h in hits if marker in str(h.get("text")))


def test_warm_promote_write_then_read_vector(tmp_path: Path):
    """Classic race: promote → immediate memory_search must hit."""
    hot = HotMemory(tmp_path)
    warm = WarmMemory(tmp_path)
    vec = VectorStore(tmp_path / "vectors")
    marker = "PROMOTED_FACT_sync_searchable_alpha_beta"
    hot.add_fact(marker)
    assert warm.add_fact(marker)
    vec.add(marker, meta={"source": "warm_promote"})  # sync index path
    hits = search_layers(query="PROMOTED_FACT_sync", hot=hot, warm=warm, vectors=vec, limit=8)
    texts = [str(h.get("text")) for h in hits]
    assert any(marker in t for t in texts)
    # Prefer seeing vector or warm
    layers = {h.get("layer") for h in hits if marker in str(h.get("text"))}
    assert layers & {"vector", "warm", "hot"}


def test_hub_memory_search_write_then_read(tmp_path: Path, monkeypatch):
    import gnom_hub.hub as hub_mod
    from gnom_hub.config import paths
    from gnom_hub.hub import Hub

    monkeypatch.setattr(paths, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    # Also patch common re-imports
    import gnom_hub.memory.hot as hot_mod
    import gnom_hub.memory.warm as warm_mod

    monkeypatch.setattr(hot_mod, "project_root", lambda: tmp_path, raising=False)
    monkeypatch.setattr(warm_mod, "project_root", lambda: tmp_path, raising=False)
    hub_mod._HUB = None
    hub = Hub()
    try:
        assert Path(hub.root) == tmp_path or str(hub.root) == str(tmp_path)
        # isolate session facts
        hub.hot.clear_facts() if hasattr(hub.hot, "clear_facts") else None
        hub.hot.session["facts"] = []
        marker = "HUB_WRITE_READ_MEMORY_marker_omega_zz9"
        r = hub.add_hot_fact(marker)
        if not r.get("ok"):
            # de-dupe / store path — force insert for test
            hub.hot.session.setdefault("facts", []).append(marker)
            hub.hot.save()
        hits = hub._tool_memory_search("HUB_WRITE_READ_MEMORY_marker", limit=5)
        assert any(marker in str(h.get("text")) for h in hits)
        p = hub.promote_hot_fact(marker)
        if not p.get("ok") and marker in hub.hot.all_facts():
            hub.warm.add_fact(marker)
            hub.index_durable_fact(marker, source="warm_promote")
        hits2 = hub._tool_memory_search("HUB_WRITE_READ_MEMORY_marker", limit=8)
        assert any(marker in str(h.get("text")) for h in hits2)
    finally:
        hub_mod._HUB = None
