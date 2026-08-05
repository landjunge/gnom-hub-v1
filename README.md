# Gnom-Hub v1.4.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop-only · USB-friendly · DeepSeek / Ollama · URL fetch · Export · Cancel · chat persist · **backup download** · keyboard shortcuts.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Chat (Send / Enter)     →  Brainstorm (Box 2)
Execute (Ctrl/⌘+Enter)  →  Distill → Flex → Workers 1–4 → Quality → Memory
Cancel  (Esc)           →  soft-cancel running job
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Key.txt: DEEPSEEK_API_KEY=sk-...
./scripts/start.sh              # http://127.0.0.1:8080/
./scripts/quality_check.sh
```

UI: **http://127.0.0.1:8080/?v=55** · LAN: `GNOM_HUB_HOST=0.0.0.0`

---

## UI

| Control | Action |
|---------|--------|
| **Send** / Enter | Brainstorm turn |
| **Execute** / Ctrl+Enter (⌘+Enter) | Distill + workers |
| **Cancel** / Esc | Soft-cancel running job |
| **Clear chat** | Wipe browser chat log |
| **Mic** | Speech-to-text |
| **Export** | Download last run as Markdown |
| **Card click** | Tuning (prompt + 5 sliders) |
| **Double-click** | Toggle agent (Memory locked) |
| **Flex** | security / neutral / researcher |
| **Worker 3/4** | Off by default |
| **Workspace** | Temp → promote |
| **Trace** | Event log |
| **System** | Budget, lang, Ollama models, checkpoint, backups (**click zip to download**), worker presets |
| **TTS** | Per-card read-aloud |
| Title badge | Shows live version from API |

Chat log persists in `sessionStorage` for this browser tab/session.

---

## Keys & env

| Variable | Role |
|----------|------|
| `DEEPSEEK_API_KEY` | Cloud LLM |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | Local LLM (`ollama/…` model string) |
| `GNOM_WEB_ALLOW_LOCAL=1` | web_fetch to private hosts |
| `TELEGRAM_BOT_TOKEN` / `GNOM_TELEGRAM_POLL=1` | Optional bot |
| `GNOM_FREE_ONLY` / `GNOM_MAX_BUDGET_USD` | LLM policy |
| `GNOM_UI_LANG` | `en` \| `de` |
| `GNOM_PHASE3=0` | Hide God/Cold/Vec |

---

## API (highlights)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/chat` · `/api/execute` | Brainstorm / workers |
| POST | `/api/jobs/{id}/cancel` | Soft-cancel |
| GET | `/api/export/last` | Markdown export |
| GET | `/api/ollama/models` | Local models |
| GET | `/api/backups` | List zips |
| GET | `/api/backups/{name}/download` | Download backup zip |
| POST | `/api/backup` · `/api/clean` | Create backup / clean state |
| POST | `/api/worker-presets*` | Save / apply / delete |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 1.0.0 | Pre-plan core |
| 1.1.0 | Ollama + web_fetch |
| 1.2.0 | Model list, auto URL fetch, Export |
| 1.3.0 | Cancel, chat persist, presets UI, backups list |
| **1.4.0** | Backup download, keyboard shortcuts, clear chat, version badge |

---

## Dev

```bash
./scripts/quality_check.sh   # ruff==0.16.1 · pytest · smoke_e2e
```

Parked: skill marketplace, auto-update, true embeddings, mobile.  
Docs: [`docs/ROADMAP.md`](docs/ROADMAP.md) · [`docs/PLAN_VS_CODE.md`](docs/PLAN_VS_CODE.md)

## License

Private use.
