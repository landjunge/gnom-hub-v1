# Gnom-Hub v1.3.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop-only · USB-friendly · **DeepSeek** / **Ollama** · auto **URL fetch** · **Export** · **Cancel job** · chat log persists in browser.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Chat (Send)  →  Brainstorm dialogue (Box 2)
                      │
                 Execute  (Cancel while running)
                      ▼
    Distill → Flex → Coordinator → Workers 1–4 → Quality → Memory
                      │
           Box 3 · Workspace temp · optional public URL fetch
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh
source .venv/bin/activate
# Key.txt: DEEPSEEK_API_KEY=sk-...
./scripts/start.sh                 # http://127.0.0.1:8080/
./scripts/quality_check.sh
```

LAN: `GNOM_HUB_HOST=0.0.0.0 ./scripts/start.sh`  
UI reload: **http://127.0.0.1:8080/?v=54**

---

## UI

| Control | Action |
|---------|--------|
| **Send** | Brainstorm turn |
| **Execute** | Distill + workers |
| **Cancel** | Soft-cancel running async job |
| **Mic** | Speech-to-text |
| **Export** | Download last run as Markdown |
| **Card click** | Tuning (prompt + 5 sliders) |
| **Double-click** | Toggle agent (Memory locked) |
| **Flex dropdown** | security / neutral / researcher |
| **Worker 3/4** | Off by default — enable via double-click |
| **Workspace** | Temp → promote / clear |
| **Trace** | Pipeline event log |
| **System** | Budget, lang DE/EN, Ollama models, checkpoint, backup list, **worker presets apply/delete**, clean |
| **TTS** | Per-card read-aloud |
| Chat log | Restored from `sessionStorage` in this browser |

---

## Keys & env

| Variable | Role |
|----------|------|
| `DEEPSEEK_API_KEY` | Cloud LLM |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | Local LLM (`ollama/…` in agent model) |
| `GNOM_WEB_ALLOW_LOCAL=1` | Allow web_fetch to private hosts |
| `TELEGRAM_BOT_TOKEN` / `GNOM_TELEGRAM_POLL=1` | Optional bot |
| `GNOM_FREE_ONLY` / `GNOM_MAX_BUDGET_USD` | LLM policy |
| `GNOM_UI_LANG` | `en` \| `de` |
| `GNOM_PHASE3=0` | Hide God/Cold/Vec chrome |

---

## API (highlights)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/chat` | Brainstorm (`?full=1` full pipeline) |
| POST | `/api/execute` | Workers pipeline |
| POST | `/api/jobs/{id}/cancel` | Soft-cancel job |
| GET | `/api/export/last` | Markdown export |
| GET | `/api/ollama/models` | Local models |
| GET | `/api/backups` | List backup zips |
| POST | `/api/backup` | Create backup |
| POST | `/api/worker-presets` · `/apply` · `/delete` | Worker presets |
| POST | `/api/clean` · `/checkpoint/*` · `/trace` | Ops |

---

## Releases

| Tag | Highlights |
|-----|------------|
| **1.0.0** | Pre-plan core complete |
| **1.1.0** | Ollama + web_fetch tool |
| **1.2.0** | Ollama list, auto URL fetch, Export |
| **1.3.0** | Cancel job, chat persist, presets UI, backups list |

---

## Dev

```bash
./scripts/quality_check.sh   # ruff==0.16.1 · pytest · smoke_e2e
```

Parked: skill marketplace, auto-update, true embeddings, mobile UI.  
Docs: [`docs/ROADMAP.md`](docs/ROADMAP.md) · [`docs/PLAN_VS_CODE.md`](docs/PLAN_VS_CODE.md)

## License

Private use.
