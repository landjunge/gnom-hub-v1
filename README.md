# Gnom-Hub v1.2.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop-only · USB-friendly · **DeepSeek** and/or **Ollama** · auto **URL fetch** · **Export** Markdown · CI green.

> **Repo convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Chat (Send)  →  Brainstorm dialogue (Box 2)
                      │
                 Execute
                      ▼
    Distill → Flex → Coordinator → Workers 1–4 → Quality → Memory
                      │
           Box 3 HTML preview · Workspace temp · optional URL fetch
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh
source .venv/bin/activate

# Key.txt (copied from example on install):
#   DEEPSEEK_API_KEY=sk-...

./scripts/start.sh                 # http://127.0.0.1:8080/
./scripts/quality_check.sh         # ruff (pinned) + pytest + smoke_e2e
```

| Env | Default |
|-----|---------|
| `GNOM_HUB_HOST` | `127.0.0.1` (use `0.0.0.0` for LAN) |
| `GNOM_HUB_PORT` | `8080` |

Hard-reload UI after updates: **http://127.0.0.1:8080/?v=53**

---

## UI

| Control | Action |
|---------|--------|
| **Send** | One brainstorm turn only |
| **Execute** | Distill + Flex + workers |
| **Mic** | Browser speech-to-text |
| **Export** | Download last run as `gnom-hub-export.md` |
| **Card click** | Tuning (system prompt + 5 sliders + model/key) |
| **Card double-click** | Toggle on/off (Memory always on) |
| **Flex dropdown** | security / neutral / researcher |
| **Worker 3/4** | Default off — double-click to enable (up to 4 workers) |
| **Workspace** | Temp files after Execute → promote / clear / delete |
| **Trace** | Light pipeline event log |
| **System** | Budget, free-only, UI lang DE/EN, Ollama model list, checkpoint, **backup zip**, **clean state** |
| **TTS** | Per-card checkbox — browser reads agent output |

Box borders follow the active agent color. Box 3 renders HTML with Preview / Source.

---

## Keys & environment

| Variable | Role |
|----------|------|
| `DEEPSEEK_API_KEY` | Cloud LLM (via `Key.txt` → private `.env`) |
| `OLLAMA_HOST` | Default `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | Default `llama3.2` |
| Agent model field | e.g. `ollama/llama3.2` forces local Ollama |
| `GNOM_WEB_ALLOW_LOCAL=1` | Allow `web_fetch` to private/localhost |
| `TELEGRAM_BOT_TOKEN` | Optional bot |
| `GNOM_TELEGRAM_POLL=1` | Long-poll Telegram |
| `GNOM_FREE_ONLY` / `GNOM_MAX_BUDGET_USD` | LLM policy |
| `GNOM_UI_LANG` | `en` or `de` |
| `GNOM_PHASE3=0` | Hide God / Cold / Vec chrome |
| `GNOM_GOD_MODE_AUTO=1` | Start elevated (discouraged) |

**Ollama (optional):** `ollama serve` · `ollama pull llama3.2` · System shows installed models.

---

## API (core)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Liveness + version + LLM flags |
| GET | `/api/state` | Full snapshot |
| POST | `/api/chat` | Brainstorm turn (`?full=1` = one-shot full pipeline) |
| POST | `/api/execute` | Distill → workers (async job by default) |
| POST | `/api/clarify` | Distillation Yes/No/… |
| GET | `/api/jobs/{id}` | Poll async job |
| POST | `/api/save` | HOT + WARM + agents |
| POST | `/api/reset` | Clear HOT (archives first) |
| POST | `/api/clean` | HOT + temp workspace + pipeline; WARM kept |
| POST | `/api/backup` | Zip → `data/backups/` |
| POST | `/api/checkpoint/save` · `/load` | Resume pipeline state |
| GET | `/api/trace` | Light event log |
| GET | `/api/export/last` | Markdown export payload |
| GET | `/api/ollama/models` | Installed Ollama tags |
| POST | `/api/agents/{id}/tune` | Per-agent knobs |
| POST | `/api/agents/enable-all` | Enable core agents |
| GET/POST | `/api/system` | Global LLM + UI lang |
| * | `/api/workspace/*` | Temp/perm files |
| * | `/api/worker-presets*` | Save/apply worker presets |
| POST | `/api/tools/call` | Tools incl. `web_fetch`, `hub_status`, … |

---

## Layout

```
src/gnom_hub/
  hub.py  main.py  api/  agents/  pipeline/  llm/  ui/  tools/
  memory/   hot · warm · cold · vector · canvas · workspace · facade
  telegram/ computer_use/ plugins/ security/
plugins/echo/
scripts/  install.sh · start.sh · quality_check.sh · smoke_*.py
docs/     PRE_PLAN · V1_SCOPE · PLAN_VS_CODE · ROADMAP
```

---

## Releases

| Version | Highlights |
|---------|------------|
| **1.0.0** | Pre-plan core complete (brainstorm→execute, UI, memory, CI) |
| **1.1.0** | Ollama provider + safe `web_fetch` tool |
| **1.2.0** | Ollama model list UI, auto URL prefetch on Execute, Export button |

Tags: `v1.0.0` · `v1.1.0` · `v1.2.0`

---

## Dev / CI

```bash
./scripts/quality_check.sh
# ruff==0.16.1 · pytest · smoke_e2e (chat→execute)
```

GitHub Actions on `main`: lint + test matrix 3.10–3.12 + smoke.

---

## Scope notes

**In product:** multi-agent pipeline, local data dirs, DeepSeek/Ollama, workspace, trace/quality/checkpoint/clean/backup, DE/EN tooltips.

**Parked / lite:** full skill marketplace, unrestricted web agent, real kernel God-Mode, auto-update, true embeddings, mobile UI.

Details: [`docs/PLAN_VS_CODE.md`](docs/PLAN_VS_CODE.md) · [`docs/PRE_PLAN.md`](docs/PRE_PLAN.md) · [`docs/V1_SCOPE.md`](docs/V1_SCOPE.md) · [`docs/ROADMAP.md`](docs/ROADMAP.md)

## License

Private use.
