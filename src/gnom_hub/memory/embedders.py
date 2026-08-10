"""Optional embedding backends for VectorStore (no heavy deps).

Default path stays bag-of-words (bow). Plugins / tools can switch to:
  - bow          — unigram L2 (legacy, USB-friendly)
  - char_ngram   — character 3-grams + light unigrams (typo/phrase robust)
  - hashing      — fixed-dim hashing trick (dense-ish sparse)

True neural models (sentence-transformers, etc.) stay out of core:
install extras yourself and register via VectorStore.set_embedder(...).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Callable
from typing import Any

_TOKEN = re.compile(r"[a-z0-9äöüß]{2,}", re.IGNORECASE)
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

EmbedFn = Callable[[str], dict[str, float]]


def _l2(counts: dict[str, float]) -> dict[str, float]:
    if not counts:
        return {}
    norm = math.sqrt(sum(v * v for v in counts.values())) or 1.0
    return {k: v / norm for k, v in counts.items()}


def embed_bow(text: str) -> dict[str, float]:
    """L2-normalized bag-of-words unigrams (VectorStore default)."""
    counts: dict[str, float] = {}
    for t in _TOKEN.findall(text or ""):
        tl = t.lower()
        if tl in _STOP:
            continue
        counts[tl] = counts.get(tl, 0.0) + 1.0
    return _l2(counts)


def embed_char_ngram(text: str, *, n: int = 3) -> dict[str, float]:
    """
    Char n-grams + sparse unigrams.

    Better than pure BoW for short DE/EN facts with typos / shared stems,
    still pure Python / JSON-serializable sparse dict.
    """
    s = re.sub(r"\s+", " ", (text or "").lower()).strip()
    counts: dict[str, float] = {}
    if len(s) >= n:
        for i in range(len(s) - n + 1):
            g = "c:" + s[i : i + n]
            counts[g] = counts.get(g, 0.0) + 1.0
    for t in _TOKEN.findall(s):
        if t in _STOP:
            continue
        counts["t:" + t] = counts.get("t:" + t, 0.0) + 1.5
    return _l2(counts)


def embed_hashing(text: str, *, dims: int = 128) -> dict[str, float]:
    """Hashing-trick sparse vector (fixed feature space, no vocab growth)."""
    dims = max(16, min(512, int(dims)))
    counts: dict[str, float] = {}
    toks = [t.lower() for t in _TOKEN.findall(text or "") if t.lower() not in _STOP]
    if not toks:
        toks = re.findall(r".{1,3}", (text or "").lower())
    for t in toks:
        h = int(hashlib.md5(t.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % dims
        sign = 1.0 if (h & 1) == 0 else -1.0
        key = f"h{idx}"
        counts[key] = counts.get(key, 0.0) + sign
    return _l2(counts)


BACKENDS: dict[str, EmbedFn] = {
    "bow": embed_bow,
    "char_ngram": embed_char_ngram,
    "hashing": embed_hashing,
}


def resolve_backend(name: str | None) -> tuple[str, EmbedFn]:
    key = (name or "bow").strip().lower() or "bow"
    if key not in BACKENDS:
        raise ValueError(f"unknown embedder backend: {name!r} (want {sorted(BACKENDS)})")
    return key, BACKENDS[key]


def backend_info() -> dict[str, Any]:
    return {
        "backends": sorted(BACKENDS.keys()),
        "default": "bow",
        "heavy_models": "optional — register via VectorStore.set_embedder after installing extras",
    }
