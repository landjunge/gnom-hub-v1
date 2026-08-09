#!/usr/bin/env python3
"""
Rank evaluation for VectorStore (hybrid BM25 + cosine).

Gold set: short Flex/WARM facts + token distractors + **phrase distractors**.
Metrics: Precision@1, Precision@3, MRR, source_ok@1, avg margin (top1−top2).

Exit 0 if thresholds met; 1 otherwise.
  python scripts/vector_rank_eval.py
  python scripts/vector_rank_eval.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gnom_hub.memory.vector_store import VectorStore

# Corpus: relevant facts + token distractors + phrase distractors
CORPUS: list[tuple[str, dict]] = [
    ("User: always enable dark theme", {"source": "flex_wish"}),
    ("User: never wipe wishes on clear", {"source": "flex_wish"}),
    ("User: prefers German language answers", {"source": "flex_wish"}),
    ("TTS should read Flex and Brainstorm thoughts", {"source": "flex_wish"}),
    ("Brand is Bean Bloom coffee shop", {"source": "warm"}),
    ("Landing page needs hero and footer", {"source": "requirement"}),
    ("Build checklist app with MVP features only", {"source": "requirement"}),
    ("always use ruff before push", {"source": "requirement"}),
    ("User: always use ruff before push", {"source": "flex_wish"}),
    # token distractors (shared unigrams, not adjacent phrase)
    ("dark room photography tips and theme parks", {"source": "warm"}),
    ("clear the table and wipe the desk now", {"source": "warm"}),
    ("flex muscles workout routine gym", {"source": "warm"}),
    ("bloom flowers garden spring bean salad", {"source": "warm"}),
    ("random noise about weather today sunny clouds", {"source": "warm"}),
    ("completely unrelated zebra astronomy notes", {"source": "warm"}),
    # phrase distractors (same adjacent bigram / phrase, wrong sense)
    ("dark theme parks in germany travel guide", {"source": "warm"}),
    ("language answers without German preference stated", {"source": "warm"}),
    ("always use black formatter before push", {"source": "warm"}),
    ("hero without footer for a landing mock", {"source": "warm"}),
]


@dataclass(frozen=True)
class Case:
    query: str
    """Substring that must appear in a relevant hit (case-insensitive)."""
    needle: str
    """Optional: require winning meta.source."""
    prefer_source: str | None = None
    """Soft tag for reporting (phrase_trap / default)."""
    kind: str = "default"


# Gold queries — needle matches relevant doc text
CASES: list[Case] = [
    Case("dark theme", "always enable dark theme", "flex_wish", "phrase_trap"),
    Case("wipe wishes clear", "never wipe wishes", "flex_wish"),
    Case("German language answers", "German language", "flex_wish", "phrase_trap"),
    Case("TTS Flex thoughts", "TTS should read", "flex_wish"),
    Case("Bean Bloom coffee", "Bean Bloom coffee", "warm"),
    Case("hero footer landing", "Landing page needs hero", "requirement", "phrase_trap"),
    Case("ruff before push", "always use ruff before push", "flex_wish", "phrase_trap"),
    Case("checklist MVP", "checklist app", "requirement"),
]

# Thresholds for short-fact hybrid (defaults must clear these)
MIN_P_AT_1 = 0.85
MIN_MRR = 0.90
MIN_SOURCE_OK = 0.75
MIN_AVG_MARGIN = 0.05  # top1 − top2; soft confidence floor


def _build_store(root: Path) -> VectorStore:
    vs = VectorStore(root)
    for text, meta in CORPUS:
        vs.add(text, meta=meta)
    return vs


def _rank(hits: list[dict], needle: str) -> int | None:
    n = needle.lower()
    for i, h in enumerate(hits, start=1):
        if n in str(h.get("text") or "").lower():
            return i
    return None


def evaluate(
    *,
    k1: float | None = None,
    b: float | None = None,
    limit: int = 5,
) -> dict:
    with tempfile.TemporaryDirectory(prefix="rank_eval_") as td:
        vs = _build_store(Path(td))
        ranks: list[int | None] = []
        margins: list[float] = []
        details: list[dict] = []
        for case in CASES:
            hits = vs.search(case.query, limit=limit, k1=k1, b=b)
            rank = _rank(hits, case.needle)
            top_src = (hits[0].get("meta") or {}).get("source") if hits else None
            top_score = float(hits[0].get("score") or 0) if hits else 0.0
            second = float(hits[1].get("score") or 0) if len(hits) > 1 else 0.0
            margin = top_score - second if hits else 0.0
            margins.append(margin)
            ranks.append(rank)
            details.append(
                {
                    "query": case.query,
                    "needle": case.needle,
                    "kind": case.kind,
                    "rank": rank,
                    "top_text": (hits[0].get("text") if hits else None),
                    "top_source": top_src,
                    "top_score": round(top_score, 4),
                    "margin": round(margin, 4),
                    "prefer_source": case.prefer_source,
                    "source_ok": (
                        case.prefer_source is None
                        or (rank == 1 and top_src == case.prefer_source)
                        or rank is None
                    ),
                }
            )

        n = len(ranks)
        p_at_1 = sum(1 for r in ranks if r == 1) / n if n else 0.0
        p_at_3 = sum(1 for r in ranks if r is not None and r <= 3) / n if n else 0.0
        mrr = sum((1.0 / r) for r in ranks if r) / n if n else 0.0
        source_ok = sum(1 for d in details if d["source_ok"] and d["rank"] == 1) / n if n else 0.0
        avg_margin = sum(margins) / n if n else 0.0
        phrase = [d for d in details if d.get("kind") == "phrase_trap"]
        phrase_p1 = sum(1 for d in phrase if d["rank"] == 1) / len(phrase) if phrase else 1.0

        ok = (
            p_at_1 >= MIN_P_AT_1
            and mrr >= MIN_MRR
            and source_ok >= MIN_SOURCE_OK
            and avg_margin >= MIN_AVG_MARGIN
        )

        return {
            "n": n,
            "p_at_1": round(p_at_1, 4),
            "p_at_3": round(p_at_3, 4),
            "mrr": round(mrr, 4),
            "source_ok_at_1": round(source_ok, 4),
            "avg_margin": round(avg_margin, 4),
            "phrase_trap_p_at_1": round(phrase_p1, 4),
            "phrase_trap_n": len(phrase),
            "min_p_at_1": MIN_P_AT_1,
            "min_mrr": MIN_MRR,
            "min_source_ok": MIN_SOURCE_OK,
            "min_avg_margin": MIN_AVG_MARGIN,
            "pass": ok,
            "details": details,
        }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="VectorStore rank evaluation")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--k1", type=float, default=None)
    p.add_argument("--b", type=float, default=None)
    args = p.parse_args(argv)

    report = evaluate(k1=args.k1, b=args.b)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("vector_rank_eval")
        print(
            f"  n={report['n']}  P@1={report['p_at_1']:.2%}  P@3={report['p_at_3']:.2%}  "
            f"MRR={report['mrr']:.3f}"
        )
        print(
            f"  source_ok@1={report['source_ok_at_1']:.2%}  avg_margin={report['avg_margin']:.3f}  "
            f"phrase_trap P@1={report['phrase_trap_p_at_1']:.2%} (n={report['phrase_trap_n']})"
        )
        print(
            f"  thresholds  P@1>={MIN_P_AT_1:.0%}  MRR>={MIN_MRR:.2f}  "
            f"src_ok>={MIN_SOURCE_OK:.0%}  margin>={MIN_AVG_MARGIN:.2f}  "
            f"→ {'PASS' if report['pass'] else 'FAIL'}"
        )
        fails = [d for d in report["details"] if d["rank"] != 1]
        if fails:
            print("  misses / not top-1:")
            for d in fails:
                print(
                    f"    q={d['query']!r} kind={d.get('kind')} rank={d['rank']} "
                    f"top={d['top_text']!r} margin={d.get('margin')}"
                )
        soft = [
            d
            for d in report["details"]
            if d["rank"] == 1 and d.get("prefer_source") and not d.get("source_ok")
        ]
        if soft:
            print("  source preference misses (counted in source_ok):")
            for d in soft:
                print(f"    q={d['query']!r} top_src={d['top_source']!r} top={d['top_text']!r}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
