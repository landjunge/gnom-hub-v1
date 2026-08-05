# Gnom-Hub

**Version:** 3.7.1 (see `/api/health` → `version`)  
**Stack:** Python ≥3.10 · FastAPI · static desktop UI · DeepSeek (default) / Ollama  
**Default URL:** `http://127.0.0.1:8080/`  
**License:** private use  

**What it is:** Local multi-agent hub. User brainstorms in chat first; workers run only after explicit **Execute**.

**What it is not:** Not a second LangGraph/CrewAI runtime. Not automatic full desktop takeover from chat alone. Computer-use is manual via **Tools** + God-Mode.

---

## English (facts)

### Pipeline

```
Chat Send → Brainstorm (Box 2)
         → [optional more Send turns]
Execute  → Distill → Flex → Coordinator → Worker(s) → Box 3
```

- HTML/landing-style tasks: **one worker** builds **one** full HTML page (not four pages).
- `plan_mode` + team/worker presets: config only; fixed orchestrator. See `docs/WORKFLOWS_AND_PRESETS.md`.

### Agents (8 fixed)

| id | Role | Default |
|----|------|---------|
| brainstorm | ideas | on |
| memory | HOT/WARM/context | on, not toggleable |
| flex | security / neutral / researcher | on |
| coordinator | distill + assign | on |
| worker1…worker4 | deliverables | 1–2 on, 3–4 off by default |

### UI layout

| Area | Fact |
|------|------|
| Agent cards | toggle, TTS checkbox, tune modal (click) |
| Box 1 | tooltips + Clarify Yes/No/Whatever/Later |
| Box 2 | brainstorm dialogue only (no HOT strip) |
| Box 3 | single worker result; HTML: Preview/Source/Copy |
| Chat | Send, Execute, Send+Exec, Mic, Cancel (when job runs) |
| Header | LLM / Mem / God / Cold / stage badges; Tools / Workspace / System |

### Keys & models

- File: project-root `Key.txt` (see `Key.txt.example`). Prefer over stale `.env` for hub keys.
- Default model id: **`deepseek-v4-flash`**
- Thinking: **off** by default (`DEEPSEEK_THINKING=0`) to avoid empty content
- Doc: `docs/KEYS_AND_MODELS.md`

### Computer-use

| Item | Fact |
|------|------|
| Location | Backend `src/gnom_hub/computer_use/`; UI under **Tools → Computer use** |
| API | `POST /api/computer-use/inspect`, `…/click`, `…/type`, `…/shell`; `GET /api/computer-use` |
| God-Mode | Header **God** badge or `POST /api/god-mode`. **Off = dry-run only.** |
| Actions | screenshot (mss/Pillow), click, type (pyautogui), allowlisted shell |
| Optional install | `pip install -e ".[computer]"` · OCR needs OS `tesseract` · Playwright Chromium for browser E2E |
| Doc | `docs/TOOLS_PORTFOLIO.md` |

### Core tools (registry)

`hub_status`, `memory_search`, `pipeline_do`, `web_fetch`, plus plugins (e.g. `echo`).

### Install & run

```bash
cd gnom-hub-v1
./scripts/install.sh
source .venv/bin/activate
# put keys in Key.txt
./scripts/start.sh
# open http://127.0.0.1:8080/
```

### Quality gate (before commit/push)

```bash
ruff check .
ruff format .
ruff format --check .
pytest tests/ -q --tb=short
# if server up: python scripts/basic_tests.py
```

Also: `./scripts/quality_check.sh` · live: `python scripts/user_landing_e2e.py` (server + key + Playwright).

Rules for coding agents: `AGENTS.md`.

### Important docs

| Path | Content |
|------|---------|
| `AGENTS.md` | mandatory pre-push gate |
| `docs/KEYS_AND_MODELS.md` | API keys, model ids |
| `docs/BASIC_USER_TEST.md` | keyboard landing E2E |
| `docs/STABILITY.md` | stability checklist |
| `docs/TOOLS_PORTFOLIO.md` | computer-use libraries |
| `docs/WORKFLOWS_AND_PRESETS.md` | presets / plan_mode freeze |
| `docs/V1_SCOPE.md` | v1 product scope |
| `docs/ROADMAP.md` | release history / status |

### Repo conventions

- Branch: **`main`**, push after completed steps  
- Do not commit `Key.txt`, `.env`, real secrets  
- UI static cache-bust: `app.css` / `app.js` `?v=` query in `index.html`

---

## Deutsch (Fakten)

### Was es ist

Lokaler Multi-Agenten-Hub. Zuerst **Brainstorm** im Chat, Worker erst nach **Execute**.

### Was es nicht ist

Keine zweite Orchestrator-Engine. Keine automatische PC-Übernahme nur durch Chat. Computer-Use läuft über **Tools** + **God-Mode**.

### Pipeline

```
Send → Brainstorm (Box 2)
Execute → Distill → Flex → Coordinator → Worker → Box 3
```

Landing/HTML: **ein** Worker, **eine** HTML-Seite.

### Boxen

1. Arounder: Hilfe + Clarify  
2. Brainstorm: nur Dialog  
3. Workers: ein Ergebnis (Preview/Source/Copy bei HTML)

### Chat

Send = nur Brainstorm · Execute = Worker-Pipeline · Send+Exec = beides · Mic · Cancel  

### Computer-Use

- **Tools**-Modal: Inspect, Click, Type, Shell  
- **God** an = echte Maus/Tastatur (sonst dry-run)  
- Optional: `pip install -e ".[computer]"` · siehe `docs/TOOLS_PORTFOLIO.md`

### Start

```bash
./scripts/install.sh && source .venv/bin/activate
./scripts/start.sh   # http://127.0.0.1:8080/
```

Keys: `Key.txt`, Modell `deepseek-v4-flash` → `docs/KEYS_AND_MODELS.md`.

### Tests / Agenten-Regeln

```bash
./scripts/quality_check.sh
pytest tests/ -q
```

Vor Push: `AGENTS.md` (ruff + pytest grün, keine Secrets).

### Lizenz

Private Nutzung.
