# Gnom-Hub v2.5.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB-friendly · DeepSeek / Ollama · **Session packs** (chat · history · **workspace**) · filter · Re-Exec.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Send / Enter              → Brainstorm (Box 2)
Execute / Ctrl+Enter      → Distill → Flex → Workers → Quality → Memory
Pack ↓ (System)           → HOT/WARM/agents/pipeline + chat + history + workspace
Pack list filter/Load…    → Filter by label · Load · Ren · ↓ · Del
Pack ↑                    → Import JSON + store under data/packs/
Auto-pack / Max packs     → Server auto-save + workspace files + prune
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

**http://127.0.0.1:8080/?v=67**

---

## UI

| Control | Action |
|---------|--------|
| **Pack ↓ / Pack ↑** | Full USB hop: chat, history, temp+perm workspace |
| **Filter packs…** | Client-side filter by label/name/date |
| **Session packs list** | Load · Ren · ↓ · Del |
| **Auto-pack / Max packs** | After Execute; prune oldest |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 2.2 | List download, import→store, pack_max prune |
| 2.3 | Rename label, mtime, label on export |
| 2.4 | Chat log + result history in pack |
| **2.5** | Workspace temp/perm in pack + pack filter |

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
