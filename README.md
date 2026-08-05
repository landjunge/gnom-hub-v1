# Gnom-Hub v1

Local-first multi-agent system.

**Pipeline:** Chat → Brainstorm → Distillation → Flex → Coordinator → Workers → Memory  
**Memory:** HOT · WARM · **COLD archive** · Mermaid · **Vector lite**  
**Control:** Agent toggles · budget · **God-Mode** (explicit)  
**Optional:** Telegram · dual workspace · **Computer-Use kit** · **Plugins / MCP-lite**  
**Portable:** USB-capable, desktop-only (LAN OK)

## Status

| Wave | Topic | Status |
|------|--------|--------|
| 0.x–1.6 | Core hub, UI, API, quality/CI | done |
| 2.0 | WARM + workspace + Telegram | done |
| **3.0** | COLD, vector, God-Mode, computer-use, plugins/MCP | **done** |
| **3.1** | Vector recall in pipeline, Archive UI, safe God-Mode shell | **done** |
| **3.2** | UI God toggle, COLD browser, optional live smoke | **done** |

Docs: [`docs/PRE_PLAN.md`](docs/PRE_PLAN.md) · [`docs/V1_SCOPE.md`](docs/V1_SCOPE.md) · [`docs/ROADMAP.md`](docs/ROADMAP.md)

## Quick start

```bash
cd gnom-hub-v1
./scripts/install.sh
source .venv/bin/activate
# Key.txt → DEEPSEEK_API_KEY=...  (optional)

./scripts/start.sh            # http://127.0.0.1:8080/
# LAN: GNOM_HUB_HOST=0.0.0.0 ./scripts/start.sh
./scripts/quality_check.sh    # ruff + pytest + smoke_e2e
```

### UI tips

- Double-click card = toggle (Memory locked)
- Flex: Shift+double-click → preset cycle
- Clarify on `?` / `maybe` → Box 1 buttons
- **Reset** = clear HOT only (WARM stays)
- **Save** = HOT + WARM + agent state

### Keys / flags

| Key / env | Role |
|-----------|------|
| `DEEPSEEK_API_KEY` | Live LLM |
| `TELEGRAM_BOT_TOKEN` | Optional bot |
| `GNOM_TELEGRAM_POLL=1` | Auto Telegram long-poll |
| `GNOM_GOD_MODE_AUTO=1` | Start with God-Mode on (discouraged) |
| `GNOM_FREE_ONLY` / `GNOM_MAX_BUDGET_USD` | LLM policy |

## API map

### Core
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness |
| GET | `/api/state` | Full snapshot |
| POST | `/api/chat` | Run pipeline |
| POST | `/api/clarify` | Distillation answer |
| POST | `/api/save` | Persist HOT+WARM+agents |
| POST | `/api/reset` | Clear HOT (`?clear_warm=true` optional) |

### Memory
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/memory` | HOT + WARM + context |
| POST | `/api/memory/warm` | Add durable fact |
| GET/POST | `/api/canvas` | Mermaid HOT |
| POST | `/api/cold/archive` | Snapshot HOT → COLD |
| GET | `/api/cold` | List archives |
| GET | `/api/cold/{id}` | Load archive |
| POST | `/api/vector/add` | Index text |
| POST | `/api/vector/search` | Lexical cosine search |

### Security / automation / plugins
| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/api/god-mode` | Explicit elevated mode |
| POST | `/api/computer-use/inspect` | Capture+vision+OCR kit |
| POST | `/api/computer-use/click` | Click (dry-run unless God-Mode) |
| POST | `/api/computer-use/shell` | Allowlisted cmds only when God-Mode on |
| GET | `/api/plugins` | Loaded plugins + tools |
| GET | `/api/mcp/tools` | MCP-style tools/list |
| POST | `/api/tools/call` | Invoke tool by name |

### Workspace / Telegram
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/workspace` | temp/perm files |
| POST | `/api/workspace/write` | Write file |
| POST | `/api/workspace/promote/{name}` | temp → perm |
| POST | `/api/telegram/*` | start/stop/inbound |

## Modules (layout)

```
src/gnom_hub/
  core/ agents/ pipeline/ llm/ ui/ api/ hub.py main.py
  memory/   hot warm cold vector_store canvas workspace facade
  telegram/ computer_use/ plugins/ security/
plugins/echo/          # demo plugin (echo tool)
```

### God-Mode
Off by default. **Click the God badge** in the UI (confirm dialog) or  
`POST /api/god-mode {"enabled":true,"reason":"..."}`.  
Clicks need God-Mode; shell only allowlisted binaries  
(`ls pwd date uname whoami echo cat head tail wc df du`) — no pipes/metacharacters.

### Reset / Archive / COLD browser
**Archive** → COLD snapshot of current HOT.  
**Reset** → auto-archives non-empty HOT, then clears HOT (WARM kept).  
**Click Cold badge** → browse archives in Box 1 (list + fact preview).

### Live smoke (optional)
```bash
python scripts/smoke_live.py          # skips if no DEEPSEEK_API_KEY
GNOM_LIVE_SMOKE=1 python scripts/smoke_live.py   # fail if no key
```
CI runs live smoke only when secret `DEEPSEEK_API_KEY` is configured (non-blocking).

### Vector lite
No heavy deps — bag-of-words + cosine. Pipeline requirements/worker outputs are auto-indexed.

### Computer-Use
Capture (Pillow if present, else stub PNG) · Vision notes · OCR (optional pytesseract) · Action dry-run.

### Plugins / MCP-lite
Drop folders under `plugins/<id>/plugin.json` + `main.py`. Example: `plugins/echo`.  
`GET /api/mcp/tools` exposes a tools/list-style manifest.

## Dev

```bash
pip install -e ".[dev]"   # httpx required for TestClient
./scripts/quality_check.sh
```

## Agent notes

[`AGENTS.md`](AGENTS.md) — commit **and push** after every section.
