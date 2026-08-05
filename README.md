# Gnom-Hub v1

Local-first multi-agent system.

**Pipeline:** Chat → Brainstorm → Distillation → Coordinator → Workers → Box 3 + Memory  
**Control:** Toggle agents, budget protection, free models only when you want  
**UI:** Agent cards + 3 boxes + interactive Box 1  
**Portable:** USB-capable, desktop-only

## Status

| Step | Topic | Status |
|------|--------|--------|
| 0.1 | EventBus + structure | done |
| 0.2 | Key.txt → .env + LLM-Manager (DeepSeek) | done |
| 0.3 | Agents + toggle + Flex presets | done |
| 0.4 | Pipeline | done |
| 0.5 | Memory HOT + Mermaid + offload | done |
| 0.6 | Desktop UI skeleton | done |
| 0.7–0.8 | HTTP API + wire + interactive clarify | done |
| 0.9 | Per-agent model/key + Flex API | done |
| 1.0 | Runbook / start script | done |
| 1.1 | Flex in pipeline, UI status, install.sh | done |
| 1.2 | Tokens on cards + error/ok toasts | done |
| 1.3 | Agent state save, canvas API, live DeepSeek | done |

Full plan: [`docs/PRE_PLAN.md`](docs/PRE_PLAN.md) · V1 scope: [`docs/V1_SCOPE.md`](docs/V1_SCOPE.md) · Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Quick start

```bash
cd gnom-hub-v1
./scripts/install.sh          # venv + deps + Key.txt template
source .venv/bin/activate
# edit Key.txt → DEEPSEEK_API_KEY=...  (optional; stubs work without)

./scripts/start.sh            # UI http://127.0.0.1:8080/
# or: python -m gnom_hub.main
# smoke: python -m gnom_hub.main --smoke
```

**UI tips:** double-click agent card = on/off (Memory locked).  
**Flex:** Shift+double-click cycles preset `security → neutral → researcher`.  
**Clarify:** if the chat has `?` or `maybe`, Box 1 asks Yes/No/Whatever/Later.

Open **http://127.0.0.1:8080/** — desktop layout (13″ fixed sizes).

### Keys / budget

| File | Role |
|------|------|
| `Key.txt` | Secrets (gitignored) → merged into `.env` |
| `.env` | Private env (gitignored) |
| `GNOM_FREE_ONLY=1` | Block non-free models |
| `GNOM_MAX_BUDGET_USD=1.0` | Session spend guard |

Without a DeepSeek key the pipeline still runs on **deterministic stubs** (great for UI debug).

### API (summary)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness |
| GET | `/api/state` | Full snapshot |
| POST | `/api/chat` | `{ "text": "..." }` start pipeline |
| POST | `/api/clarify` | `{ "option": "Yes" }` Box-1 answer |
| POST | `/api/agents/{id}/toggle` | Double-click toggle |
| POST | `/api/agents/flex/preset` | `{ "preset": "security" }` |
| POST | `/api/agents/{id}/llm` | `{ "model", "api_key" }` optional |
| POST | `/api/save` | Persist HOT memory |
| GET | `/api/tooltips` | Box-1 registry |

## Structure

```
src/gnom_hub/
├── core/        EventBus
├── agents/      Manager, toggle, Flex presets
├── pipeline/    Chat → … → workers
├── memory/      HOT session + mermaid + offload
├── llm/         DeepSeek + budget / free_only
├── api/         FastAPI
├── ui/static/   Desktop UI
├── hub.py       Wiring facade
└── main.py      Server / smoke
```

## Dev

```bash
ruff check .
ruff format --check .
pytest tests/ -v
```

## Agent notes

See [`AGENTS.md`](AGENTS.md) — **commit + push after every section**.
