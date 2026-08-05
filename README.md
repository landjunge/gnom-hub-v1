# Gnom-Hub v1

Local-first multi-agent system.

**Pipeline:** Chat → Brainstorm → Distillation → Coordinator → Workers → Box 3 + Memory  
**Memory:** HOT (session) + **WARM** (durable facts) + Mermaid canvas  
**Control:** Toggle agents, budget protection, free models only when you want  
**UI:** Agent cards + 3 boxes + interactive Box 1  
**Optional:** Telegram bot, dual workspace (temp/perm)  
**Portable:** USB-capable, desktop-only (LAN OK)

## Status

| Step | Topic | Status |
|------|--------|--------|
| 0.1–1.6 | Core hub, UI, API, quality/CI | done |
| 2.0 | WARM lite + workspace + Telegram optional | done |
| CI | `pip install -e ".[dev]"` + smoke_e2e | done |

Full plan: [`docs/PRE_PLAN.md`](docs/PRE_PLAN.md) · V1 scope: [`docs/V1_SCOPE.md`](docs/V1_SCOPE.md) · Roadmap: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Quick start

```bash
cd gnom-hub-v1
./scripts/install.sh          # venv + deps + Key.txt template
source .venv/bin/activate
# edit Key.txt → DEEPSEEK_API_KEY=...  (optional; stubs work without)

./scripts/start.sh            # UI http://127.0.0.1:8080/
# LAN: GNOM_HUB_HOST=0.0.0.0 ./scripts/start.sh
```

**UI tips**

- Double-click agent card = on/off (Memory locked)
- Flex: Shift+double-click cycles `security → neutral → researcher`
- Clarify: chat with `?` or `maybe` → Box 1 Yes/No/Whatever/Later
- **Reset** clears HOT session only; **WARM facts stay**
- **Save** writes HOT + WARM + agent toggles

### Keys / budget

| File / env | Role |
|------------|------|
| `Key.txt` / `.env` | Secrets (gitignored) |
| `DEEPSEEK_API_KEY` | Live LLM |
| `TELEGRAM_BOT_TOKEN` | Optional bot |
| `GNOM_TELEGRAM_POLL=1` | Auto long-poll Telegram |
| `GNOM_FREE_ONLY=1` | Block non-free models |
| `GNOM_MAX_BUDGET_USD=1.0` | Session spend guard |

Without DeepSeek the pipeline uses **deterministic stubs**.

### API (summary)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness |
| GET | `/api/state` | Full snapshot |
| POST | `/api/chat` | Start pipeline |
| POST | `/api/clarify` | Box-1 answer |
| POST | `/api/agents/{id}/toggle` | Toggle |
| POST | `/api/agents/flex/preset` | Flex preset |
| POST | `/api/save` | Persist HOT+WARM+agents |
| POST | `/api/reset` | Clear HOT (`?clear_warm=true` also clears WARM) |
| GET | `/api/memory` | HOT + WARM facts + context |
| POST | `/api/memory/warm` | `{ "text": "…" }` add durable fact |
| GET | `/api/workspace` | temp/perm file lists |
| POST | `/api/workspace/write` | write file |
| POST | `/api/workspace/promote/{name}` | temp → perm |
| POST | `/api/telegram/start` | start poller |
| POST | `/api/telegram/stop` | stop poller |
| POST | `/api/telegram/inbound` | inject message (tests / no Telegram net) |
| GET | `/api/help` | Help text |
| GET | `/api/canvas` | Mermaid |
| GET | `/api/tooltips` | Box-1 registry |

### Telegram (optional)

```bash
# Key.txt
TELEGRAM_BOT_TOKEN=123456:ABC...
export GNOM_TELEGRAM_POLL=1
./scripts/start.sh
```

Commands: `/status` `/do <task>` `/last` `/reset` `/yes` `/no` `/whatever` `/later` `/help`  
Plain text = task (`/do`).

## Structure

```
src/gnom_hub/
├── core/         EventBus
├── agents/       Manager, toggle, Flex
├── pipeline/     Chat → … → workers
├── memory/       HOT, WARM, facade, canvas, workspace
├── llm/          DeepSeek + budget
├── telegram/     Optional bot bridge
├── api/          FastAPI
├── ui/static/    Desktop UI
├── hub.py
└── main.py
```

## Dev

```bash
pip install -e ".[dev]"   # includes httpx for TestClient
./scripts/quality_check.sh
# or: ruff + pytest + python scripts/smoke_e2e.py
```

**CI** installs `.[dev]`, runs ruff, pytest, `scripts/smoke_e2e.py`.

## Agent notes

See [`AGENTS.md`](AGENTS.md) — **commit + push after every section**.
