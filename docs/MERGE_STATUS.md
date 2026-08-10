# Merge status — Gnom-Hub improvement wave (2026-08-10)

All listed PRs are **merged into `main`**. Open PRs: none from this wave.

| PR | Title | Status |
|----|-------|--------|
| [#13](https://github.com/landjunge/gnom-hub-v1/pull/13) | Scoring heuristic for full_page_html | **merged** |
| [#14](https://github.com/landjunge/gnom-hub-v1/pull/14) | Export pin race-hardening + plan score UI/docs | **merged** |
| [#15](https://github.com/landjunge/gnom-hub-v1/pull/15) | Clear plan_html_score on execute start | **merged** |
| [#16](https://github.com/landjunge/gnom-hub-v1/pull/16) | v3.9.1 + plugin disk discovery + version single source | **merged** |
| [#17](https://github.com/landjunge/gnom-hub-v1/pull/17) | Non-sticky cancel_check + pack deep-copy | **merged** |
| [#18](https://github.com/landjunge/gnom-hub-v1/pull/18) | Isolate tool-loop cancel from idle hub | **merged** |
| [#19](https://github.com/landjunge/gnom-hub-v1/pull/19) | Tool-loop cancel isolation (CI flake) | **merged** |
| [#20](https://github.com/landjunge/gnom-hub-v1/pull/20) | Richer DE page scoring, plugin docs, cancel hygiene | **merged** |
| [#21](https://github.com/landjunge/gnom-hub-v1/pull/21) | Plan-mode toast + 3.9 changelog | **merged** |
| [#22](https://github.com/landjunge/gnom-hub-v1/pull/22) | Embeddings plugin + PLUGINS/HUB/MERGE docs | **merged** |

## Delivered in #22

| Area | Deliverable |
|------|-------------|
| Embeddings | Pluggable VectorStore embedders + `embeddings_lite` plugin |
| Plugin details | [PLUGINS.md](PLUGINS.md) catalog |
| Hub architecture | [HUB_ARCHITECTURE.md](HUB_ARCHITECTURE.md) exact overview |
| Merge status | This file |

## CI note

Python matrix (3.10 / 3.11 / 3.12) is the gate. Vercel preview may fail (Python desk app — expected).

## Verify on main

```bash
git checkout main && git pull
PYTHONPATH=src pytest tests/ -q
python scripts/vector_rank_eval.py
```

## Wave closeout

Desk improvement wave **complete** for freeze-conform work:

- Coordinator scoring + observability
- Plugin disk discovery + catalog
- Embeddings lite (no heavy deps) + Vector UI/API switch
- Hub architecture + merge status docs
- Cancel / export race hygiene

Still optional (not blocking): neural embeddings package, live E2E with keys, skill marketplace, auto-update, mobile UI.
