# Gnom-Hub v1 — Detailed Code Analysis (for external AI readers)

**Purpose:** Hand this document to another AI so it can reason about the codebase without rediscovering architecture, product rules, or past failure modes.

| Field | Value |
|-------|--------|
| **Repo** | `gnom-hub-v1` (private local multi-agent hub) |
| **Package** | `gnom_hub` under `src/` |
| **Version** | **3.7.1** (`pyproject.toml`, `src/gnom_hub/__init__.py`) |
| **HEAD (at write time)** | structural repair Phases A–G (hub extract + UI parts) |
| **Python** | ≥3.10 |
| **Default UI** | `http://127.0.0.1:8080/` |
| **Stack** | FastAPI + uvicorn · desktop SPA (`app.js` from `parts/*` · `app.css` · `index.html`) · optional DeepSeek / Ollama |
| **License** | Private use |
| **LOC (approx.)** | ~10k Python · ~4.7k `app.js` (6 parts) · hub façade ~1.5k |

---

## 1. Product identity (non-negotiable)

Gnom is **not** “chat → tools → chaos”. Core product rule:

> **Brainstorm freely. Execute only when the user says so.**

Pipeline target (from `AGENTS.md`):

```
Chat → Brainstorm → Distillation → [Execute] → Coordinator → Worker(s) → Box 3 + Memory
```

### Product constraints the code must honor

1. **No auto-execute** after brainstorm. Separate `Send` vs `Execute` buttons.
2. **Memory is always on** (agent not toggleable).
3. **Worker 3/4 default off**; worker 1–2 on.
4. **Presets freeze:** team presets + worker presets + `plan_mode` only.  
   **No** workflow engine, skill marketplace, or second orchestrator (`docs/WORKFLOWS_AND_PRESETS.md`).
5. **YAGNI + KISS** — user repeatedly rejected UI chrome / overengineering.
6. **One global Save** button; language Basic English UI, Box 1 multi-language ready.
7. **Full-page HTML deliverable = one worker only** (not 4 parallel half-pages).

---

## 2. Repository layout

```
gnom-hub-v1/
├── AGENTS.md                 # Coding rules for human/AI agents working in this repo
├── README.md / README_DE.md  # Product docs (EN/DE)
├── Key.txt / Key.txt.example # Local secrets (never commit real keys)
├── pyproject.toml            # package, ruff, pytest, optional [computer]
├── scripts/                  # start, smoke, e2e, quality_check, basic_tests
├── docs/                     # scope, stability, keys, roadmap, this analysis
├── data/                     # runtime state (hot/warm/cold/workspace/vector/…)
├── plugins/                  # optional plugin folders
├── tests/                    # pytest (pythonpath=src)
└── src/gnom_hub/
    ├── main.py               # CLI: --smoke | HTTP server
    ├── hub.py                # ★ composition root (~3200 LOC)
    ├── api/app.py            # FastAPI routes + static mount
    ├── core/event_bus.py     # sync pub/sub
    ├── agents/               # roster + role implementations
    ├── pipeline/             # orchestrator + stages
    ├── memory/               # HOT/WARM/COLD/vector/workspace
    ├── llm/                  # DeepSeek + Ollama manager
    ├── computer_use/         # screenshot/click/type/shell (God-Mode)
    ├── security/god_mode.py
    ├── tools/ + plugins/
    ├── telegram/
    ├── config/               # keys, project_root paths
    └── ui/static/            # SPA
```

### LOC by area (Python)

| Area | ~LOC | Role |
|------|------|------|
| `hub.py` | ~1520 | Façade + wiring (mixins for bulk) |
| `telegram/commands.py` | ~690 | Telegram slash commands (mixin) |
| `session_pack.py` | ~560 | Session pack export/import (mixin) |
| `backup_ops.py` | ~150 | Backup zip ops (mixin) |
| `jobs.py` | ~260 | Async job runner (mixin) |
| `memory/wiring.py` | ~90 | Bus → HOT/WARM handlers (mixin) |
| `ui/static/parts/*` + `app.js` | ~4.7k | Desktop UI (edit parts → `build_ui_js.py`) |
| `pipeline/` | 1460 | Orchestrator, gates, DoD |
| `agents/` | 1158 | Roles + helpers |
| `api/app.py` | 877 | Thin HTTP over Hub methods |
| `llm/` | 593 | Clients + budget |

**Hub shape:** `Hub(TelegramCommandMixin, BackupOpsMixin, SessionPackMixin, JobsMixin, MemoryWiringMixin)`. Public API method names stay on Hub; bulk lives in mixins. Prefer thin API → Hub → mixin/module; no second orchestrator.

---

## 3. Runtime architecture

```
Browser SPA (app.js)
    │  REST + job polling
    ▼
FastAPI (api/app.py)  ──get_hub()──►  Hub singleton
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              EventBus              Orchestrator          MemoryFacade
           (sync emit/on)        (pipeline stages)     (HOT+WARM+vector)
                    │                    │
                    ▼                    ▼
              AgentManager          Role agents
           (AgentState roster)   (Brainstorm, Memory,
                                  Flex, Coordinator,
                                  Worker1–4)
                                         │
                                         ▼
                                    LLMManager
                                 (DeepSeek / Ollama)
```

### Boot path

1. `python -m gnom_hub.main` → `uvicorn` → `gnom_hub.api.app:app`
2. First request / module load constructs `Hub()` once via `get_hub()`
3. `Hub.__init__`:
   - `EventBus`, `AgentManager`, `LLMManager`, memory stores, workspace, cold, vector
   - **Scrubs** HOT facts + vector garbage on boot (post `27c2e58`)
   - Computer-use kit + tool registry + plugins
   - New pipeline, load agent state, apply `Key.txt`, enable core agents
   - `_wire_memory()` + `_wire_trace()`
4. Static UI at `/` from `ui/static/`

### Process model

- **Sync** endpoints for tests/smoke.
- **Async jobs** for UI chat/execute: Hub starts a thread, returns `job_id`; UI polls `/api/jobs/{id}`.
- Soft-cancel via `job["cancel"]` flag + `orchestrator.cancel_check`.
- Cooperative cancel between stages/workers (`PipelineCancelled`).

---

## 4. EventBus

**File:** `src/gnom_hub/core/event_bus.py`  
Simple synchronous `on` / `off` / `emit`. No async, no persistence.

### Important events

| Event | Emitter | Consumers |
|-------|---------|-----------|
| `pipeline.stage` | Orchestrator | UI pulse (agent cards), job status |
| `pipeline.brainstorm` | Orchestrator | UI Box 2 |
| `pipeline.brainstorm_ready` | Orchestrator | enables Execute |
| `pipeline.distill` / `flex` / `coordinate` / `worker` | Orchestrator | UI + trace |
| `pipeline.question` | Orchestrator | Box 1 clarify |
| `pipeline.quality` | Orchestrator | internal notes (not Box 3 chrome) |
| `pipeline.memory_hint` | MemoryAgent.store | Hub → HOT messages + requirement facts |
| `pipeline.memory_curated` | MemoryAgent.store | Hub → HOT+WARM durable facts |
| `pipeline.done` / `error` / `cancelled` | Orchestrator | Hub job finalize |
| `agent.activity` | BaseAgent | UI pulse |
| `agent.status` | Manager | UI cards |

**UI mapping note:** stage `worker1`…`worker4` (not only generic `work`) so only the active worker card pulses.

---

## 5. Agents

### 5.1 Roster (`agents/models.py`, `agents/manager.py`)

| AgentId | Color | Toggleable | Default |
|---------|-------|------------|---------|
| brainstorm | red | yes | on |
| memory | blue | **no** (locked) | on |
| flex | yellow | yes | on (preset: security) |
| coordinator | green | yes | on |
| worker1 | orange | yes | on |
| worker2 | purple | yes | on |
| worker3 | teal | yes | **off** |
| worker4 | gray | yes | **off** |

Flex presets: `security` | `neutral` | `researcher`.

Per-agent: model, api_key, system_prompt, temperature, top_p, max_tokens, penalties, TTS flag.  
Persisted under `data/hot/agents.json`.

### 5.2 BaseAgent (`agents/base.py`)

- Wraps `AgentState` + bus + optional LLM.
- `ask(system, user, …)` routes through `LLMManager` with agent id for usage tracking.
- `has_llm()`, `emit_active(True/False)`, stubs when no key.

### 5.3 Role implementations

| Class | File | Responsibility |
|-------|------|----------------|
| `BrainstormAgent` | `roles.py` | Multi-turn dialogue; prior messages; memory-sanitized context |
| `FlexAgent` | `roles.py` | Security/neutral/researcher review of requirements |
| `CoordinatorAgent` | `roles_ext.py` | Distill requirements; optional clarify question; **plan** worker tasks |
| `WorkerAgent` | `roles_ext.py` | Produce deliverable text/HTML for one task |
| `MemoryAgent` | `roles_ext.py` | `recall()` + `store()` (curate facts; does not write disk itself) |

Shared helpers: `agents/roles_helpers.py`

- `_with_memory` / `_sanitize_memory_ctx` — inject only clean memory lines
- `_is_garbage_fact` — hard reject HTML, meta, pipeline chatter, known hallucination loops
- brainstorm history formatters, clarify heuristic

### 5.4 Coordinator plan modes (`plan_mode`)

Set via Hub/API/team presets. Whitelist only:

| Mode | Behavior |
|------|----------|
| `default` | LLM plan lines `workerN \| task`, else simple multi-worker templates |
| `full_page_html` | **Exactly one worker** builds complete single-file HTML (`_html_full_page_plan`) |
| `plan_qa` | Deterministic QA-style task templates |
| `diagnosis` | Deterministic diagnosis templates |

Auto-detection: if user text matches `_wants_one_html_page` (html/landing/seite/page/…), coordinator forces single-worker HTML plan even in default flow paths that call that helper.

**Past bug:** multi-worker all writing incomplete pages + Execute using last chat turn (“mann nicht du die worker”).  
**Fix:** `_pick_execute_task` prefers long / page-like user turns; one-worker HTML plan.

---

## 6. Pipeline / Orchestrator

**Files:** `pipeline/orchestrator.py`, `pipeline/models.py`, `pipeline/pipeline.py` (thin re-export/alias)

### Stages (`PipelineStage`)

`idle → brainstorm → distill → [clarify] → flex → coordinate → work → done | error`

Also emitted mid-work: `worker1`…`worker4` for UI.

### Entry points

| Method | Use |
|--------|-----|
| `brainstorm_turn(text)` | Default UX: one dialogue turn; no workers |
| `execute()` | Distill → flex → plan → workers → memory store |
| `answer_clarify(option)` | Resume after Box 1 question |
| `start(text)` | Full one-shot (tests / Telegram `/do`) |
| `rerun_worker(id)` | Re-run one worker’s last task |

### Execute critical path (`execute` → `_run_flex_coord_workers` → `_finish`)

1. Resolve task text via `_pick_execute_task(brainstorm_turns)`
2. Clear sticky error / old worker outputs
3. `memory.recall(task)` → `memory_context`
4. Coordinator `distill` → requirements; maybe `clarify` and return
5. Flex review (appends `Flex/{preset}: …` line to requirements)
6. Coordinator `plan(worker_ids, plan_mode=…)`
7. Optional URL prefetch (`web_fetch`) into memory context
8. Append **Definition of Done** block to each worker task
9. For each task: run worker; soft-retry incomplete HTML; validate gate; emit `pipeline.worker`
10. `_quality_check` → `quality_notes` (internal)
11. `_finish` → `MemoryAgent.store` → `pipeline.done`

### Quality / gates (orchestrator bottom)

- `_definition_of_done` — binding checklist text on every worker task
- `_validate_worker_draft` — HTML completeness, interaction, CSS-without-JS, etc.
- Soft retries for incomplete HTML / missing interaction
- `_quality_check` — aggregates gate issues (emitted as `pipeline.quality`; **not** shown as Box 3 chrome after declutter)

### Topic switch (`_is_topic_switch`)

If user message is clearly a new topic vs prior brainstorm turns, dialogue restarts instead of continuing polluted context.

---

## 7. Memory system (HOT / WARM / COLD / Vector)

**Facade:** `memory/facade.py` — `pipeline_context()` merges WARM + HOT + vector hits for query hint.

### Layers

| Layer | Path | Lifetime | Content |
|-------|------|----------|---------|
| **HOT** | `data/hot/session.json` + `mermaid_canvas.mmd` | Session | messages, facts, canvas nodes |
| **Offload** | `data/offload/n*.txt` | Session | long texts replaced by stubs |
| **WARM** | `data/warm/facts.jsonl` | Durable | long-lived facts (survives HOT clear) |
| **COLD** | `data/cold/sessions/{id}/` | Archive | archived HOT sessions |
| **Vector** | `data/vector/docs.jsonl` | Durable | bag-of-words cosine “embeddings” (no heavy deps) |
| **Workspace** | `data/workspace/{temp,perm,exports}` | Artifacts | auto-capture after execute |

### Write path (important)

```
MemoryAgent.store()
  → emit pipeline.memory_hint
       Hub.on_memory_hint:
         HOT messages (user/brainstorm/flex)
         HOT facts from clean requirements
         WARM if "Ziel:"/"Goal:" requirement
         worker notes (truncated, no code fences)
  → LLM extract 0–3 durable facts
  → emit pipeline.memory_curated
       Hub.on_memory_curated:
         HOT + WARM + vector (if passes _is_garbage_fact)
  → on pipeline.done: scrub_facts + compress_if_needed
```

### Garbage protection (`_is_garbage_fact`) — commit `27c2e58`

Rejects:

- HTML/code dumps (`<!DOCTYPE`, tags, fenced html)
- Empty meta (`(none)`, `(no durable facts…)`)
- Pipeline meta (`worker produced`, truncation, B1 tests…)
- Known notes-app hallucination loop strings
- Markdown chrome (`## Requirements`, `Today** – …`)

Applied at: `warm.add_fact`, `hot.add_fact`, load scrub, vector `add`/`scrub`, facade context, recall sanitize.

**Clean / Reset:** HOT + temp workspace + pipeline cleared; **WARM kept** by default.

### Historical failure mode

WARM filled with HTML lines, test artifacts, and mixed projects → polluted every new brainstorm. Fixed by filters + one-time scrub/clear of polluted stores.

---

## 8. Hub (composition root)

**File:** `src/gnom_hub/hub.py`

Responsibilities (not exhaustive):

- Construct all subsystems
- `snapshot()` — single payload for UI (`/api/state`)
- `chat` / `chat_async`, `execute_sync` / `execute_async`
- Jobs dict + cancel + list
- Memory CRUD helpers (hot/warm promote)
- Backup zip, session packs (USB portable)
- Checkpoint save/load
- Cold archive/restore
- Workspace capture after execute
- Export last execute (`_last_execute_export` survives reset)
- God-mode toggle → computer kit
- Telegram command dispatch (`/hot`, `/warm`, `/ws`, `/do`, …)
- Worker/team presets + `plan_mode` sync
- Trace ring buffer
- Usage / budget exposure from LLMManager

**API layer** (`api/app.py`) should stay thin: parse body → call Hub → return dict.

---

## 9. LLM layer

| File | Role |
|------|------|
| `llm/manager.py` | Routing, free_only, budget USD, per-agent usage |
| `llm/deepseek.py` | OpenAI-compatible client; default model **`deepseek-v4-flash`** |
| `llm/ollama.py` | Local models via `ollama/` prefix |
| `llm/types.py` | `LLMMessage`, `LLMResult`, budget/key errors |

### Keys (`config/keys.py` + `Key.txt`)

Documented in `docs/KEYS_AND_MODELS.md`:

- `DEEPSEEK_API_KEY` / system key → brainstorm, memory, flex, coordinator
- `WORKER_API_KEY` → workers
- `DEEPSEEK_MODEL` default `deepseek-v4-flash`
- **Thinking off by default** (`DEEPSEEK_THINKING=0`) — empty content bug with thinking mode

Without keys: stub responses so pipeline still reaches `done` for tests.

Env guards:

- `GNOM_FREE_ONLY=1` — block paid models
- `GNOM_MAX_BUDGET_USD` — hard stop

---

## 10. UI (SPA)

**Files:** `ui/static/index.html`, `app.css`, `app.js` (~4.7k LOC, built from `parts/00`–`05`)

### Layout

1. **Top bar:** badges (LLM, $, Mem, Vec, God, Cold, stage), Workspace/Tools/Trace/Export, System/Help/Archive/Reset/Save  
2. **Agent cards row** (8) — color frames, online, tokens, TTS checkbox  
3. **Three boxes:**  
   - **Box 1** — Arounder / clarify / tooltips (not agent dump)  
   - **Box 2** — Brainstorm dialogue  
   - **Box 3** — Worker results: **Preview / Source / Copy only** (no quality strip, no HOT strip, no action-bar experiments)  
4. **Chat bar:** Mic · input · Send · Execute · Send+Exec  

### UI rules learned the hard way

- Do **not** reintroduce floating action bars or absolute iframe layouts that break flex boxes.
- TTS: `speechSynthesis` must start in a **user gesture**; speaking after `await` fails in Chrome — queue + speak on checkbox/gesture.
- Pulse: only agent matching stage id (worker-specific stages).
- Execute re-enable: after brainstorm job ends, re-apply `can_execute` when `chatBusy` clears (`lastCanExecute`) — regression fixed in 3.7.1.
- Poll jobs until `done`/`error`/`cancelled`; apply snapshot repeatedly.

### System modal

HOT/WARM fact lists, promote, clear; language; backup/clean; checkpoint; etc.

---

## 11. Computer use & tools

### God-Mode (`security/god_mode.py`)

Without God-Mode: dry-run only. With God-Mode + deps: real mouse/keyboard/shell.

### Computer-use package

| Module | Role |
|--------|------|
| `capture.py` | Screenshot via **mss** first, Pillow fallback |
| `action.py` | click, type (pyautogui) |
| `ocr.py` | pytesseract optional |
| `workflow.py` | higher-level flows |
| API | `/api/computer-use/*`, Tools modal in UI |

Optional install: `pip install -e ".[computer]"`

### Tools / plugins

- `ToolRegistry` + `PluginLoader` under `plugins/`
- Core tools: `hub_status`, `memory_search`, `pipeline_do`, `web_fetch`
- `web_fetch`: public HTTP only; blocks private IPs unless `GNOM_WEB_ALLOW_LOCAL=1`

Portfolio notes: `docs/TOOLS_PORTFOLIO.md`

---

## 12. Data directory contract

```
data/
  hot/           session.json, mermaid_canvas.mmd, agents.json, checkpoint, presets
  warm/          facts.jsonl
  cold/          index.jsonl + sessions/{id}/
  vector/        docs.jsonl
  offload/       n1.txt …
  workspace/     temp/ perm/ exports/
  packs/         portable session packs
  backups/       zip backups
  computer_use/  last screenshot etc.
```

All paths relative via `config/paths.project_root()` — USB-portable design.

Atomic writes: `memory/atomic.py` (write temp + replace).

---

## 13. API surface (summary)

Health/state: `GET /api/health`, `/api/state`, `/api/agents`, `/api/system`  
Chat pipeline: `POST /api/chat`, `/api/execute`, `/api/clarify`, jobs + cancel  
Memory: `/api/memory`, hot/warm CRUD + promote/clear  
Workspace, cold, vector, backups, packs  
Presets: worker + team + `POST /api/plan-mode`  
Computer-use + god-mode  
Telegram inbound/start/stop  
Static: `GET /`

Full list generated from `api/app.py` decorators — ~90 routes; most map 1:1 to Hub methods.

---

## 14. Tests & quality gates

| Command | Purpose |
|---------|---------|
| `ruff check .` + `ruff format .` | Mandatory before commit (`AGENTS.md`) |
| `pytest tests/ -q` | Unit/API (pythonpath=src) |
| `python -m gnom_hub.main --smoke` | Brainstorm→execute without UI |
| `scripts/quality_check.sh` | Stability track |
| `scripts/basic_tests.py` | B1–B3 when server up |
| `scripts/user_landing_e2e.py` | Playwright real landing-page user path |

**Never commit:** `Key.txt` with real keys, `.env` secrets.

Commit style: `feat(…):` / `fix:` / `docs:` — push to `origin/main` after each completed step (project convention).

---

## 15. Known pitfalls / do-not-regress list

1. **Execute disabled after brainstorm** — busy flag must restore `can_execute`.  
2. **Multi-worker HTML mess** — one full page → one worker (`full_page_html` / `_wants_one_html_page`).  
3. **Execute task = last short chat reply** — use `_pick_execute_task`.  
4. **Memory stores HTML** — always pass `_is_garbage_fact`; never feed raw worker HTML into WARM.  
5. **Quality strip / HOT strip / action bars in boxes** — user-rejected; do not re-add.  
6. **TTS after await** — speak in gesture context.  
7. **All workers pulse on `work`** — emit per-worker stage ids.  
8. **Sticky pipeline.error** — clear on execute / `_finish`.  
9. **DeepSeek thinking mode** — leave off unless explicitly needed.  
10. **Workflow engine** — frozen out; presets only.  
11. **Overengineering** — user will reject chrome and “100 controls”; keep boxes simple.  
12. **hub.py growth** — prefer extracting only when a cohesive module exists; don’t scatter second hubs.

---

## 16. Recent meaningful commits (context)

| Commit | Meaning |
|--------|---------|
| `27c2e58` | Memory: garbage filters, scrub, durable-only store |
| `541634f` | README screenshots |
| `3ece349` / `86e6ca5` | Professional EN/DE README split |
| `bb1a636` / `716df5c` | Computer-use portfolio + Tools UI |
| `3043ab9` | Drop quality strip; pick real page task for Execute |
| `06116d5` / `b80b260` | Remove action-bar experiment; fix box layout |
| `6250226` | TTS in user gesture |
| `b5759d4` / `8cdfe51` | Strip Box 3 / Box 2 clutter |

---

## 17. How another AI should change code safely

1. Read `AGENTS.md` + this doc + `docs/STABILITY.md` for the area.  
2. Prefer **smallest fix** in the right layer (orchestrator vs hub wire vs UI).  
3. Do not expand UI surface unless explicitly requested.  
4. Run ruff + pytest before commit.  
5. For chat/execute/Box3: also consider `user_landing_e2e.py`.  
6. Push main with clear message.  
7. Never invent DeepSeek model IDs — update `KEYS_AND_MODELS.md` only from real API docs.

### Suggested reading order for deep work

1. `pipeline/orchestrator.py` — control flow  
2. `agents/roles_ext.py` + `roles_helpers.py` — plan + memory + HTML single-worker  
3. `hub.py` — `_wire_memory`, `snapshot`, job runners  
4. `memory/*` — persistence contract  
5. `ui/static/app.js` — `applySnapshot`, chat busy, execute, box rendering  
6. `api/app.py` — route map only  

---

## 18. Explicit non-goals (parked)

From `docs/V1_SCOPE.md` / PRE_PLAN — do not implement unless scope reopened:

- Skill marketplace / auto tool load  
- Web-surfing agent as first-class role  
- True vector embeddings (current store is lexical bag-of-words)  
- Mobile UI  
- Workflow/skill engine (presets freeze)  
- Kernel-level automation beyond God-Mode desktop  

---

## 19. One-paragraph summary for system prompts

> Gnom-Hub is a local FastAPI multi-agent desk: user brainstorms multi-turn with a red Brainstorm agent; only on Execute does Coordinator distill requirements, Flex review, plan tasks (one worker for full HTML pages), run workers with DoD/HTML gates, and Memory store durable facts into HOT/WARM while filtering garbage. UI is a single SPA with 8 agent cards and 3 boxes; Hub is the composition root; EventBus is sync; LLM is DeepSeek v4-flash (thinking off) with optional Ollama; God-Mode gates real computer-use. Do not reintroduce UI clutter, multi-worker HTML pages, memory HTML pollution, or a workflow engine.

---

*End of analysis. Update this file when architecture or product rules change.*
