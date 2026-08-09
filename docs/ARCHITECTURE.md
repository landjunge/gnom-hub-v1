# Gnom-Hub Architecture (overview)

Short map of the running system. Deep dive: [CODE_ANALYSIS_FOR_AI.md](CODE_ANALYSIS_FOR_AI.md).  
Agent contracts: [AGENTS_DEFINITION.md](AGENTS_DEFINITION.md).  
Mermaid style guide + **class palette**: [MERMAID.md](MERMAID.md).  
README diagrams: [README.md](../README.md) · [README_DE.md](../README_DE.md).

## One sentence

**Brainstorm freely; Execute only on purpose** — fixed eight-agent desk, local FastAPI + SPA, durable memory with Flex wishes protected.

## Runtime shape

```mermaid
---
title: Gnom-Hub runtime
config:
  flowchart:
    curve: basis
    padding: 12
---
flowchart TB
  subgraph Client["Browser SPA"]
    direction TB
    UI["UI · app.js ← parts/*"]:::ui
    Badges["LLM · Tools · God · Stage"]:::ui
  end

  subgraph API["FastAPI :8080"]
    direction LR
    REST["REST"]:::ui
    Jobs["Async jobs"]:::ui
  end

  subgraph Hub["Hub · composition + mixins"]
    direction TB
    Bus((EventBus)):::core
    Orch["Orchestrator"]:::core
    Agents["8 role agents"]:::core
    LLM["LLM manager<br/>DeepSeek / Ollama · auth"]:::core
    Mem["Memory<br/>HOT · WARM · COLD · Vector"]:::warm
    Tools["ToolRegistry + PluginLoader"]:::core
    WS["Workspace · packs · backups"]:::store
    CU["Computer-use + God-Mode"]:::danger
  end

  UI --> REST
  Badges --> REST
  REST --> Jobs
  Jobs --> Orch
  REST --> Orch
  Bus <-.->|"sync events"| Orch
  Orch --> Agents
  Agents --> LLM
  Orch --> Mem
  Orch --> Tools
  Agents --> Tools
  Tools --> WS
  Tools --> CU
  Mem --> WS

  classDef ui fill:#1a1f2e,stroke:#5b8def,color:#e6edf3,stroke-width:1px
  classDef core fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
  classDef warm fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
  classDef store fill:#1a2433,stroke:#7c9cbf,color:#e6edf3,stroke-width:1px
  classDef danger fill:#2a1818,stroke:#c45c5c,color:#f5e6e6,stroke-width:2px
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
---
title: Stage machine
---
stateDiagram-v2
  [*] --> memory
  memory --> brainstorm
  brainstorm --> distill: Execute
  brainstorm --> brainstorm: Send turn
  distill --> clarify: needs user
  distill --> flex: clear
  clarify --> flex: answered
  flex --> coordinate
  coordinate --> work
  work --> done: ok
  work --> work: soft retry
  done --> [*]

  note right of brainstorm
    Send stays in dialogue
  end note
  note right of work
    Prefetch tools + quality gates
  end note
```

```mermaid
flowchart LR
  memory([memory]):::terminal --> brainstorm:::core
  brainstorm --> distill:::core
  distill --> clarify{clarify?}:::gate
  clarify -->|yes| clarify_ui[clarify UI]:::ui
  clarify -->|no| flex:::locked
  clarify_ui --> flex
  flex --> coordinate:::core
  coordinate --> work:::work
  work --> done([done]):::terminal

  classDef ui fill:#1a1f2e,stroke:#5b8def,color:#e6edf3,stroke-width:1px
  classDef core fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
  classDef locked fill:#2a2218,stroke:#c9a227,color:#f5f0e6,stroke-width:2px
  classDef work fill:#141c2a,stroke:#6ea8fe,color:#e6edf3,stroke-width:1px
  classDef gate fill:#2a2418,stroke:#d4a017,color:#f5f0e6,stroke-width:1px
  classDef terminal fill:#12151c,stroke:#8b929e,color:#c9cdd4,stroke-width:1px
```

| Mode | What runs |
|------|-----------|
| **Send** | Brainstorm turn + Flex absorb/co-talk; optional auto-Execute |
| **Execute** | Distill → clarify? → Flex briefing + wish inject → plan → **prefetch tools** → workers → quality + Flex nudge |
| **One-shot** | Tests / Telegram `/do` full path |

### Execute path (detail)

```mermaid
---
title: Execute sequence
---
sequenceDiagram
  autonumber
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

  rect rgb(30, 42, 30)
    Note over P,T: core · worker prefetch
    O->>P: tool_calls_needed
    P->>T: web_fetch / memory_search / install_tool
    T-->>P: results
  end

  O->>W: run with context + wishes
  opt worker tools
    W->>T: optional call
    T-->>W: result
  end
  W-->>O: draft or FEHLER

  alt fixable quality gap
    O->>O: quality gates · soft retries
    O->>F: nudge
    F-->>W: correction
  else auth / non-fixable
    rect rgb(42, 24, 24)
      Note over O,U: danger · honest FEHLER
      O-->>U: FEHLER (no fake stub)
    end
  end
  O-->>U: Box 3 + Memory
```

## Agents (fixed roster)

```mermaid
---
title: Fixed desk
---
flowchart TB
  subgraph Desk["8 agents"]
    direction TB
    B[Brainstorm]:::core
    M[Memory locked]:::locked
    F[Flex locked]:::locked
    C[Coordinator]:::core
    subgraph Workers["Workers"]
      direction LR
      W1[W1]:::work
      W2[W2]:::work
      W3[W3]:::work
      W4[W4]:::work
    end
  end

  B -->|"dialogue"| F
  F -->|"wishes → WARM"| M
  C -->|"tasks"| Workers
  F -.->|"nudge"| Workers

  classDef core fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
  classDef locked fill:#2a2218,stroke:#c9a227,color:#f5f0e6,stroke-width:2px
  classDef work fill:#141c2a,stroke:#6ea8fe,color:#e6edf3,stroke-width:1px
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
---
title: Memory layers
---
flowchart TB
  HOT["HOT · session<br/>messages · facts · canvas"]:::hot
  WARM["WARM · durable<br/>facts · Flex wishes"]:::warm
  COLD["COLD · archive"]:::cold
  VEC[("Vector hybrid<br/>BM25 + cosine")]:::store
  WORK["Workspace<br/>temp · perm"]:::store

  HOT -->|"promote"| WARM
  HOT -->|"archive"| COLD
  HOT & WARM --> VEC
  WARM -.->|"facts feed"| WORK

  classDef hot fill:#2a2218,stroke:#c9a227,color:#f5f0e6,stroke-width:1px
  classDef warm fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
  classDef cold fill:#1a1f2e,stroke:#6b7280,color:#c9cdd4,stroke-width:1px
  classDef store fill:#1a2433,stroke:#7c9cbf,color:#e6edf3,stroke-width:1px
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
---
title: Tool surface
---
flowchart LR
  subgraph Sources
    Core["Core tools<br/>hub_status · web_fetch · …"]:::core
    Plug["Plugins<br/>echo · install_tool · text_stats"]:::plugin
  end

  Reg[["ToolRegistry<br/>validate · retry · tags"]]:::core
  Pref["worker_prefetch"]:::work
  API["POST /api/tools/call"]:::ui
  UI["Tools modal"]:::ui

  Core --> Reg
  Plug --> Reg
  Pref --> Reg
  API --> Reg
  UI --> API

  classDef ui fill:#1a1f2e,stroke:#5b8def,color:#e6edf3,stroke-width:1px
  classDef core fill:#1e2a1e,stroke:#3a8f6e,color:#e6edf3,stroke-width:1px
  classDef work fill:#141c2a,stroke:#6ea8fe,color:#e6edf3,stroke-width:1px
  classDef plugin fill:#221a2e,stroke:#9b7ed9,color:#efe6f5,stroke-width:1px
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
