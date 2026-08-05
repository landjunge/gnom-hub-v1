# Gnom-Hub v2.0.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB-friendly · DeepSeek / Ollama · **Session pack** · **History Re-Exec** · Cost badge · Compact · Diff · Workspace.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Send / Enter              → Brainstorm (Box 2)
Execute / Ctrl+Enter      → Distill → Flex → Workers → Quality → Memory
Send+Exec                 → Brainstorm turn then Execute
History → Re-Exec         → Re-run workers from a prior brainstorm
System → Pack ↓ / Pack ↑  → Portable session JSON (USB hop)
Ctrl/⌘+S                  → Save HOT + agents
Esc                       → Close Diff/FS overlay, or cancel job
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

**http://127.0.0.1:8080/?v=62**

---

## UI

| Control | Action |
|---------|--------|
| **Pack ↓ / Pack ↑** (System) | Export / import portable session JSON |
| **History… + Re-Exec** (Box 3) | Restore outputs or re-run workers |
| **Cost badge** | Session spend (warn near budget) |
| **Compact** | Toggle denser layout |
| **Copy all / Diff** | All workers / line-diff W1–W2 |
| **Send / Execute / Send+Exec / Cancel** | Pipeline control |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 1.5–1.8 | Send+Exec, Copy, Diff, timer, workspace |
| 1.9 | Cost badge, result history, compact mode |
| **2.0** | Session pack (USB), History Re-Exec |

---

## Dev

```bash
./scripts/quality_check.sh
```

Docs: [`docs/ROADMAP.md`](docs/ROADMAP.md)

## License

Private use.
