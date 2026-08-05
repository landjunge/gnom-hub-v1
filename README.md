# Gnom-Hub

**Version:** 3.7.1 · **Python:** ≥3.10 · **UI:** `http://127.0.0.1:8080/`  
**License:** private use  

**Deutsch:** [README_DE.md](README_DE.md)

Local multi-agent hub: **brainstorm first**, then **Execute** workers.

**Not:** a second LangGraph/CrewAI stack · not automatic full PC control from chat alone.

---

## Pipeline

```
Send → Brainstorm (Box 2)
Execute → Distill → Flex → Coordinator → Worker(s) → Box 3
```

HTML/landing tasks: **one worker**, **one** HTML page.

## Agents (8 fixed)

| id | role | default |
|----|------|---------|
| brainstorm | ideas | on |
| memory | session memory | on (locked) |
| flex | security / neutral / researcher | on |
| coordinator | distill + plan | on |
| worker1…worker4 | deliverables | 1–2 on; 3–4 off |

## UI

| Area | Content |
|------|---------|
| Box 1 | help + Clarify (Yes / No / Whatever / Later) |
| Box 2 | brainstorm dialogue only |
| Box 3 | one worker result (Preview / Source / Copy for HTML) |
| Chat | Send · Execute · Send+Exec · Mic · Cancel |
| Tools | tool registry + **Computer use** (inspect / click / type / shell) |
| God badge | real mouse/keyboard/shell when **on** (else dry-run) |

## Install

```bash
cd gnom-hub-v1
./scripts/install.sh && source .venv/bin/activate
# keys → Key.txt  (see Key.txt.example)
./scripts/start.sh
```

Keys & model: [`docs/KEYS_AND_MODELS.md`](docs/KEYS_AND_MODELS.md) · default model **`deepseek-v4-flash`**.

Computer-use packages (optional):

```bash
pip install -e ".[computer]"
# macOS OCR: brew install tesseract
python -m playwright install chromium   # for E2E scripts
```

Details: [`docs/TOOLS_PORTFOLIO.md`](docs/TOOLS_PORTFOLIO.md)

## Tests / quality gate

```bash
./scripts/quality_check.sh
# server on :8080:
python scripts/basic_tests.py
python scripts/user_landing_e2e.py
```

Agent rules (ruff + pytest before every push): [`AGENTS.md`](AGENTS.md)

## Docs index

| File | Topic |
|------|--------|
| [README_DE.md](README_DE.md) | German README |
| [AGENTS.md](AGENTS.md) | coding / push gate |
| [docs/KEYS_AND_MODELS.md](docs/KEYS_AND_MODELS.md) | API keys, models |
| [docs/BASIC_USER_TEST.md](docs/BASIC_USER_TEST.md) | keyboard landing E2E |
| [docs/STABILITY.md](docs/STABILITY.md) | stability checklist |
| [docs/TOOLS_PORTFOLIO.md](docs/TOOLS_PORTFOLIO.md) | computer-use libs |
| [docs/WORKFLOWS_AND_PRESETS.md](docs/WORKFLOWS_AND_PRESETS.md) | presets / plan_mode |
| [docs/V1_SCOPE.md](docs/V1_SCOPE.md) | v1 scope |
| [docs/ROADMAP.md](docs/ROADMAP.md) | history / status |

## Conventions

- Push completed work to **`main`**
- Never commit `Key.txt`, `.env`, or real secrets
- Static UI cache: `?v=` on `app.css` / `app.js` in `index.html`
