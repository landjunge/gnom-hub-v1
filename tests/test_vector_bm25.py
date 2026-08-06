"""BM25 hybrid vector search — short-doc params + bigrams + distractors."""

from pathlib import Path

from gnom_hub.memory import vector_store as m
from gnom_hub.memory.vector_store import VectorStore, _bm25_scores, _tokenize


def test_short_doc_defaults() -> None:
    # Fine-tuned short-fact defaults (see vector_store module comment)
    assert m._K1 == 1.15
    assert m._B == 0.25
    assert m._BM25_WEIGHT == 0.88
    assert m._COSINE_WEIGHT == 0.12
    assert abs(m._BM25_WEIGHT + m._COSINE_WEIGHT - 1.0) < 1e-9
    assert m._MIN_SCORE == 0.025
    assert m._SOURCE_BOOST["flex_wish"] == 1.20


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


def test_bm25_distractor_ranking_short_facts(tmp_path: Path) -> None:
    """Fine-tune regression: real wish beats topical distractors."""
    vs = VectorStore(tmp_path)
    vs.add("dark room photography tips and theme parks", meta={"source": "warm"})
    vs.add("User: always enable dark theme", meta={"source": "flex_wish"})
    vs.add("clear the table and wipe the desk now", meta={"source": "warm"})
    vs.add("User: never wipe wishes on clear", meta={"source": "flex_wish"})
    vs.add("flex muscles workout routine gym", meta={"source": "warm"})
    vs.add("TTS should read Flex thoughts", meta={"source": "flex_wish"})

    h1 = vs.search("dark theme", limit=2)
    assert h1 and "always enable dark theme" in h1[0]["text"]

    h2 = vs.search("wipe wishes clear", limit=2)
    assert h2 and "never wipe wishes" in h2[0]["text"].lower()

    h3 = vs.search("TTS Flex thoughts", limit=2)
    assert h3 and "TTS should read" in h3[0]["text"]


def test_bm25_source_boost_flex(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path)
    vs.add("always use ruff before push", meta={"source": "requirement"})
    vs.add("User: always use ruff before push", meta={"source": "flex_wish"})
    hits = vs.search("ruff before push", limit=2)
    assert hits
    assert hits[0]["meta"].get("source") == "flex_wish"


def test_bm25_min_score_filters_noise(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path)
    vs.add("completely unrelated zebra astronomy")
    hits = vs.search("ruff format python lint", limit=5, min_score=0.08)
    assert isinstance(hits, list)
    for h in hits:
        assert h["score"] >= 0.08


def test_bm25_param_override(tmp_path: Path) -> None:
    vs = VectorStore(tmp_path, k1=1.15, b=0.25)
    vs.add("USB portable single-file HTML")
    hits = vs.search("portable USB", k1=1.0, b=0.2, limit=1)
    assert hits and hits[0]["score"] > 0


def test_bm25_unit_scores_monotone() -> None:
    docs = [
        _tokenize("dark theme ui preference", drop_stop=True),
        _tokenize("usb stick portable", drop_stop=True),
    ]
    q = _tokenize("dark theme", drop_stop=True)
    scores = _bm25_scores(q, docs, k1=1.15, b=0.25)
    assert scores[0] > scores[1]


def test_hybrid_weights_bm25_dominates(tmp_path: Path) -> None:
    """With 0.88 BM25 weight, exact token match beats weak cosine-only overlap."""
    vs = VectorStore(tmp_path)
    vs.add("alpha beta gamma delta epsilon zeta", meta={"source": "warm"})
    vs.add("User: portable USB install path", meta={"source": "flex_wish"})
    hits = vs.search("portable USB", limit=1)
    assert hits
    assert "portable USB" in hits[0]["text"]
