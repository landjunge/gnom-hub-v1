# Gnom-Hub — exact architecture overview

Companion to [ARCHITECTURE.md](ARCHITECTURE.md) (runtime diagrams) and
[CODE_ANALYSIS_FOR_AI.md](CODE_ANALYSIS_FOR_AI.md) (deep dive).

## One sentence

**Brainstorm freely; Execute only on purpose** — fixed 8-agent desk, local FastAPI + SPA,
memory tiers HOT / WARM / COLD + Vector, plugins as tools, no second orchestrator.

## Layers (top → bottom)

| Layer | What | Code |
|-------|------|------|
| **Browser SPA** | 3 boxes, jobs poll, Tools/System modals | `ui/static/parts/*` → `app.js` |
| **HTTP API** | REST + async jobs + MCP-lite | `api/app.py` |
| **Hub** | Composition root + mixins | `hub.py` + `*_ops.py` |
| **Pipeline** | Stages: brainstorm → distill → flex → coordinate → work → quality | `pipeline/orchestrator.py` |
| **Agents** | 8 fixed roles | `agents/roles*.py` |
| **LLM** | DeepSeek + Ollama | `llm/manager.py` |
| **Memory** | HOT · WARM · COLD · Vector | `memory/*` |
| **Tools** | Core registry + plugins | `plugins/*`, `tools/*` |
| **Data** | USB-portable files under `data/` | jsonl / packs / workspace |

## Pipeline stages

```
chat (brainstorm*) ──► Execute ──► distill → flex → coordinate → workers → quality → done
                         │
                         ├─ tool_drill short-circuit
                         ├─ browser_nav short-circuit
                         └─ plan_mode: default | full_page_html | team | plan_qa | diagnosis
```

**Coordinate quality (3.9.1):** weighted `_html_page_score` ≥ 3 → deterministic
`full_page_html` (one worker). LLM multi-worker HTML only if `plan_mode=team`.

## Eight agents (fixed)

| Agent | Job |
|-------|-----|
| Brainstorm | Multi-turn dialogue partner |
| Memory | Facts → WARM / vector |
| Flex | Personal wishes / quality nudges (not a designer) |
| Coordinator | Plan workers (or fast-path HTML) |
| Worker 1–4 | Deliverables + TOOL_CALL tools |

## Memory tiers (HOT / WARM / COLD)

| Tier | Durability | Path | Role |
|------|------------|------|------|
| **HOT** | Session | `data/hot/` | Current dialogue, canvas, short facts |
| **WARM** | Durable wishes/facts | `data/warm/` | Survives reset; Flex wishes protected |
| **COLD** | Archives | `data/cold/` | Snapshots on reset/clean |
| **Vector** | Search index | `data/vector/docs.jsonl` | Hybrid BM25 + embedder cosine |
| **Workspace** | Files | `data/workspace/` | Worker HTML / temp / exports |

Facade `pipeline_context()` merges Flex wishes + WARM + HOT + vector hits (garbage filtered).

### Vector embedders

Default **bow**. Optional backends via plugin `embeddings_lite` (`char_ngram`, `hashing`).
See [PLUGINS.md](PLUGINS.md).

## Jobs & cancel

- Async jobs hold `_pipeline_lock`; one active pipeline job
- Soft cancel: `job.cancel` → cooperative `cancel_check` between stages/workers
- Tool loops only honor cancel when `_active_job_id` is set (no sticky cancel)

## Plugins & tools

- Core tools always registered
- Drop-in `plugins/<id>/` discovered at boot / reload
- Workers call tools with `TOOL_CALL name={...}` text protocol
- God-Mode gates real shell / computer-use

## Freeze constraints (do not regress)

- No second workflow engine / second orchestrator
- No auto-execute by default (desk exceptions documented in AGENTS.md)
- No skill marketplace as core (drop-in plugins only)
- No heavy embedding deps in core

## Version

`gnom_hub.__version__` (single source) — currently **3.9.1**.  
Notes: [CHANGELOG_3.9.md](CHANGELOG_3.9.md).

## Next (V4)

Skills / marketplace / neural embeddings / mobile — design only: [V4_PLAN.md](V4_PLAN.md).
