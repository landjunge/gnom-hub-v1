# Gnom-Hub v3.4.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB · COLD · Vector · Trace · Backup · Usage/Jobs · **Workspace zip + /ws**.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Workspace

```
UI Workspace modal     → ↓ zip temp · ↓ zip perm · ↓ all
POST /api/workspace/export?zone=temp|perm|all
GET  /api/workspace/exports/{name}
Telegram /ws list | cat | promote | del | clear | write
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=76**

---

## Releases

| Tag | Highlights |
|-----|------------|
| 3.2 | Backup restore |
| 3.3 | Usage & Jobs modal |
| **3.4** | Workspace zip export + Telegram /ws |

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
