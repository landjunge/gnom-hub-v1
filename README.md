# Gnom-Hub v3.3.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB · COLD · Vector · Trace · Backup restore · **Usage & Jobs** · Telegram remote.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Usage & Jobs

```
Click $ cost badge   → by-agent spend · recent jobs · Cancel · Reset usage
GET /api/jobs        → list recent jobs
GET /api/usage       → session spend snapshot
POST /api/usage/reset
Telegram /jobs · /usage [reset] · /jobs cancel <id>
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=75**

---

## Releases

| Tag | Highlights |
|-----|------------|
| 3.1 | Trace export |
| 3.2 | Backup restore |
| **3.3** | Usage modal + jobs list + /jobs /usage |

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
