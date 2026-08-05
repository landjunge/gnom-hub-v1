# Gnom-Hub v2.8.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB packs · Telegram **bs/exec/pack/warm/cancel** · WARM fact manager · DeepSeek / Ollama.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Desktop:  Send = Brainstorm · Execute = workers · System WARM add/del
Telegram: plain=/bs · /exec · /do · /pack · /warm · /cancel · /last
```

---

## Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# Key.txt: DEEPSEEK_API_KEY=sk-...  (optional TELEGRAM_BOT_TOKEN=...)
./scripts/start.sh
./scripts/quality_check.sh
```

**http://127.0.0.1:8080/?v=70**

---

## Telegram

| Command | Action |
|---------|--------|
| plain / `/bs` | Brainstorm turn |
| `/exec` | Execute from notes |
| `/do <task>` | Full one-shot |
| `/pack list\|save\|load` | Session packs |
| `/warm list\|add\|del\|clear` | Durable WARM facts |
| `/cancel` | Soft-cancel running job |
| `/last` `/status` `/reset` | Results / state / clear HOT |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 2.6 | ui_prefs + pack notes |
| 2.7 | Telegram brainstorm-first + /pack |
| **2.8** | WARM manager (UI/API/Telegram) + /cancel |

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
