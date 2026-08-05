# Gnom-Hub v3.0.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB packs · COLD restore · **Vector browser** · Telegram bs/exec/pack/warm/cold/**vec**/cancel.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Click Vec badge     → list / search / add / delete vector docs
Telegram /vec       → search | add | list | del | clear
Execute pipeline    → requirements + memory facts indexed (lexical)
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=72**

---

## Vector lite

| Action | Desktop | Telegram |
|--------|---------|----------|
| Open | Click **Vec** badge | `/vec list` |
| Search | Query + Search | `/vec search <q>` |
| Add | Add field | `/vec add <text>` |
| Delete | Del on row | `/vec del <id>` |
| Clear | Clear | `/vec clear` |

Lexical bag-of-words cosine (no heavy deps) — not true embeddings.

---

## Releases

| Tag | Highlights |
|-----|------------|
| 2.8 | WARM manager + /cancel |
| 2.9 | COLD restore/delete |
| **3.0** | Vector browser UI + API list/del + /vec |

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
