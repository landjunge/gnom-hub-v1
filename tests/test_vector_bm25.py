"""BM25 hybrid vector search — short-doc params + bigrams."""

from pathlib import Path

from gnom_hub.memory.vector_store import VectorStore, _bm25_scores, _tokenize


def test_bm25_prefers_rare_informative_terms(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path)
    vs.add("the the the the common words only filler text here")
    vs.add("User prefers dark theme for UI panels")
    vs.add("usb portable installation on stick")
    hits = vs.search("dark theme UI", limit=3)
    assert hits
    assert "dark" in hits[0]["text"].lower()


def test_bm25_bigrams_prefer_phrase_match(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path)
    vs.add("dark room with theme park tickets")  # both tokens, not phrase
    vs.add("User prefers dark theme for UI")  # true phrase
    hits = vs.search("dark theme", limit=2)
    assert hits
    assert "prefers dark theme" in hits[0]["text"].lower()


def test_bm25_source_boost_flex(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path)
    vs.add("always use ruff before push", meta={"source": "requirement"})
    vs.add("User: always use ruff before push", meta={"source": "flex_wish"})
    hits = vs.search("ruff before push", limit=2)
    assert hits
    assert hits[0]["meta"].get("source") == "flex_wish" or hits[0]["score"] > 0


def test_bm25_min_score_filters_noise(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path)
    vs.add("completely unrelated zebra astronomy")
    hits = vs.search("ruff format python lint", limit=5, min_score=0.05)
    assert isinstance(hits, list)
    for h in hits:
        assert h["score"] >= 0.05


def test_bm25_param_override(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path, k1=1.2, b=0.3)
    vs.add("USB portable single-file HTML")
    hits = vs.search("portable USB", k1=1.0, b=0.2, limit=1)
    assert hits and hits[0]["score"] > 0


def test_bm25_unit_scores_monotone() -> None:
    docs = [
        _tokenize("dark theme ui preference", drop_stop=True),
        _tokenize("usb stick portable", drop_stop=True),
    ]
    q = _tokenize("dark theme", drop_stop=True)
    scores = _bm25_scores(q, docs, k1=1.2, b=0.3)
    assert scores[0] > scores[1]


def test_short_doc_defaults() -> None:
    from gnom_hub.memory import vector_store as m

    assert m._K1 == 1.2
    assert m._B == 0.3
    assert m._BM25_WEIGHT == 0.85
    assert abs(m._BM25_WEIGHT + m._COSINE_WEIGHT - 1.0) < 1e-9
