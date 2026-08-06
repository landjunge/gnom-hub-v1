# Gnom-Hub Architecture (overview)

Short map of the running system. Deep dive: [CODE_ANALYSIS_FOR_AI.md](CODE_ANALYSIS_FOR_AI.md).  
Agent contracts: [AGENTS_DEFINITION.md](AGENTS_DEFINITION.md).

## One sentence

**Brainstorm freely; Execute only on purpose** — fixed eight-agent desk, local FastAPI + SPA, durable memory with Flex wishes protected.

## Runtime shape

```
Browser SPA (static parts → app.js)
       │  REST + job polling
       ▼
FastAPI  →  Hub (composition + mixins)
              ├── EventBus
              ├── Orchestrator (stages)
              ├── 8 role agents (LLM manager)
              ├── Memory HOT / WARM / COLD / Vector
              ├── Workspace · packs · backups · jobs
              └── Computer-use (+ God-Mode dry-run default)
```

## Pipeline stages

```
memory → brainstorm → distill → [clarify] → flex → coordinate → work → done
```

| Mode | What runs |
|------|-----------|
| **Send** | Brainstorm turn + Flex absorb/co-talk; optional auto-Execute |
| **Execute** | Distill → clarify? → Flex briefing + wish inject → plan → workers → quality + Flex nudge |
| **One-shot** | Tests / Telegram `/do` full path |

## Agents (fixed roster)

| Agent | Role | Toggle |
|-------|------|--------|
| Brainstorm | Multi-turn ideas | on |
| Memory | Recall + durable facts | on, locked |
| **Flex** | Fixed proxy: wishes → WARM, co-talk, Execute trigger, nudge | on, **locked** |
| Coordinator | Distill + plan | on |
| Worker 1–4 | Deliverables | 1–2 on; 3–4 toggleable |

Flex details: standing `User:` / `Wish:` facts (`source=flex`), never trimmed before non-flex, injected as `Flex-wish:` into requirements.

## Memory

| Layer | Lifetime | Role |
|-------|----------|------|
| HOT | Session | Messages, session facts |
| WARM | Durable | Long-lived facts; **flex reserve** on trim |
| COLD | Archive | Past sessions |
| Vector | Durable | Hybrid BM25 (88%) + cosine (12%), flex_wish boost |
| Workspace | Artifacts | Temp / permanent after execute |

`pipeline_context` puts **FLEX_WISHES** first with its own budget.

## Plan modes

| Mode | Behavior |
|------|----------|
| `default` | Auto full-page HTML when task looks like a page; else LLM/stub split |
| `full_page_html` | Exactly one worker, one complete HTML file |
| `plan_qa` / `diagnosis` | Deterministic multi-worker templates |

## Quality gates (workers)

HTML: complete `</html>`, real interaction, structure-before-CSS. Soft retries (max 2) on incomplete_html / missing_interaction / gate_fail. Flex `nudge_gaps` after quality notes.

## Testing layers

| Layer | Command |
|-------|---------|
| Unit/integration | `pytest tests/ -q` |
| Fast mutation | `python scripts/mutation_check.py` |
| Vector rank-eval | `python scripts/vector_rank_eval.py` |
| Deep mutmut | `./scripts/run_mutmut.sh` ([MUTMUT.md](MUTMUT.md)) |
| Nightly mutation | GitHub Actions `mutation-nightly.yml` |

## What this is not

- Not a second workflow engine (no Ruffus/Airflow in the hot path)
- Not multiplayer / unattended full autonomy
- Not a cloud lock-in: keys in `Key.txt`, data under `data/`

## Key source paths

| Area | Path |
|------|------|
| Orchestrator | `src/gnom_hub/pipeline/orchestrator.py` |
| Flex / Brainstorm | `src/gnom_hub/agents/roles.py` |
| Coordinator / Workers | `src/gnom_hub/agents/roles_ext.py` |
| Helpers (clarify, flex meta) | `src/gnom_hub/agents/roles_helpers.py` |
| Memory facade | `src/gnom_hub/memory/facade.py` |
| Vector BM25 | `src/gnom_hub/memory/vector_store.py` |
| SQLite WARM | `src/gnom_hub/memory/sqlite_store.py` |
