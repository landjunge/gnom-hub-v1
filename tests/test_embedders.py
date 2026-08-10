"""Pluggable vector embedders (bow / char_ngram / hashing)."""

from __future__ import annotations

from pathlib import Path

from gnom_hub.memory.embedders import (
    BACKENDS,
    embed_bow,
    embed_char_ngram,
    embed_hashing,
    resolve_backend,
)
from gnom_hub.memory.vector_store import VectorStore


def test_backends_registered():
    assert set(BACKENDS) == {"bow", "char_ngram", "hashing"}
    for name in BACKENDS:
        key, fn = resolve_backend(name)
        assert key == name
        v = fn("dark theme landing page")
        assert isinstance(v, dict)
        assert v  # non-empty for real text


def test_embed_fns_l2_ish():
    import math

    for fn in (embed_bow, embed_char_ngram, embed_hashing):
        v = fn("User prefers dark theme for UI panels")
        norm = math.sqrt(sum(x * x for x in v.values()))
        assert 0.99 <= norm <= 1.01


def test_vector_store_switch_embedder(tmp_path: Path):
    vs = VectorStore(tmp_path)
    assert vs.embedder_name == "bow"
    vs.add("User: always enable dark theme", meta={"source": "flex_wish"})
    vs.add("dark room photography tips", meta={"source": "warm"})
    hits_bow = vs.search("dark theme", limit=2)
    assert hits_bow
    assert "dark theme" in hits_bow[0]["text"].lower()

    out = vs.set_embedder("char_ngram", reindex=True)
    assert out["ok"] is True
    assert out["embedder"] == "char_ngram"
    assert out["reindexed"] >= 2
    st = vs.embedder_status()
    assert st["active"] == "char_ngram"
    hits = vs.search("dark theme", limit=2)
    assert hits
    # phrase still ranks
    assert "theme" in hits[0]["text"].lower()

    vs.set_embedder("hashing", reindex=True)
    assert vs.embedder_name == "hashing"
    assert vs.search("dark theme", limit=1)

    vs.set_embedder("bow", reindex=True)
    assert vs.embedder_name == "bow"


def test_resolve_backend_rejects_unknown():
    try:
        resolve_backend("nope-model")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "unknown" in str(exc).lower()


def test_rank_eval_still_passes_with_default_bow():
    """Default bow must not regress gold rank-eval."""
    import json
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "vector_rank_eval.py"), "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = json.loads(proc.stdout)
    assert report.get("pass") is True
    assert float(report.get("p_at_1") or 0) >= 0.85
