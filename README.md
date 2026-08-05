# Gnom-Hub v2.7.0

Local multi-agent control hub: **brainstorm first**, then **Execute** workers.

Desktop · USB packs · Telegram **bs/exec/pack** · DeepSeek / Ollama · History Re-Exec.

> **Convention:** every meaningful change is **pushed to `main`** and this **README is updated** in the same commit.

---

## Flow

```
Desktop:  Send = Brainstorm · Execute = workers
Telegram: plain or /bs = Brainstorm · /exec = Execute · /do = one-shot
Packs:    System Pack ↓/↑  ·  Telegram /pack list|save|load
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

**http://127.0.0.1:8080/?v=69**

---

## Telegram

| Command | Action |
|---------|--------|
| plain text / `/bs` | Brainstorm turn (no auto-execute) |
| `/exec` | Run workers from notes |
| `/do <task>` | Full one-shot pipeline |
| `/pack list` | List saved packs |
| `/pack save [label]` | Persist pack on disk |
| `/pack load <n\|name>` | Import pack by index or name |
| `/status` `/last` `/reset` | Hub state / results / clear HOT |
| `/yes` `/no` … | Clarify answers |

---

## Releases

| Tag | Highlights |
|-----|------------|
| 2.4–2.6 | Packs: chat, history, workspace, prefs, notes |
| **2.7** | Telegram brainstorm-first + /pack commands |

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
