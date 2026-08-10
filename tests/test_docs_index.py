"""Docs index builder + search API."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _mod():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "build_docs_index.py"
    spec = importlib.util.spec_from_file_location("build_docs_index", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_collect_and_search():
    mod = _mod()
    rows = mod.collect()
    assert len(rows) >= 20
    files = {r["file"] for r in rows}
    assert "SKILLS.md" in files
    hits = mod.search(rows, "skills embeddings install", limit=5)
    assert hits
    assert any("SKILL" in h["file"].upper() or "skill" in h["title"].lower() for h in hits)


def test_docs_search_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import gnom_hub.hub as hub_mod
    from gnom_hub.api.app import create_app

    root = Path(__file__).resolve().parents[1]
    # hub needs project with scripts + docs
    monkeypatch.setattr(hub_mod, "project_root", lambda: root)
    monkeypatch.setattr(hub_mod, "_HUB", None)
    app = create_app()
    with TestClient(app) as c:
        r = c.get("/api/docs")
        assert r.status_code == 200
        body = r.json()
        assert body.get("count", 0) >= 1
        r2 = c.get("/api/docs/search", params={"q": "plan_mode", "limit": 8})
        assert r2.status_code == 200
        assert "hits" in r2.json()
    hub_mod._HUB = None
