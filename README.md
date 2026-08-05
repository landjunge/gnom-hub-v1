# Gnom-Hub v1.9.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB-friendly · DeepSeek / Ollama · **Cost badge** · **Result history** · **Compact mode** · Copy all / Diff · Job timer · Workspace · auto-save.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Send / Enter              → Brainstorm (Box 2)
Execute / Ctrl+Enter      → Distill → Flex → Workers → Quality → Memory
Send+Exec                 → Brainstorm turn then Execute
Ctrl/⌘+S                  → Save HOT + agents
Esc                       → Close Diff/FS overlay, or cancel job
Compact                   → Denser UI (persisted)
History…                  → Restore previous Execute results (session)
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Key.txt: DEEPSEEK_API_KEY=sk-...
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=61**

---

## UI

| Control | Action |
|---------|--------|
| **Cost badge** | Session spend (warn near budget) |
| **Compact** | Toggle denser layout |
| **History…** (Box 3) | Restore last N execute result sets |
| **Copy all / Diff** | All workers / line-diff W1–W2 |
| **Copy / DL / Tab / WS / ↑ / ⛶** | Per-panel tools |
| **Send / Execute / Send+Exec / Cancel** | Pipeline control |
| **Ctrl/⌘+S** | Save |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 1.5–1.7 | Send+Exec, Copy, DL, Tab, WS, timestamps |
| 1.8 | Copy all, Diff, timer, ↑ perm |
| 1.8.1 | Sticky-error + redirect SSRF fixes |
| **1.9** | Cost badge, result history, compact mode, clarify lock |

---

## Dev

```bash
./scripts/quality_check.sh
```

Docs: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## License

Private use.
