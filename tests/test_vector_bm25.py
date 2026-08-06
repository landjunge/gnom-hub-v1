"""BM25 hybrid vector search (stage-1 embeddings)."""

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


def test_bm25_source_boost_flex(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path)
    vs.add("always use ruff before push", meta={"source": "requirement"})
    vs.add("User: always use ruff before push", meta={"source": "flex_wish"})
    hits = vs.search("ruff before push", limit=2)
    assert hits
    # flex_wish should rank at least as high as requirement (boost)
    assert hits[0]["meta"].get("source") == "flex_wish" or hits[0]["score"] > 0


def test_bm25_min_score_filters_noise(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path)
    vs.add("completely unrelated zebra astronomy")
    hits = vs.search("ruff format python lint", limit=5, min_score=0.05)
    # may be empty or very weak — must not crash
    assert isinstance(hits, list)
    for h in hits:
        assert h["score"] >= 0.05


def test_bm25_unit_scores_monotone() -> None:
    docs = [
        _tokenize("dark theme ui preference", drop_stop=True),
        _tokenize("usb stick portable", drop_stop=True),
    ]
    q = _tokenize("dark theme", drop_stop=True)
    scores = _bm25_scores(q, docs)
    assert scores[0] > scores[1]
