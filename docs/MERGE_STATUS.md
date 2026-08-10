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
| [#23](https://github.com/landjunge/gnom-hub-v1/pull/23) | MERGE_STATUS include #22 | **merged** |
| [#24](https://github.com/landjunge/gnom-hub-v1/pull/24) | Vector embedder API/UI closeout | **merged** |

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

## V4 Skills wave (3.10.0)

| Area | Status |
|------|--------|
| Playbook skills + API/UI | shipped this branch |
| Local catalog / install | shipped |
| Neural plugin (optional) | shipped |
| Mobile CSS | shipped |

## 3.10.1 finish

Learned skills S2, orchestration docs, mobile tabs, qa_checklist, telegram skills — see [GITHUB_HOLDER_3.10.md](GITHUB_HOLDER_3.10.md).

## 3.10.x reliability & docs wave (merged)

| PR | Title | Status |
|----|-------|--------|
| [#30](https://github.com/landjunge/gnom-hub-v1/pull/30)–[#33](https://github.com/landjunge/gnom-hub-v1/pull/33) | Neural install path · simple install · mermaid | **merged** |
| [#34](https://github.com/landjunge/gnom-hub-v1/pull/34) | Tauri deferred endgame | **merged** |
| [#35](https://github.com/landjunge/gnom-hub-v1/pull/35) | UI quality polish | **merged** |
| [#36](https://github.com/landjunge/gnom-hub-v1/pull/36)–[#38](https://github.com/landjunge/gnom-hub-v1/pull/38) | README/INDEX search | **merged** |
| [#39](https://github.com/landjunge/gnom-hub-v1/pull/39)–[#40](https://github.com/landjunge/gnom-hub-v1/pull/40) | Memory freshness (HOT+WARM+Vector) | **merged** |
| [#41](https://github.com/landjunge/gnom-hub-v1/pull/41)–[#42](https://github.com/landjunge/gnom-hub-v1/pull/42) | Prefetch why · Clarify Later | **merged** |

Docs: [MEMORY_FRESHNESS.md](MEMORY_FRESHNESS.md) · [PIPELINE_RELIABILITY.md](PIPELINE_RELIABILITY.md) · [INSTALL_SIMPLE.md](INSTALL_SIMPLE.md)
