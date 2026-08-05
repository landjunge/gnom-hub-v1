# Gnom-Hub v3.5.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB · COLD · Vector · Trace · Backup · Jobs · Workspace · **Tools browser**.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Tools

```
Header Tools button     → list plugins/tools · Run · Quick Fetch
POST /api/tools/call    → { name, arguments }
Telegram /tools         → list
Telegram /tool <name> [json|plain]
Telegram /fetch <url>   → web_fetch shortcut
```

Core tools: `hub_status`, `memory_search`, `pipeline_do`, `web_fetch` (+ any loaded plugins).

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=77**

---

## Releases

| Tag | Highlights |
|-----|------------|
| 3.3 | Usage & Jobs |
| 3.4 | Workspace zip + /ws |
| **3.5** | Tools browser + /tools /fetch |

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
