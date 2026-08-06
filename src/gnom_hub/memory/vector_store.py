"""Vector lite: BM25 + bag-of-words cosine (no heavy deps)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from gnom_hub.config.paths import project_root
from gnom_hub.memory.atomic import atomic_write_text

_TOKEN = re.compile(r"[a-z0-9äöüß]{2,}", re.IGNORECASE)

# Light DE/EN stopwords — keep short facts usable (do not over-filter)
_STOP = frozenset(
    {
        "und",
        "oder",
        "der",
        "die",
        "das",
        "ein",
        "eine",
        "ist",
        "are",
        "the",
        "and",
        "or",
        "for",
        "mit",
        "von",
        "zu",
        "im",
        "in",
        "on",
        "of",
        "to",
        "a",
        "an",
    }
)

# Okapi BM25 defaults
_K1 = 1.5
_B = 0.75

# Hybrid blend + filters
_BM25_WEIGHT = 0.75
_COSINE_WEIGHT = 0.25
_MIN_SCORE = 0.02

_SOURCE_BOOST = {
    "flex_wish": 1.15,
    "flex_personal": 1.15,
    "warm": 1.08,
    "memory_agent": 1.05,
    "requirement": 1.0,
}


def _tokenize(text: str, *, drop_stop: bool = False) -> list[str]:
    toks = [t.lower() for t in _TOKEN.findall(text or "")]
    if drop_stop:
        toks = [t for t in toks if t not in _STOP]
    return toks


def _embed(text: str) -> dict[str, float]:
    """L2-normalized bag-of-words (stored for cosine / backward compat)."""
    counts: dict[str, float] = {}
    for t in _tokenize(text, drop_stop=True):
        counts[t] = counts.get(t, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return {k: v / norm for k, v in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def _bm25_scores(
    query_tokens: list[str],
    docs_tokens: list[list[str]],
    *,
    k1: float = _K1,
    b: float = _B,
) -> list[float]:
    """Standard BM25 over in-memory token lists."""
    n = len(docs_tokens)
    if n == 0 or not query_tokens:
        return []
    df: dict[str, int] = {}
    for toks in docs_tokens:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    avgdl = sum(len(t) for t in docs_tokens) / n
    scores: list[float] = []
    for toks in docs_tokens:
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        dl = len(toks) or 1
        s = 0.0
        for q in query_tokens:
            f = tf.get(q, 0)
            if f <= 0:
                continue
            n_q = df.get(q, 0)
            # IDF as in Okapi BM25 (positive for rare terms)
            idf = math.log(1.0 + (n - n_q + 0.5) / (n_q + 0.5))
            denom = f + k1 * (1.0 - b + b * dl / (avgdl or 1.0))
            s += idf * (f * (k1 + 1.0)) / (denom or 1.0)
        scores.append(s)
    return scores


def _source_boost(meta: dict[str, Any] | None) -> float:
    if not meta:
        return 1.0
    src = str(meta.get("source") or "").lower()
    return float(_SOURCE_BOOST.get(src, 1.0))


class VectorStore:
    """
    data/vector/docs.jsonl — {id, text, meta, vec}

    Search = hybrid BM25 (primary) + cosine on stored BoW vec (secondary).
    Zero heavy deps; USB / offline friendly.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.dir = self.root / "data" / "vector"
        self.path = self.dir / "docs.jsonl"
        self._docs: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        self._docs = []
        if not self.path.is_file():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                self._docs.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        body = "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in self._docs)
        atomic_write_text(self.path, body)

    def upsert(self, doc_id: str, text: str, meta: dict[str, Any] | None = None) -> str:
        text = (text or "").strip()
        if not text:
            return doc_id
        vec = _embed(text)
        entry = {"id": doc_id, "text": text, "meta": meta or {}, "vec": vec}
        for i, d in enumerate(self._docs):
            if d.get("id") == doc_id:
                self._docs[i] = entry
                self.save()
                return doc_id
        self._docs.append(entry)
        self.save()
        return doc_id

    def add(self, text: str, meta: dict[str, Any] | None = None) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        try:
            from gnom_hub.agents.roles_helpers import _is_garbage_fact

            if _is_garbage_fact(text):
                return ""
        except Exception:  # noqa: BLE001
            pass
        doc_id = f"v{len(self._docs) + 1}"
        return self.upsert(doc_id, text, meta)

    def scrub(self) -> int:
        """Drop garbage docs; returns number removed."""
        try:
            from gnom_hub.agents.roles_helpers import _is_garbage_fact
        except Exception:  # noqa: BLE001
            return 0
        before = len(self._docs)
        kept: list[dict[str, Any]] = []
        seen: set[str] = set()
        for d in self._docs:
            text = str(d.get("text") or "").strip()
            if not text or _is_garbage_fact(text):
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            kept.append(d)
        removed = before - len(kept)
        if removed:
            self._docs = kept
            self.save()
        return removed

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        min_score: float = _MIN_SCORE,
    ) -> list[dict[str, Any]]:
        """Hybrid BM25 + cosine; rare terms beat raw token overlap."""
        q = (query or "").strip()
        if not q or not self._docs:
            return []
        q_toks = _tokenize(q, drop_stop=True)
        if not q_toks:
            q_toks = _tokenize(q, drop_stop=False)
        docs_toks = [
            _tokenize(str(d.get("text") or ""), drop_stop=True)
            or _tokenize(str(d.get("text") or ""))
            for d in self._docs
        ]
        bm25 = _bm25_scores(q_toks, docs_toks)
        # Normalize BM25 to ~0..1 for blend (relative to max in this query)
        max_b = max(bm25) if bm25 else 0.0
        qv = _embed(q)
        scored: list[tuple[float, dict[str, Any]]] = []
        for i, d in enumerate(self._docs):
            b_raw = bm25[i] if i < len(bm25) else 0.0
            b_norm = (b_raw / max_b) if max_b > 0 else 0.0
            vec = d.get("vec") or {}
            if isinstance(vec, dict) and vec:
                c = _cosine(qv, {str(k): float(v) for k, v in vec.items()})
            else:
                c = _cosine(qv, _embed(str(d.get("text") or "")))
            hybrid = _BM25_WEIGHT * b_norm + _COSINE_WEIGHT * c
            hybrid *= _source_boost(d.get("meta") if isinstance(d.get("meta"), dict) else None)
            scored.append((hybrid, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, d in scored[:limit]:
            if score < min_score:
                continue
            out.append(
                {
                    "id": d.get("id"),
                    "text": d.get("text"),
                    "meta": d.get("meta") or {},
                    "score": round(score, 4),
                }
            )
        return out

    def count(self) -> int:
        return len(self._docs)

    def list_docs(self, limit: int = 40) -> list[dict[str, Any]]:
        """Newest-last slice without embedding vectors (for UI)."""
        out: list[dict[str, Any]] = []
        for d in self._docs[-max(1, limit) :]:
            out.append(
                {
                    "id": d.get("id"),
                    "text": str(d.get("text") or "")[:500],
                    "meta": d.get("meta") or {},
                }
            )
        return list(reversed(out))

    def get(self, doc_id: str) -> dict[str, Any] | None:
        for d in self._docs:
            if d.get("id") == doc_id:
                return {
                    "id": d.get("id"),
                    "text": d.get("text"),
                    "meta": d.get("meta") or {},
                }
        return None

    def delete(self, doc_id: str) -> bool:
        before = len(self._docs)
        self._docs = [d for d in self._docs if d.get("id") != doc_id]
        if len(self._docs) == before:
            return False
        self.save()
        return True

    def clear(self) -> None:
        self._docs = []
        self.save()
