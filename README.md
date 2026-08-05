# Gnom-Hub

**Local multi-agent control hub** — think first, then act.

| | |
|--|--|
| **Version** | 3.7.1 |
| **Stack** | Python ≥3.10 · FastAPI · desktop UI |
| **Default** | `http://127.0.0.1:8080/` |
| **LLM** | DeepSeek (`deepseek-v4-flash`) · optional Ollama |
| **License** | Private use |

**Deutsch:** [README_DE.md](README_DE.md)

### Screenshot

![Gnom-Hub desktop UI](docs/assets/gnom-hub-ui.png)

*Agent cards, three work boxes, chat — local at `http://127.0.0.1:8080/`*

![Tools · Computer use](docs/assets/gnom-hub-tools.png)

*Tools modal with computer-use controls (Inspect / Click / Type / Shell)*

---

## Why Gnom?

Most agent tools either **run away immediately** (chat → tools → chaos) or hide behind heavy frameworks. Gnom is built around a deliberate product rule:

> **Brainstorm freely. Execute only when you say so.**

That single split is the product.

### What stands out

| Strength | What it means in practice |
|----------|---------------------------|
| **Brainstorm → Execute** | Chat can stay exploratory. Workers (cost, files, side effects) start only on **Execute**. |
| **Visible multi-agent desk** | Eight fixed roles as cards + three work boxes — you always see *who* is active and *where* output lands. |
| **One page, not four** | For landing/HTML work, Gnom assigns **one worker** and **one complete HTML file** — no fragment soup. |
| **Local & portable** | Runs on your machine; keys in `Key.txt`; USB-friendly layout; no cloud lock-in required. |
| **Safety by default** | Computer control (mouse/keyboard/shell) is **dry-run** until **God-Mode** is explicitly on. |
| **Operator-grade ops** | HOT/WARM/COLD memory, workspace, backups, packs, jobs, light trace, budget guard — for real sessions, not demos only. |
| **Lean architecture** | One fixed orchestrator. Presets configure the team; they do **not** invent a second agent runtime. |

### Who it’s for

- Builders who want a **desktop control surface** for multi-agent work  
- People who need **HTML/page deliverables** they can preview in-box  
- Operators who care about **cost, keys, cancel, and audit** — not only “vibe chat”

### Who it’s not for

- Fully autonomous unattended agents with no human gate  
- Drop-in replacement for LangGraph/CrewAI research stacks  
- Silent background control of your PC from every chat message  

---

## Quick start

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Configure Key.txt  →  docs/KEYS_AND_MODELS.md
./scripts/start.sh
# open http://127.0.0.1:8080/
```

### Chat

| Control | Action |
|---------|--------|
| **Send** | Brainstorm turn → Box 2 |
| **Execute** | Distill → Flex → Coordinator → Worker(s) → Box 3 |
| **Send+Exec** | Both in sequence |
| **Mic** | Speech-to-text |
| **Cancel** | Abort running job |

### Boxes

| Box | Role |
|-----|------|
| **1 · Arounder** | Help + Clarify (Yes / No / Whatever / Later) |
| **2 · Brainstorm** | Multi-turn dialogue |
| **3 · Workers** | Deliverable (HTML preview or text) |

### Computer use

Desktop control lives under **Tools → Computer use** (Inspect · Click · Type · Shell).

| Mode | Behavior |
|------|----------|
| God **off** | Dry-run only (safe) |
| God **on** | Real mouse / keyboard / allowlisted shell |

Optional packages: `pip install -e ".[computer]"` — see [`docs/TOOLS_PORTFOLIO.md`](docs/TOOLS_PORTFOLIO.md).

---

## Architecture (short)

```
UI  ──►  Hub (FastAPI)  ──►  Orchestrator
                │                 │
                ├─ Agents (8)     ├─ Brainstorm
                ├─ LLM manager    ├─ Distill / Flex
                ├─ Memory HOT/WARM/COLD
                ├─ Workspace
                └─ Computer-use kit (+ God-Mode)
```

**Agents:** brainstorm · memory · flex · coordinator · worker1–4  

**Pipeline stages:** memory → brainstorm → distill → [clarify] → flex → coordinate → work → done  

---

## Quality & contribution

```bash
./scripts/quality_check.sh
python scripts/basic_tests.py          # needs server :8080
python scripts/user_landing_e2e.py     # Playwright + live key
```

Coding agents must follow [`AGENTS.md`](AGENTS.md): ruff + pytest green before every push; never commit secrets.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [README_DE.md](README_DE.md) | German README |
| [AGENTS.md](AGENTS.md) | Agent coding rules / push gate |
| [docs/KEYS_AND_MODELS.md](docs/KEYS_AND_MODELS.md) | Keys & model IDs |
| [docs/BASIC_USER_TEST.md](docs/BASIC_USER_TEST.md) | Canonical user E2E |
| [docs/STABILITY.md](docs/STABILITY.md) | Stability checklist |
| [docs/TOOLS_PORTFOLIO.md](docs/TOOLS_PORTFOLIO.md) | Computer-use libraries |
| [docs/WORKFLOWS_AND_PRESETS.md](docs/WORKFLOWS_AND_PRESETS.md) | Team presets & plan_mode |
| [docs/V1_SCOPE.md](docs/V1_SCOPE.md) | Product scope |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Release history |

---

## License

Private use.
