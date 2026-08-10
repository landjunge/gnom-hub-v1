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


def test_api_vector_embedder(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import gnom_hub.hub as hub_mod
    from gnom_hub.api.app import create_app

    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/api/vector")
        assert r.status_code == 200
        body = r.json()
        assert "embedder" in body
        assert body["embedder"].get("active") == "bow"
        r2 = c.post("/api/vector/add", json={"text": "User prefers dark theme UI"})
        assert r2.status_code == 200
        r3 = c.post(
            "/api/vector/embedder",
            json={"backend": "char_ngram", "reindex": True},
        )
        assert r3.status_code == 200
        assert r3.json()["embedder"]["active"] == "char_ngram"
        r4 = c.post("/api/vector/search", json={"query": "dark theme", "limit": 3})
        assert r4.status_code == 200
        assert r4.json().get("embedder") == "char_ngram"
        bad = c.post("/api/vector/embedder", json={"backend": "nope", "reindex": False})
        assert bad.status_code == 400
    hub_mod._HUB = None


def test_probe_neural_fastembed_installed():
    from gnom_hub.memory.neural_embed import probe_neural

    p = probe_neural()
    assert "fastembed" in p
    # CI may or may not have package; if installed, True
    try:
        import fastembed  # noqa: F401

        assert p["fastembed"] is True
    except ImportError:
        assert p["fastembed"] is False


def test_api_vector_embedder_fastembed_if_available(tmp_path, monkeypatch):
    try:
        import fastembed  # noqa: F401
    except ImportError:
        return  # skip without package
    from fastapi.testclient import TestClient

    import gnom_hub.hub as hub_mod
    from gnom_hub.api.app import create_app

    monkeypatch.setattr(hub_mod, "project_root", lambda: tmp_path)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/api/vector")
        assert r.status_code == 200
        emb = r.json().get("embedder") or {}
        assert emb.get("neural_available", {}).get("fastembed") is True
        r2 = c.post(
            "/api/vector/embedder",
            json={"backend": "fastembed", "reindex": False},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["embedder"]["active"] == "fastembed"
    hub_mod._HUB = None
