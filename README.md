# Gnom-Hub v2.6.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB · Session packs (chat · history · workspace · **ui prefs · notes**) · filter · Re-Exec.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Send / Enter              → Brainstorm (Box 2)
Execute / Ctrl+Enter      → Distill → Flex → Workers → Quality → Memory
Pack ↓                    → Full hop + compact/lang prefs + optional notes
Pack list filter/Load…    → Filter (label/notes) · Load · Ren · ↓ · Del
Pack ↑                    → Import JSON + store under data/packs/
Auto-pack / Max packs     → Server auto-save + prune
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

**http://127.0.0.1:8080/?v=68**

---

## UI

| Control | Action |
|---------|--------|
| **Pack ↓ / Pack ↑** | USB hop: chat, history, workspace, compact, lang, notes |
| **Filter packs…** | Label / notes / name / date |
| **Ren** | Edit label + notes |
| **Auto-pack / Max packs** | After Execute; prune oldest |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 2.3 | Rename label, mtime, label on export |
| 2.4 | Chat log + result history in pack |
| 2.5 | Workspace temp/perm + pack filter |
| **2.6** | ui_prefs (compact/lang) + pack notes |

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
