# Basic User Test (canonical)

**Purpose:** Real user-position tests — **Playwright on the desktop UI**, plus **Gnom Tools / computer-use** so the Tools portfolio is not dead weight.

## Suite (preferred)

| Script | What |
|--------|------|
| **`scripts/user_scenarios_e2e.py`** | **Main** multi-scenario runner |
| `scripts/e2e_lib.py` | Shared HTTP + Playwright waits |
| `scripts/user_landing_e2e.py` | Thin wrapper → S1 only |
| `scripts/basic_tests.py` | B1–B3 API + light UI (no full Tools path) |

### Scenarios

| ID | Name | How it uses Gnom |
|----|------|------------------|
| **S1** | Landing happy path | Real keyboard → Box 2 brainstorm → Execute → Box 3 HTML |
| **S2** | Topic switch | TTS brainstorm → todo task → Execute must pick todo |
| **S3** | Clarify | Vague request → clarify or done without hang |
| **S4** | Clean then task | `/api/clean` then small HTML pricing section |
| **S5** | **Tools + computer-use** | UI Tools modal + `/api/tools/call` + `/api/computer-use/*` |

**Default (optimized):** `S1 + S5` — product path + why Tools exist.  
**Full:** `--all` or `GNOM_E2E_ALL=1` in quality_check.

---

## How to run

```bash
./scripts/start.sh
source .venv/bin/activate
# first time:
# pip install playwright && python -m playwright install chromium

# Quick (recommended): landing + tools
python scripts/user_scenarios_e2e.py

# All five scenarios
python scripts/user_scenarios_e2e.py --all

# Watch browser
GNOM_E2E_HEADED=1 python scripts/user_scenarios_e2e.py --only 5

# quality_check includes S1+S5 when server is up
./scripts/quality_check.sh
GNOM_E2E_ALL=1 ./scripts/quality_check.sh
```

Artifacts: `data/e2e-scenarios/<timestamp>/` — screenshots, `report.json`, `REPORT.md`.  
Latest: `data/e2e-scenarios/latest_report.json`.

---

## Pass criteria

### S1 (landing)
| Check | Required |
|-------|----------|
| Box 2 brainstorm non-empty | yes |
| Stage `done` or `clarify` | yes |
| ≥1 worker panel / outputs | yes |
| No pipeline.error | yes |
| Worker body **≥800 chars** | **yes (hard)** |
| File `LATEST_RESULT/RESULT.html` written | **yes (hard)** |
| HTML preview preferred | soft |

**Agents:** A green JSON `ok: true` without a human-openable deliverable is a **failed test design**. Fix criteria; do not wait for the user to ask “where is the result?”.

### S5 (tools — non-negotiable for “tools portfolio”)
| Check | Required |
|-------|----------|
| `POST /api/tools/call` hub_status works | yes |
| `GET/POST /api/computer-use` responds | yes |
| Tools modal opens in UI | yes |

God-Mode may stay **off** (dry-run inspect is enough for CI).

---

## Why this shape

- **Playwright** = real frontend (keyboard, buttons, boxes) — not API-only “user”.  
- **Tools/computer-use APIs + Tools modal** = portfolio is exercised, not only documented.  
- **Default S1+S5** = fast enough for quality_check; full S1–S5 when you care about topic/clarify/clean.
