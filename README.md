# Gnom-Hub v1.7.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB-friendly · DeepSeek / Ollama · URL fetch · Export · Cancel · **Send+Exec** · Box 3 **Copy / DL / Tab / WS / Fullscreen** · **Ctrl+S** · chat **timestamps** · auto-save.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Send / Enter              → Brainstorm (Box 2)
Execute / Ctrl+Enter      → Distill → Flex → Workers → Quality → Memory
Send+Exec                 → Brainstorm turn then Execute
Ctrl/⌘+S                  → Save HOT + agents
Esc                       → Close fullscreen, or cancel running job
```

After a successful **Execute**, HOT + agents are **auto-saved** and **Box 3** is focused (flash highlight).

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Key.txt: DEEPSEEK_API_KEY=sk-...
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=58**

---

## UI

| Control | Action |
|---------|--------|
| **Send** / Enter | Brainstorm turn |
| **Execute** / Ctrl+⌘+Enter | Workers pipeline |
| **Send+Exec** | Send then Execute |
| **Cancel** / Esc | Soft-cancel job |
| **Ctrl/⌘+S** | Save HOT + agents |
| **Copy** (Box 3) | Copy worker result |
| **DL** (Box 3) | Download `.html` / `.txt` |
| **Tab** (Box 3) | Open HTML in new browser tab |
| **WS** (Box 3) | Save result to temp workspace |
| **⛶** (Box 3) | Fullscreen preview (Esc closes) |
| **Export** | Download last run as Markdown |
| **Clear chat** | Wipe browser chat log (timestamps kept while open) |
| **Mic** | Speech-to-text |
| **Card click** | Tuning |
| **Double-click** | Toggle agent |
| **Workspace / Trace / System** | Files, log, keys/backup/presets |

System → backups: **click name = download**, **× = delete**.

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

Uses existing workspace write. Prior: chat, execute, cancel, export, ollama, backups, presets, clean, checkpoint, trace, tools (`web_fetch`), save.

---

## Releases

| Tag | Highlights |
|-----|------------|
| 1.0 | Pre-plan core |
| 1.1 | Ollama + web_fetch |
| 1.2 | Model list, auto URL, Export |
| 1.3 | Cancel, chat persist, presets UI |
| 1.4 | Backup download, keyboard, clear chat |
| 1.5 | Send+Exec, Copy, auto-save, delete backup |
| 1.6 | HTML download, fullscreen, Ctrl+S, focus Box 3 |
| **1.7** | Open HTML in tab, save to workspace (WS), chat timestamps |

---

## Dev

```bash
./scripts/quality_check.sh
```

Docs: [`docs/ROADMAP.md`](docs/ROADMAP.md) · [`docs/PLAN_VS_CODE.md`](docs/PLAN_VS_CODE.md)

## License

Private use.
