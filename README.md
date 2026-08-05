# Gnom-Hub v2.2.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB-friendly · DeepSeek / Ollama · **Session packs** · prune · History Re-Exec · Cost badge · Diff · Workspace.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Send / Enter              → Brainstorm (Box 2)
Execute / Ctrl+Enter      → Distill → Flex → Workers → Quality → Memory
Pack ↓ (System)           → Save under data/packs/ + download JSON
Pack list Load / ↓ / Del  → Import, download, or remove stored packs
Pack ↑                    → Import JSON from disk + store into data/packs/
Auto-pack after Execute   → System toggle (or GNOM_AUTO_PACK=1)
Max packs kept            → Prune oldest (default 30, GNOM_PACK_MAX)
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

**http://127.0.0.1:8080/?v=64**

---

## UI

| Control | Action |
|---------|--------|
| **Pack ↓ / Pack ↑** | Save+download / import session JSON (+ store) |
| **Session packs list** | Load · ↓ download · Del |
| **Auto-pack / Max packs** | Auto-save after Execute; prune oldest |
| **History… + Re-Exec** | Restore outputs or re-run workers |
| **Cost / Compact / Diff** | Spend badge, density, W1↔W2 |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 1.9 | Cost badge, result history, compact |
| 2.0 | Session pack JSON, History Re-Exec |
| 2.1 | Packs on disk, list Load/Del, auto-pack |
| **2.2** | List download, import→store, pack_max prune |

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
