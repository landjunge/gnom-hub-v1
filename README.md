# Gnom-Hub v2.9.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB packs · COLD **restore** · Telegram bs/exec/pack/warm/**cold**/cancel · WARM · DeepSeek/Ollama.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Desktop:  Archive HOT → COLD browser → Restore to HOT / Delete
Telegram: /cold list | load <n|id> | del <n|id>
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=71**

---

## COLD

| Action | How |
|--------|-----|
| Archive | Header **Archive** or Reset (auto) |
| Browse | Click **Cold** badge |
| Restore | Select archive → **Restore to HOT** (current HOT archived first if non-empty) |
| Delete | Select → **Delete** |
| Telegram | `/cold list` · `/cold load 1` · `/cold del <id>` |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 2.7 | Telegram brainstorm-first + /pack |
| 2.8 | WARM manager + /cancel |
| **2.9** | COLD restore/delete (UI + API + Telegram) |

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
