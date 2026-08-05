# Gnom-Hub v3.1.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB packs · COLD · Vector · **Trace export** · Telegram bs/exec/pack/warm/cold/vec/**trace**/cancel.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Trace

```
Header Trace button  → Refresh · ↓ JSON · ↓ MD · Clear
Telegram /trace [n]  → last n events
Telegram /trace clear
API GET /api/trace/export?fmt=json|md
API POST /api/trace/clear
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=73**

---

## Releases

| Tag | Highlights |
|-----|------------|
| 2.9 | COLD restore/delete |
| 3.0 | Vector browser + /vec |
| **3.1** | Trace download (JSON/MD), clear, /trace |

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
