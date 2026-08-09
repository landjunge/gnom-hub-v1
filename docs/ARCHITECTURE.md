# Gnom-Hub Architecture (overview)

Short map of the running system. Deep dive: [CODE_ANALYSIS_FOR_AI.md](CODE_ANALYSIS_FOR_AI.md).  
Agent contracts: [AGENTS_DEFINITION.md](AGENTS_DEFINITION.md).  
README diagrams: [README.md](../README.md) · [README_DE.md](../README_DE.md).

## One sentence

**Brainstorm freely; Execute only on purpose** — fixed eight-agent desk, local FastAPI + SPA, durable memory with Flex wishes protected.

## Runtime shape

```mermaid
flowchart TB
  subgraph Client["Browser SPA"]
    UI["UI · app.js ← parts/*"]
    Badges["LLM · Tools · God · Stage"]
  end

  subgraph API["FastAPI :8080"]
    REST["REST + job polling"]
    Jobs["Async jobs"]
  end

  subgraph Hub["Hub · composition + mixins"]
    Bus["EventBus sync"]
    Orch["Orchestrator"]
    Agents["8 role agents"]
    LLM["LLM manager\nDeepSeek / Ollama · auth"]
    Mem["Memory\nHOT · WARM · COLD · Vector"]
    Tools["ToolRegistry + PluginLoader"]
    WS["Workspace · packs · backups"]
    CU["Computer-use + God-Mode"]
  end

  UI --> REST
  Badges --> REST
  REST --> Jobs
  REST --> Hub
  Jobs --> Orch
  Bus --- Orch
  Orch --> Agents
  Agents --> LLM
  Orch --> Mem
  Orch --> Tools
  Agents --> Tools
  Tools --> WS
  Tools --> CU
  Mem --> WS
```

ASCII (fallback):

```
Browser SPA (static parts → app.js)
       │  REST + job polling
       ▼
FastAPI  →  Hub (composition + mixins)
              ├── EventBus
              ├── Orchestrator (stages)
              ├── 8 role agents (LLM manager)
              ├── Memory HOT / WARM / COLD / Vector
              ├── ToolRegistry + Plugins
              ├── Workspace · packs · backups · jobs
              └── Computer-use (+ God-Mode dry-run default)
```

## Pipeline stages

```mermaid
flowchart LR
  memory --> brainstorm --> distill
  distill --> clarify{clarify?}
  clarify -->|yes| clarify_ui[clarify UI]
  clarify -->|no| flex
  clarify_ui --> flex
  flex --> coordinate --> work --> done
```

```
memory → brainstorm → distill → [clarify] → flex → coordinate → work → done
```

| Mode | What runs |
|------|-----------|
| **Send** | Brainstorm turn + Flex absorb/co-talk; optional auto-Execute |
| **Execute** | Distill → clarify? → Flex briefing + wish inject → plan → **prefetch tools** → workers → quality + Flex nudge |
| **One-shot** | Tests / Telegram `/do` full path |

### Execute path (detail)

```mermaid
sequenceDiagram
  participant U as User
  participant O as Orchestrator
  participant F as Flex
  participant C as Coordinator
  participant P as Prefetch
  participant W as Worker(s)
  participant T as ToolRegistry

  U->>O: Execute
  O->>O: distill requirements
  O->>F: briefing + absolute wishes
  F-->>O: binding_wishes
  O->>C: plan tasks
  C-->>O: worker plan
  O->>P: tool_calls_needed
  P->>T: web_fetch / memory_search / install_tool
  T-->>P: results
  O->>W: run with context + wishes
  W->>T: optional tools
  W-->>O: draft / FEHLER
  O->>O: quality gates · retries
  O->>F: nudge if fixable
  O-->>U: Box 3 + Memory
```

## Agents (fixed roster)

```mermaid
flowchart TB
  subgraph Desk["Fixed desk"]
    B[Brainstorm]
    M[Memory locked]
    F[Flex locked]
    C[Coordinator]
    W1[Worker 1]
    W2[Worker 2]
    W3[Worker 3]
    W4[Worker 4]
  end
  B -->|dialogue| F
  F -->|wishes WARM| M
  C -->|tasks| W1
  C --> W2
  C --> W3
  C --> W4
  F -.->|nudge| W1
  F -.-> W2
```

| Agent | Role | Toggle |
|-------|------|--------|
| Brainstorm | Multi-turn ideas | on |
| Memory | Recall + durable facts | on, locked |
| **Flex** | Fixed proxy: wishes → WARM, co-talk, Execute trigger, nudge | on, **locked** |
| Coordinator | Distill + plan | on |
| Worker 1–4 | Deliverables | 1–2 on; 3–4 toggleable |

Flex details: standing `User:` / `Wish:` facts (`source=flex`), never trimmed before non-flex, injected as absolute orders into worker DoD.

## Memory

```mermaid
flowchart TB
  HOT["HOT · session\nmessages · facts · canvas"]
  WARM["WARM · durable\nfacts · Flex wishes"]
  COLD["COLD · archive"]
  VEC["Vector hybrid\nBM25 + cosine"]
  WORK["Workspace\ntemp · perm"]

  HOT -->|promote| WARM
  HOT -->|archive| COLD
  HOT --> VEC
  WARM --> VEC
  WARM -.->|facts feed| WORK
```

| Layer | Lifetime | Role |
|-------|----------|------|
| HOT | Session | Messages, session facts |
| WARM | Durable | Long-lived facts; **flex reserve** on trim |
| COLD | Archive | Past sessions |
| Vector | Durable | Hybrid BM25 (88%) + cosine (12%), flex_wish boost |
| Workspace | Artifacts | Temp / permanent after execute |

`pipeline_context` puts **FLEX_WISHES** first with its own budget.

## Tools & plugins

```mermaid
flowchart LR
  Core["Core tools\nhub_status · web_fetch · …"]
  Plug["Plugins\necho · install_tool · text_stats"]
  Reg["ToolRegistry"]
  Pref["worker_prefetch"]
  API["POST /api/tools/call"]

  Core --> Reg
  Plug --> Reg
  Pref --> Reg
  API --> Reg
```

## Plan modes

| Mode | Behavior |
|------|----------|
| `default` | Auto full-page HTML when task looks like a page; else LLM/stub split |
| `full_page_html` | Exactly one worker, one complete HTML file |
| `plan_qa` / `diagnosis` | Deterministic multi-worker templates |

## Quality gates (workers)

HTML: complete `</html>`, real interaction, structure-before-CSS. Soft retries (max 2) on incomplete_html / missing_interaction / gate_fail. Flex `nudge_gaps` after quality notes — **skipped** on auth / non-fixable errors.

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
- Not a cloud lock-in: keys in `User/Key.txt`, data under `data/`

## Key source paths

| Area | Path |
|------|------|
| Orchestrator | `src/gnom_hub/pipeline/orchestrator.py` |
| Flex / Brainstorm | `src/gnom_hub/agents/roles.py` |
| Coordinator / Workers | `src/gnom_hub/agents/roles_ext.py` / `roles_workers.py` |
| Helpers (clarify, flex meta) | `src/gnom_hub/agents/roles_helpers.py` |
| Memory facade | `src/gnom_hub/memory/facade.py` |
| Vector BM25 | `src/gnom_hub/memory/vector_store.py` |
| SQLite WARM | `src/gnom_hub/memory/sqlite_store.py` |
| Tool registry | `src/gnom_hub/plugins/registry.py` |
| Plugin loader | `src/gnom_hub/plugins/loader.py` |
| Prefetch | `src/gnom_hub/tools/worker_prefetch.py` |
| Auth keys | `src/gnom_hub/config/keys.py` · `config/auth.py` |
