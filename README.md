# Gnom-Hub v3.2.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB packs · COLD · Vector · Trace · **Backup restore** · Telegram full remote control.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Backup restore

```
System → Backup zip     → creates data/backups/gnom-hub-backup-*.zip
List item → Rest        → restore HOT + WARM + agents (+ checkpoint if present)
Telegram /backup save | list | load <n|name> | del <n|name>
API POST /api/backups/{name}/restore
```

Current non-empty HOT is archived to COLD before restore (safety).

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=74**

---

## Releases

| Tag | Highlights |
|-----|------------|
| 3.0 | Vector browser + /vec |
| 3.1 | Trace export + /trace |
| **3.2** | Backup restore (UI/API/Telegram) |

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
