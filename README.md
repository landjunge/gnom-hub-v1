# Gnom-Hub v2.3.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB-friendly · DeepSeek / Ollama · **Session packs** · rename · prune · History Re-Exec · Cost · Diff · Workspace.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Send / Enter              → Brainstorm (Box 2)
Execute / Ctrl+Enter      → Distill → Flex → Workers → Quality → Memory
Pack ↓ (System)           → Optional label → save data/packs/ + download
Pack list Load/Ren/↓/Del  → Import, rename label, download, delete
Pack ↑                    → Import JSON + store under data/packs/
Auto-pack / Max packs     → Auto-save + prune oldest (GNOM_PACK_MAX)
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

**http://127.0.0.1:8080/?v=65**

---

## UI

| Control | Action |
|---------|--------|
| **Pack ↓ / Pack ↑** | Save+download (optional label) / import+store |
| **Session packs list** | Load · Ren · ↓ · Del (+ mtime) |
| **Auto-pack / Max packs** | Auto-save after Execute; prune oldest |
| **History… + Re-Exec** | Restore outputs or re-run workers |
| **Cost / Compact / Diff** | Spend badge, density, W1↔W2 |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 2.0 | Session pack JSON, History Re-Exec |
| 2.1 | Packs on disk, list Load/Del, auto-pack |
| 2.2 | List download, import→store, pack_max prune |
| **2.3** | Rename pack label, mtime in list, label on export |

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
