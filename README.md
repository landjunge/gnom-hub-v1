# Gnom-Hub v3.6.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB · COLD · Vector · Trace · Backup · Jobs · Workspace · Tools · **HOT facts**.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## HOT vs WARM

| Layer | Lifetime | System | Telegram |
|-------|----------|--------|----------|
| **HOT** | Session (reset clears) | Add / Del / Clear / →W promote | `/hot …` |
| **WARM** | Durable across reset | Add / Del / Clear | `/warm …` |

```
POST /api/memory/hot
DELETE /api/memory/hot?text=
POST /api/memory/hot/clear
POST /api/memory/hot/promote
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=78**

---

## Releases

| Tag | Highlights |
|-----|------------|
| 3.4 | Workspace zip + /ws |
| 3.5 | Tools browser + /tools /fetch |
| **3.6** | HOT facts manager + promote to WARM |

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
