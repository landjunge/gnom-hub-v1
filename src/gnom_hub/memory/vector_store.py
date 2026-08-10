"""Vector lite: BM25 (short-doc tuned) + pluggable cosine embedder (no heavy deps)."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gnom_hub.config.paths import project_root
from gnom_hub.memory.atomic import atomic_write_text
from gnom_hub.memory.embedders import embed_bow, resolve_backend

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

# Short-document Okapi BM25 (WARM/Flex facts ≈ 5–20 tokens, not web pages).
# Tuned 2026-08 for Gnom fact lines (grid + distractor ranking):
#   k1≈1.15 → mild TF saturation (lines rarely repeat tokens)
#   b≈0.25  → little length norm (all candidates similarly short)
#   BM25 88% / cosine 12% → lexical phrase match dominates BoW ties
#   flex_wish ×1.20 → standing wishes outrank similar requirement/warm lines
_K1 = 1.15
_B = 0.25

# Hybrid: BM25 carries lexical intent; cosine is a light tie-breaker on BoW vec.
_BM25_WEIGHT = 0.88
_COSINE_WEIGHT = 0.12
_MIN_SCORE = 0.025

_SOURCE_BOOST = {
    "flex_wish": 1.20,
    "flex_personal": 1.15,
    "warm": 1.06,
    "memory_agent": 1.05,
    "requirement": 1.0,
}


def _unigrams(text: str, *, drop_stop: bool = False) -> list[str]:
    toks = [t.lower() for t in _TOKEN.findall(text or "")]
    if drop_stop:
        toks = [t for t in toks if t not in _STOP]
    return toks


def _tokenize(text: str, *, drop_stop: bool = False, bigrams: bool = True) -> list[str]:
    """Unigrams + adjacent bigrams (helps 'dark theme', 'bean bloom', 'hot clear')."""
    uni = _unigrams(text, drop_stop=drop_stop)
    if not bigrams or len(uni) < 2:
        return uni
    bi = [f"{uni[i]}_{uni[i + 1]}" for i in range(len(uni) - 1)]
    return uni + bi


def _embed(text: str) -> dict[str, float]:
    """Default embedder (bag-of-words) — VectorStore may override per instance."""
    return embed_bow(text)


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
        return [0.0] * n if n else []
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

    Search = hybrid BM25 (short-doc k1/b + bigrams) + cosine on unigram BoW.
    Zero heavy deps; USB / offline friendly.
    """

    def __init__(
        self,
        root: Path | None = None,
        *,
        k1: float = _K1,
        b: float = _B,
        bm25_weight: float = _BM25_WEIGHT,
        cosine_weight: float = _COSINE_WEIGHT,
        min_score: float = _MIN_SCORE,
    ) -> None:
        self.root = Path(root) if root is not None else project_root()
        self.dir = self.root / "data" / "vector"
        self.path = self.dir / "docs.jsonl"
        self.k1 = float(k1)
        self.b = float(b)
        self.bm25_weight = float(bm25_weight)
        self.cosine_weight = float(cosine_weight)
        self.min_score = float(min_score)
        self.embedder_name: str = "bow"
        self._embed_fn: Callable[[str], dict[str, float]] = embed_bow
        self._docs: list[dict[str, Any]] = []
        self.load()

    def set_embedder(
        self,
        name: str | None = None,
        *,
        fn: Callable[[str], dict[str, float]] | None = None,
        reindex: bool = False,
    ) -> dict[str, Any]:
        """
        Switch embedding backend.

        name: bow | char_ngram | hashing (or custom label when fn given)
        fn: optional custom embed callable (plugin / neural model wrapper)
        reindex: recompute stored vecs with the new embedder
        """
        if fn is not None:
            self._embed_fn = fn
            self.embedder_name = (name or "custom").strip() or "custom"
        else:
            key, emb = resolve_backend(name)
            self.embedder_name = key
            self._embed_fn = emb
        n = 0
        if reindex:
            n = self.reindex()
        return {
            "ok": True,
            "embedder": self.embedder_name,
            "reindexed": n,
            "docs": self.count(),
        }

    def reindex(self) -> int:
        """Recompute vec for every stored doc with current embedder."""
        n = 0
        for d in self._docs:
            text = str(d.get("text") or "")
            if not text.strip():
                continue
            d["vec"] = self._embed_fn(text)
            d.setdefault("meta", {})
            if isinstance(d["meta"], dict):
                d["meta"]["embedder"] = self.embedder_name
            n += 1
        if n:
            self.save()
        return n

    def embedder_status(self) -> dict[str, Any]:
        from gnom_hub.memory.embedders import backend_info

        info = backend_info()
        return {
            "active": self.embedder_name,
            "docs": self.count(),
            "backends": info["backends"],
            "default": info["default"],
            "note": info["heavy_models"],
        }

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
        vec = self._embed_fn(text)
        meta_out = dict(meta or {})
        meta_out.setdefault("embedder", self.embedder_name)
        entry = {"id": doc_id, "text": text, "meta": meta_out, "vec": vec}
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
        # Core-key dedupe: one doc per semantic body; keep higher-priority source
        try:
            from gnom_hub.memory.dedupe import core_key, prefer_canonical_wish

            ck = core_key(text)
            if ck:
                rank = {
                    "flex_wish": 3,
                    "flex_personal": 2,
                    "warm": 1,
                    "memory_agent": 1,
                    "requirement": 0,
                }
                new_src = str((meta or {}).get("source") or "").lower()
                new_rank = int(rank.get(new_src, 0))
                for d in self._docs:
                    if core_key(str(d.get("text") or "")) != ck:
                        continue
                    doc_id = str(d.get("id") or "")
                    old_meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
                    old_src = str(old_meta.get("source") or "").lower()
                    old_rank = int(rank.get(old_src, 0))
                    if new_rank > old_rank:
                        # Prefer canonical User: form when upgrading to flex
                        body = prefer_canonical_wish(text) or text
                        return self.upsert(doc_id, body, meta)
                    return doc_id
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
        min_score: float | None = None,
        k1: float | None = None,
        b: float | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid BM25 + cosine; params override store defaults per call."""
        q = (query or "").strip()
        if not q or not self._docs:
            return []
        thr = self.min_score if min_score is None else float(min_score)
        use_k1 = self.k1 if k1 is None else float(k1)
        use_b = self.b if b is None else float(b)

        q_toks = _tokenize(q, drop_stop=True, bigrams=True)
        if not q_toks:
            q_toks = _tokenize(q, drop_stop=False, bigrams=True)
        docs_toks = [
            _tokenize(str(d.get("text") or ""), drop_stop=True, bigrams=True)
            or _tokenize(str(d.get("text") or ""), drop_stop=False, bigrams=True)
            for d in self._docs
        ]
        bm25 = _bm25_scores(q_toks, docs_toks, k1=use_k1, b=use_b)
        max_b = max(bm25) if bm25 else 0.0
        qv = self._embed_fn(q)
        scored: list[tuple[float, dict[str, Any]]] = []
        for i, d in enumerate(self._docs):
            b_raw = bm25[i] if i < len(bm25) else 0.0
            b_norm = (b_raw / max_b) if max_b > 0 else 0.0
            vec = d.get("vec") or {}
            if isinstance(vec, dict) and vec:
                c = _cosine(qv, {str(k): float(v) for k, v in vec.items()})
            else:
                c = _cosine(qv, self._embed_fn(str(d.get("text") or "")))
            hybrid = self.bm25_weight * b_norm + self.cosine_weight * c
            hybrid *= _source_boost(d.get("meta") if isinstance(d.get("meta"), dict) else None)
            scored.append((hybrid, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, d in scored[:limit]:
            if score < thr:
                continue
            vec = d.get("vec")
            has_vec = bool(isinstance(vec, dict) and vec)
            out.append(
                {
                    "id": d.get("id"),
                    "text": d.get("text"),
                    "meta": d.get("meta") or {},
                    "score": round(score, 4),
                    "indexed": has_vec,
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
