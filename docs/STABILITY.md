# Stability checklist (track A)

Goal: **trust the hub** before adding features. Run this after chat/Execute/LLM/key changes.

---

## Quick gate (every commit / before “fertig”)

```bash
cd gnom-hub-v1
source .venv/bin/activate
./scripts/quality_check.sh
```

Expect: ruff OK · pytest green · smoke e2e OK · live smoke **non-empty** content when key present.

---

## Basic user gate (real keyboard path)

Needs server + DeepSeek key + Playwright:

```bash
./scripts/start.sh   # if not running
python scripts/user_landing_e2e.py
# optional: GNOM_E2E_HEADED=1 python scripts/user_landing_e2e.py
```

| Criterion | Pass |
|-----------|------|
| Brainstorm Box 2 non-empty | required |
| Execute enables after Send | required (fixed 3.7.1 `lastCanExecute`) |
| Stage `done`, ≥1 worker panel | required |
| No `pipeline.error` | required |
| HTML preview / substantial worker text | preferred |

Reports: `data/e2e-user/<timestamp>/` · summary `data/e2e-user/latest_report.json`  
Doc: [`BASIC_USER_TEST.md`](BASIC_USER_TEST.md)

---

## Config sanity

| Check | Expected |
|-------|----------|
| `Key.txt` | `DEEPSEEK_MODEL=deepseek-v4-flash`, system + worker keys |
| `/api/state` → `llm.default_model` | `deepseek-v4-flash` |
| Agents | all `model=deepseek-v4-flash`, online if keys set |
| Thinking | **off** by default (`DEEPSEEK_THINKING=0`) so content is not empty |

Reference: [`KEYS_AND_MODELS.md`](KEYS_AND_MODELS.md)

---

## Known stability fixes (do not regress)

| Issue | Fix |
|-------|-----|
| Execute stuck disabled after brainstorm | `lastCanExecute` + re-apply on `setChatBusy(false)` |
| Sticky pipeline.error on re-execute | clear error on execute/`_finish`; job status by stage |
| web_fetch redirect SSRF | SafeRedirect + final host check |
| V4 Flash empty / tiny content | `thinking: {type: disabled}` by default; fallback `reasoning_content` |

---

## When to re-run what

| You changed… | Run |
|--------------|-----|
| Any Python / CI | `quality_check.sh` |
| Chat busy, Execute, Box 3, pipeline stages | + `user_landing_e2e.py` |
| DeepSeek client / model / keys | + `smoke_live.py` + user E2E |
| Only docs | quality optional |

---

## Last stability pass log

| Date | quality | user E2E | notes |
|------|---------|----------|-------|
| 2026-08-05 | 119 pass | PASS (4 workers, quality poor) | thinking-on burned tokens |
| 2026-08-05 | 119 pass + live pong | **PASS** 4 HTML iframes, quality 5–6/6, export ~27k | thinking default **disabled** |
