"""Multi-layer memory search: HOT + WARM lexical (sync) + Vector hybrid.

Fresh content is immediately keyword-findable even before promotion/indexing.
Vector hits carry ``indexed: true`` when a stored embedding exists.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

_WORD = re.compile(r"[a-z0-9äöüß_]{2,}", re.IGNORECASE)


class _FactSource(Protocol):
    def all_facts(self) -> list[str]: ...


def _tokens(text: str) -> set[str]:
    # Split snake_case / compound identifiers so UNIQUE_FRESH_FACT matches.
    raw = (text or "").replace("_", " ").replace("-", " ")
    return {m.group(0).lower() for m in _WORD.finditer(raw)}


def lexical_score(query: str, text: str) -> float:
    """Cheap overlap score in [0, 1] for HOT/WARM sync search."""
    q = (query or "").strip().lower()
    t = (text or "").strip().lower()
    if not q or not t:
        return 0.0
    if q in t:
        return min(1.0, 0.72 + min(0.28, len(q) / max(40.0, len(t))))
    qt = _tokens(q)
    tt = _tokens(t)
    if not qt:
        return 0.0
    if not tt:
        # fallback: char containment of query words
        words = [w for w in q.split() if len(w) >= 3]
        if not words:
            return 0.0
        hit = sum(1 for w in words if w in t)
        return hit / len(words) if hit else 0.0
    inter = len(qt & tt)
    # substring soft match (unique_fresh in unique_fresh_fact_…)
    if inter == 0:
        soft = 0
        for a in qt:
            if any(a in b or b in a for b in tt if min(len(a), len(b)) >= 4):
                soft += 1
        if soft:
            return min(0.9, soft / len(qt) * 0.75)
        # raw containment of tokens
        soft2 = sum(1 for a in qt if a in t)
        if soft2:
            return min(0.85, soft2 / len(qt) * 0.7)
        return 0.0
    return min(1.0, (inter / len(qt)) * 0.85 + (inter / max(1, len(tt))) * 0.15)


def search_layers(
    *,
    query: str,
    hot: _FactSource | None = None,
    warm: _FactSource | None = None,
    vectors: Any | None = None,
    limit: int = 8,
    include_hot: bool = True,
    include_warm: bool = True,
    include_vector: bool = True,
) -> list[dict[str, Any]]:
    """Unified search across HOT → WARM → Vector.

    Returns hits sorted by score (desc). Each hit:
      text, score, layer (hot|warm|vector), indexed (bool), id?, meta?
    """
    q = (query or "").strip()
    if not q:
        return []
    lim = max(1, min(40, int(limit)))
    scored: list[tuple[float, dict[str, Any]]] = []

    if include_hot and hot is not None:
        try:
            facts = list(hot.all_facts() or [])
        except Exception:  # noqa: BLE001
            facts = []
        for i, f in enumerate(facts):
            sc = lexical_score(q, f)
            if sc <= 0:
                continue
            scored.append(
                (
                    sc * 1.05,  # slight bias: session HOT is freshest
                    {
                        "id": f"hot:{i}",
                        "text": f,
                        "score": round(sc * 1.05, 4),
                        "layer": "hot",
                        "indexed": False,
                        "meta": {"source": "hot", "fresh": True},
                    },
                )
            )

    if include_warm and warm is not None:
        try:
            facts = list(warm.all_facts() or [])
        except Exception:  # noqa: BLE001
            facts = []
        for i, f in enumerate(facts):
            sc = lexical_score(q, f)
            if sc <= 0:
                continue
            scored.append(
                (
                    sc,
                    {
                        "id": f"warm:{i}",
                        "text": f,
                        "score": round(sc, 4),
                        "layer": "warm",
                        "indexed": False,  # may also appear as vector
                        "meta": {"source": "warm", "fresh": True},
                    },
                )
            )

    if include_vector and vectors is not None and hasattr(vectors, "search"):
        try:
            vhits = vectors.search(q, limit=lim)
        except Exception:  # noqa: BLE001
            vhits = []
        for h in vhits or []:
            if not isinstance(h, dict):
                continue
            text = str(h.get("text") or "")
            meta = h.get("meta") if isinstance(h.get("meta"), dict) else {}
            # indexed: stored embedding present (check via get if possible)
            indexed = True
            doc_id = str(h.get("id") or "")
            if hasattr(vectors, "_docs"):
                for d in getattr(vectors, "_docs", []) or []:
                    if str(d.get("id") or "") == doc_id:
                        vec = d.get("vec")
                        indexed = bool(isinstance(vec, dict) and vec)
                        break
            sc = float(h.get("score") or 0)
            scored.append(
                (
                    sc + 0.02,  # tiny boost for hybrid path when scores comparable
                    {
                        "id": h.get("id"),
                        "text": text,
                        "score": round(sc, 4),
                        "layer": "vector",
                        "indexed": indexed,
                        "meta": {**meta, "fresh": False},
                    },
                )
            )

    # Dedupe by core-ish text, keep best score
    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _sc, hit in scored:
        key = " ".join(str(hit.get("text") or "").lower().split())[:160]
        if not key or key in seen:
            # Prefer vector hit if same text — merge indexed flag
            if key and out:
                for prev in out:
                    pk = " ".join(str(prev.get("text") or "").lower().split())[:160]
                    if pk == key:
                        if hit.get("indexed"):
                            prev["indexed"] = True
                        layers = prev.setdefault("layers", [prev.get("layer")])
                        if hit.get("layer") not in layers:
                            layers.append(hit.get("layer"))
                        break
            continue
        seen.add(key)
        hit = dict(hit)
        hit["layers"] = [hit.get("layer")]
        out.append(hit)
        if len(out) >= lim:
            break
    return out
