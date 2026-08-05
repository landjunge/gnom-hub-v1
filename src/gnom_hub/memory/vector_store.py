"""Vector lite: bag-of-words embeddings + cosine (no heavy deps)."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from gnom_hub.config.paths import project_root
from gnom_hub.memory.atomic import atomic_write_text

_TOKEN = re.compile(r"[a-z0-9äöüß]{2,}", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "")]


def _embed(text: str) -> dict[str, float]:
    counts: dict[str, float] = {}
    for t in _tokenize(text):
        counts[t] = counts.get(t, 0.0) + 1.0
    # l2 normalize
    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return {k: v / norm for k, v in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    # iterate smaller
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


class VectorStore:
    """
    data/vector/docs.jsonl — {id, text, meta, vec}
    Hybrid-ish: pure lexical cosine on term vectors (RRF-ready later).
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
        doc_id = f"v{len(self._docs) + 1}"
        return self.upsert(doc_id, text, meta)

    def search(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        qv = _embed(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for d in self._docs:
            vec = d.get("vec") or {}
            if isinstance(vec, dict):
                score = _cosine(qv, {str(k): float(v) for k, v in vec.items()})
            else:
                score = 0.0
            scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, d in scored[:limit]:
            if score <= 0:
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

    def clear(self) -> None:
        self._docs = []
        self.save()
