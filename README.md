# Gnom-Hub

**Local multi-agent control hub** — brainstorm first, execute only when you say so.

| | |
|--|--|
| **Version** | 3.7.1 |
| **Stack** | Python ≥3.10 · FastAPI · desktop SPA |
| **UI** | `http://127.0.0.1:8080/` |
| **LLM** | DeepSeek (`deepseek-v4-flash`, thinking off) · optional Ollama |
| **License** | Private use |

**Deutsch:** [README_DE.md](README_DE.md)  
**Deep code handoff (for other AIs):** [docs/CODE_ANALYSIS_FOR_AI.md](docs/CODE_ANALYSIS_FOR_AI.md)

---

### Screenshots

![Gnom-Hub desktop UI](docs/assets/gnom-hub-ui.png)

*Eight agent cards · three work boxes · chat — local desktop*

![Tools · Computer use](docs/assets/gnom-hub-tools.png)

*Tools modal: core tools + computer-use (Inspect / Click / Type / Shell)*

---

## Why Gnom?

Most agent products either **fire tools on every message** or hide control inside heavy frameworks. Gnom is built around one product rule:

> **Brainstorm freely. Execute only when you press Execute.**

That split is the product: exploration stays cheap and reversible; workers (cost, files, side effects) start only on purpose.

### What is strong

| Strength | In practice |
|----------|-------------|
| **Brainstorm → Execute** | Send is dialogue only. Workers run after **Execute** (or Send+Exec). |
| **Visible multi-agent desk** | Eight fixed roles as cards + three boxes — you see who is active and where output lands. |
| **One HTML page, not four** | Landing/page tasks assign **one worker** and **one complete** single-file HTML document. |
| **Local & portable** | Runs on your machine; keys in `User/Key.txt`; USB-friendly `data/`; no cloud lock-in required. |
| **Honest LLM / auth** | Placeholder keys (`sk-your-…`) are not “ready”. Workers return **FEHLER**, not fake stubs. Session blocks dead keys after 401. |
| **Safety by default** | Mouse / keyboard / shell are **dry-run** until **God-Mode** is explicitly on. |
| **Tools you can see** | Registry + plugins; worker **prefetch** (`web_fetch`, `memory_search`, `install_tool`); UI **Tools** badge + light trace. |
| **Operator ops** | HOT / WARM / COLD memory, workspace, backups, session packs, jobs, soft-cancel, light trace, budget guard. |
| **Lean orchestration** | One fixed pipeline. Team/worker **presets** + `plan_mode` only — no second workflow engine. |
| **Memory hygiene** | Durable facts go to WARM; Flex wishes (`source=flex`) survive HOT clear; HTML/meta junk filtered. |
| **Flex as operator proxy** | Locked agent: stores only your wishes as **absolute** orders, co-writes in brainstorm, can press Execute, nudges workers (skips useless re-runs on auth fail). |

### Who it is for

- Builders who want a **desktop control surface** for multi-agent work  
- People who need **HTML deliverables** with in-box preview  
- Operators who care about **cost, keys, cancel, and audit** — not only vibe chat  

### Who it is not for

- Fully autonomous unattended agents with no human gate  
- Drop-in replacement for LangGraph / CrewAI research stacks  
- Silent PC control from every chat message  

---

## Quick start

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Keys → personal WS User/Key.txt  (see docs/KEYS_AND_MODELS.md)
./scripts/start.sh
# open http://127.0.0.1:8080/
```

Copy `Key.txt.example` → **`User/Key.txt`** (or root `Key.txt` for legacy) and set at least:

- `DEEPSEEK_API_KEY` — system agents (brainstorm, memory, flex, coordinator)  
- `WORKER_API_KEY` — workers (optional; falls back to system key if empty)  
- `DEEPSEEK_MODEL=deepseek-v4-flash`  

**Never** paste example placeholders (`sk-your-system-deepseek-key`) — the hub treats them as missing.  
Never commit `Key.txt`, `User/`, or `.env`.

Without a **usable** API key (and without Ollama), workers report **FEHLER — kein Deliverable** instead of pretending success. Pipeline stages still run for smoke tests.

Header badges:

| Badge | Meaning |
|-------|---------|
| **LLM: …** | Live provider / placeholder / blocked / no key |
| **Tools: N** | Tool calls this pipeline run (prefetch + registry) |
| **God / Mem / Vec / Cold / Stage** | Ops surface |

---

## Using the desk

### Chat controls

| Control | Action |
|---------|--------|
| **Send** | One brainstorm turn → Box 2 |
| **Execute** | Distill → Flex → Coordinator plan → Worker(s) → Box 3 + Memory |
| **Send+Exec** | Both in sequence |
| **Mic** | Browser speech-to-text |
| **Cancel** | Soft-cancel the running job |

Chat supports **flag chips** (colors attach intent) and free-text notes on results where enabled.

### Boxes

| Box | Role |
|-----|------|
| **1 · Arounder** | Help / tooltips · Clarify (Yes / No / Whatever / Later) |
| **2 · Brainstorm** | Multi-turn dialogue |
| **3 · Workers** | Deliverable — HTML **Preview** / Source / Copy |

### Agents (fixed roster)

| Agent | Role | Default |
|-------|------|---------|
| Brainstorm | Free multi-turn partner | on |
| Memory | Always-on recall + durable fact store | on (locked) |
| Flex | **Fixed** personal companion: wishes → WARM, co-talk, Execute trigger, worker nudge | on (**locked**) |
| Coordinator | Distill requirements · plan worker tasks | on |
| Worker 1–2 | Produce deliverables | on |
| Worker 3–4 | Extra capacity | on (toggleable) |

### Computer use

**Tools → Computer use** — Inspect · Click · Type · Shell.

| Mode | Behavior |
|------|----------|
| God **off** | Dry-run only (safe default) |
| God **on** | Real mouse / keyboard / allowlisted shell |

```bash
pip install -e ".[computer]"   # optional extras
```

Details: [docs/TOOLS_PORTFOLIO.md](docs/TOOLS_PORTFOLIO.md).

---

## Tools & plugins

### Core tools (always registered)

| Tool | Purpose |
|------|---------|
| `hub_status` | Compact stage / auth / tool_calls / god |
| `tools_list` | List tools (optional `tag` filter) |
| `memory_search` | Vector / lexical search |
| `pipeline_do` | Full pipeline with a task text |
| `pipeline_info` | Stage, tool_calls, quality head |
| `web_fetch` | Public HTTP(S) → text (SSRF-safe defaults) |
| `workspace_list` / `workspace_read` | Hub workspace zones |
| `trace_tail` | Last light-trace events |

API: `GET /api/plugins`, `POST /api/tools/call`, `GET /api/mcp/tools`.

### Worker prefetch

On **Execute**, workers may auto-call (and log as `pipeline.tool_call`):

- `web_fetch` when the task contains URLs  
- `memory_search` for standing context  
- `install_tool` (plugin) for missing allowlisted packages (e.g. Playwright) — dry-run first  

### Plugins

Trusted packs under `plugins/<id>/` with `plugin.json` + `main.py`.

```bash
python scripts/new_plugin.py my_tool   # from plugins/_template
# edit plugins/my_tool/ · restart or:
# POST /api/plugins/reload?plugin_id=my_tool
```

Helpers: `from gnom_hub.plugins.sdk import ok, fail, retry`.  
Security & authoring: [docs/PLUGIN_SECURITY.md](docs/PLUGIN_SECURITY.md).

Bundled examples: `echo`, `install_tool`, `text_stats` (`_template` is not loaded).

---

## Architecture

```
Browser SPA (app.js ← parts/* via build_ui_js.py)
       │  REST + job polling
       ▼
FastAPI  ──►  Hub (composition root + mixins)
                 ├── EventBus (sync)
                 ├── Orchestrator (stages)
                 ├── 8 role agents
                 ├── LLM manager (DeepSeek / Ollama + auth snapshot)
                 ├── Memory (HOT / WARM / COLD / vector)
                 ├── ToolRegistry + PluginLoader
                 ├── Workspace · packs · backups · jobs
                 └── Computer-use kit (+ God-Mode)
```

Hub public methods live on focused mixins (`pipeline_api`, `jobs`, `session_pack`, `presets`, `tools_ops`, …). API routes stay thin.

### Pipeline stages

```
memory → brainstorm → distill → [clarify] → flex → coordinate → work → done
```

- **Brainstorm** (Send): dialogue only; Flex absorbs wishes + co-talk; may auto-Execute when intent is clear.  
- **Execute**: distill → optional clarify → Flex briefing + absolute wish inject → plan → prefetch tools → workers → quality gates / retries → Flex nudge.  
- Full one-shot path exists for tests / Telegram (`/do`).  

### Memory layers

| Layer | Lifetime | Purpose |
|-------|----------|---------|
| **HOT** | Session | Messages, session facts, Mermaid canvas |
| **WARM** | Durable | Long-lived facts (survive HOT clear / clean) |
| **COLD** | Archive | Saved past sessions |
| **Vector** | Durable | Hybrid BM25 + cosine (short-fact tuned; flex boost) |
| **Workspace** | Artifacts | Temp / permanent files after execute |

Clean / Reset clears HOT + temp workspace + pipeline; **WARM stays** unless cleared explicitly.

### Plan modes (presets)

Configured via team presets — not a second orchestrator:

| Mode | Behavior |
|------|----------|
| `default` | Auto HTML full-page when task looks like a page; else LLM/stub split |
| `full_page_html` | Exactly **one** worker builds one complete HTML page |
| `plan_qa` | Deterministic QA-style task templates |
| `diagnosis` | Deterministic diagnosis templates |

See [docs/WORKFLOWS_AND_PRESETS.md](docs/WORKFLOWS_AND_PRESETS.md).

---

## Quality & contribution

```bash
ruff check .
ruff format .
ruff format --check .
pytest tests/ -q --tb=short

# Local pre-push gate (also via git hooks)
./scripts/prepush_gate.sh
./scripts/install_git_hooks.sh   # pre-commit + pre-push + safe.directory

# Mutation testing (test the tests)
python scripts/mutation_check.py              # fast scoped helpers — must kill all
# optional deep: ./scripts/run_mutmut.sh      # see docs/MUTMUT.md

./scripts/quality_check.sh
python scripts/basic_tests.py          # needs server on :8080
python scripts/user_scenarios_e2e.py   # Playwright scenarios
python -m gnom_hub.main --smoke        # brainstorm → execute without UI
```

Coding agents: follow [AGENTS.md](AGENTS.md) — ruff + pytest green before every push; commit and push after each completed step; never commit secrets.

Flex role contract: [docs/AGENTS_DEFINITION.md](docs/AGENTS_DEFINITION.md). Testing notes: [docs/TESTING.md](docs/TESTING.md).

---

## Documentation

| Document | Purpose |
|----------|---------|
| [README_DE.md](README_DE.md) | German README |
| [AGENTS.md](AGENTS.md) | Coding rules / push gate |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Short system map |
| [docs/CODE_ANALYSIS_FOR_AI.md](docs/CODE_ANALYSIS_FOR_AI.md) | Full architecture for external AIs |
| [docs/KEYS_AND_MODELS.md](docs/KEYS_AND_MODELS.md) | Keys & model IDs |
| [docs/PLUGIN_SECURITY.md](docs/PLUGIN_SECURITY.md) | Plugins: trust, authoring, reload |
| [docs/BASIC_USER_TEST.md](docs/BASIC_USER_TEST.md) | Canonical user E2E |
| [docs/STABILITY.md](docs/STABILITY.md) | Stability checklist |
| [docs/TOOLS_PORTFOLIO.md](docs/TOOLS_PORTFOLIO.md) | Computer-use libraries |
| [docs/AGENTS_DEFINITION.md](docs/AGENTS_DEFINITION.md) | Agent roster · **Flex fixed** contract |
| [docs/WORKFLOWS_AND_PRESETS.md](docs/WORKFLOWS_AND_PRESETS.md) | Presets & plan_mode |
| [docs/TESTING.md](docs/TESTING.md) | pytest + mutation overview |
| [docs/MUTMUT.md](docs/MUTMUT.md) | mutmut config · profiles · hooks |
| [docs/V1_SCOPE.md](docs/V1_SCOPE.md) | Product scope |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Release history |

---

## License

Private use.
