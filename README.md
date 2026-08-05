# Gnom-Hub v2.4.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB-friendly · DeepSeek / Ollama · **Session packs** (chat + history) · rename · prune · Re-Exec.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Send / Enter              → Brainstorm (Box 2)
Execute / Ctrl+Enter      → Distill → Flex → Workers → Quality → Memory
Pack ↓ (System)           → HOT/WARM/agents/pipeline + chat log + result history
Pack list Load/Ren/↓/Del  → Import (restores UI chat/history), rename, USB copy
Pack ↑                    → Import JSON + store under data/packs/
Auto-pack / Max packs     → Server auto-save (no browser UI state) + prune
History → Re-Exec         → Re-run workers from a prior brainstorm
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

**http://127.0.0.1:8080/?v=66**

---

## UI

| Control | Action |
|---------|--------|
| **Pack ↓ / Pack ↑** | Full USB hop incl. chat + result history |
| **Session packs list** | Load · Ren · ↓ · Del (+ mtime) |
| **Auto-pack / Max packs** | Server-side pack after Execute; prune |
| **History… + Re-Exec** | Restore outputs or re-run workers |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 2.1 | Packs on disk, list Load/Del, auto-pack |
| 2.2 | List download, import→store, pack_max prune |
| 2.3 | Rename label, mtime, label on export |
| **2.4** | Pack includes chat log + result history |

---

## Dev

```bash
ruff check .
ruff format .
pytest tests/ -v --tb=short
```

Docs: [`docs/ROADMAP.md`](docs/ROADMAP.md) · Agent rules: [`AGENTS.md`](AGENTS.md)

## License

Private use.
