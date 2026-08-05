# Gnom-Hub v1.0.0

Local multi-agent control hub: **free brainstorm first**, then **Execute** workers.

Desktop-only · USB-friendly · DeepSeek LLM · no mandatory cloud backend for the app process.

## Flow

```
Chat (Send)  →  Brainstorm dialogue (Box 2)
                      │
                 Execute button
                      ▼
         Distill → Flex → Coordinator → Workers 1–4 → Quality → Memory
                      │
                 Box 3 + Workspace temp
```

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh
source .venv/bin/activate

# Edit Key.txt:
#   DEEPSEEK_API_KEY=sk-...

./scripts/start.sh                 # http://127.0.0.1:8080/
./scripts/quality_check.sh         # ruff + pytest + smoke_e2e
```

LAN: `GNOM_HUB_HOST=0.0.0.0 ./scripts/start.sh`

## UI (essentials)

| Control | Action |
|---------|--------|
| **Send** | One brainstorm turn |
| **Execute** | Distill + workers |
| **Mic** | Speech-to-text (browser) |
| **Card click** | Agent tuning (prompt + 5 sliders) |
| **Card double-click** | Toggle agent on/off (Memory locked) |
| **Flex dropdown** | security / neutral / researcher |
| **Worker 3/4** | Off by default — double-click to enable |
| **Workspace** | Temp outputs → promote to permanent |
| **Trace** | Light pipeline log |
| **System** | Budget, free-only, language DE/EN, checkpoint, **backup zip**, **clean state** |
| **TTS** | Checkbox on card — browser reads outputs |

Hard-reload after updates: `http://127.0.0.1:8080/?v=51` (or higher).

## Keys & env

| Variable | Role |
|----------|------|
| `DEEPSEEK_API_KEY` | Live LLM (Key.txt → private `.env`) |
| `TELEGRAM_BOT_TOKEN` | Optional bot |
| `GNOM_TELEGRAM_POLL=1` | Long-poll Telegram |
| `GNOM_FREE_ONLY` / `GNOM_MAX_BUDGET_USD` | LLM policy |
| `GNOM_UI_LANG` | `en` or `de` |
| `GNOM_PHASE3=0` | Hide God/Cold/Vec chrome |
| `GNOM_GOD_MODE_AUTO=1` | Start elevated (discouraged) |

## API (core)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/chat` | Brainstorm turn (`?full=1` = one-shot pipeline) |
| POST | `/api/execute` | Distill → workers |
| POST | `/api/clarify` | Distillation answer |
| GET | `/api/state` | Full snapshot |
| POST | `/api/save` | HOT + WARM + agents |
| POST | `/api/reset` | Clear HOT (optional archive) |
| POST | `/api/clean` | Clean HOT + temp + pipeline (WARM kept) |
| POST | `/api/backup` | Zip → `data/backups/` |
| POST | `/api/checkpoint/save\|load` | Resume pipeline state |
| GET | `/api/trace` | Light event log |
| POST | `/api/agents/{id}/tune` | Per-agent knobs |
| GET/POST | `/api/system` | Global LLM + UI lang |
| * | `/api/workspace/*` | Temp/perm files |
| * | `/api/worker-presets*` | Save/apply worker presets |

## Modules

```
src/gnom_hub/
  hub.py  main.py  api/  agents/  pipeline/  llm/  ui/
  memory/   (hot warm cold vector canvas workspace facade)
  telegram/ computer_use/ plugins/ security/
```

## V1 complete vs parked (Pre-Plan)

**Done:** brainstorm→execute, 4+4 agent slots, memory tiers, workspace, tuning, TTS/STT, trace, quality, checkpoint, clean, backup, DE/EN tooltips, CI.

**Parked / lite only:** full skill marketplace, web surfing agent, real kernel God-Mode, auto-update channel, true embedding vectors, self-explaining videos.

See [`docs/PLAN_VS_CODE.md`](docs/PLAN_VS_CODE.md) · [`docs/PRE_PLAN.md`](docs/PRE_PLAN.md) · [`docs/V1_SCOPE.md`](docs/V1_SCOPE.md)

## License

Private use.
