# Gnom-Hub v1.8.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB-friendly · DeepSeek / Ollama · **Copy all** · **Diff W1/W2** · **Job timer** · **↑ permanent workspace** · Box 3 full toolbar · timestamps · auto-save.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Send / Enter              → Brainstorm (Box 2)
Execute / Ctrl+Enter      → Distill → Flex → Workers → Quality → Memory
Send+Exec                 → Brainstorm turn then Execute
Ctrl/⌘+S                  → Save HOT + agents
Esc                       → Close Diff/FS overlay, or cancel job
```

While a job runs, the **job timer** ticks in the Box 3 header. After Execute, duration is logged in chat and Box 3 flashes.

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Key.txt: DEEPSEEK_API_KEY=sk-...
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=59**

---

## UI

| Control | Action |
|---------|--------|
| **Send** / Enter | Brainstorm turn |
| **Execute** / Ctrl+⌘+Enter | Workers pipeline |
| **Send+Exec** | Send then Execute |
| **Cancel** / Esc | Soft-cancel job |
| **Ctrl/⌘+S** | Save HOT + agents |
| **Copy all** (Box 3 header) | Copy every worker result |
| **Diff** (Box 3 header) | Line diff first two workers |
| **Copy / DL / Tab / WS / ↑** | Per-panel clipboard, download, new tab, temp WS, **perm** WS |
| **⛶** | Fullscreen preview |
| **Export** | Markdown download of last run |
| **Workspace / Trace / System** | Files, log, keys/backup/presets |

---

## Keys & env

| Variable | Role |
|----------|------|
| `DEEPSEEK_API_KEY` | Cloud LLM |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | Local (`ollama/…` model) |
| `GNOM_WEB_ALLOW_LOCAL=1` | web_fetch private hosts |
| `TELEGRAM_*` / `GNOM_TELEGRAM_POLL` | Optional bot |
| `GNOM_FREE_ONLY` / `GNOM_MAX_BUDGET_USD` | Policy |
| `GNOM_UI_LANG` | `en` \| `de` |
| `GNOM_PHASE3=0` | Hide God/Cold/Vec |

---

## API

No new endpoints in 1.8. Workspace write already supports `zone: "perm"`.

---

## Releases

| Tag | Highlights |
|-----|------------|
| 1.0–1.4 | Core → cancel, keyboard, backups |
| 1.5 | Send+Exec, Copy, auto-save |
| 1.6 | DL, fullscreen, Ctrl+S, focus Box 3 |
| 1.7 | Tab, WS temp, chat timestamps |
| **1.8** | Copy all, Diff W1/W2, job timer, ↑ perm |

---

## Dev

```bash
./scripts/quality_check.sh
```

Docs: [`docs/ROADMAP.md`](docs/ROADMAP.md) · [`docs/PLAN_VS_CODE.md`](docs/PLAN_VS_CODE.md)

## License

Private use.
