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

### Three basic tests (B1–B3)

```bash
# server on :8080 recommended
python scripts/basic_tests.py
```

| ID | What | Catches |
|----|------|--------|
| **B1** | API brainstorm → execute | empty pipeline, no workers |
| **B2** | job JSON + `can_execute` | invalid JSON / sticky state |
| **B3** | keyboard Send, UI unfreezes | frozen input, Execute stuck, badge `running…` |

Report: `data/basic-tests/latest_report.json`

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

## Presets (frozen)

Team + Worker presets and `plan_mode` are enough. Do **not** add a workflow subsystem without a proven live pain.
Doc: [`WORKFLOWS_AND_PRESETS.md`](WORKFLOWS_AND_PRESETS.md).

## Known stability fixes (do not regress)

| Issue | Fix |
|-------|-----|
| Execute stuck disabled after brainstorm | `lastCanExecute` + re-apply on `setChatBusy(false)` |
| Sticky pipeline.error on re-execute | clear error on execute/`_finish`; job status by stage |
| web_fetch redirect SSRF | SafeRedirect + final host check |
| V4 Flash empty / tiny content | `thinking: {type: disabled}` by default; fallback `reasoning_content` |
| Brainstorm felt one-shot | Multi-turn `prior` messages + HOT persist per turn; seed from HOT |

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
| 2026-08-05 | 119 pass + B1–B3 | **PASS** (workers max 6k) | stage race, cancel race, Key.txt wins, poll timeout recover |
| 2026-08-05 | **121** + B1–B3 + user E2E | **PASS** 4× HTML 7/7, 4 iframes, export ~42k, $0.006 | DoD + gates + 3200 HTML tokens + 2 retries; still section-split plan (coord fix next) |
| 2026-08-05 | **122** + user E2E | **PASS** tasks = full page + variant + QA + a11y | deterministic HTML plan (no LLM section-split); concurrent hub traffic can race export |

### Debug-team fixes (2026-08-05)

| Bug | Fix |
|-----|-----|
| Concurrent jobs cross-update EventBus handlers | Handlers only while job owns lock + `_active_job_id` |
| Sync chat/execute vs async race | All sync paths use `_pipeline_lock` |
| Soft-cancel then `status=done` | `_finalize_job`: cancel always wins |
| Soft-cancel waits for full LLM run | Cooperative `cancel_check` between stages/workers |
| Clarify hide before API success | Hide only after success; resync on failure |
| Key.txt edits ignored by stale `.env` | Hub keys from Key.txt always overwrite |
| Empty DeepSeek content treated as success | Raise `LLMError` if still empty |
| UI timeout leaves mid-stage + orphan job | Cancel + `/api/state` resync; longer poll |
| Re-Exec while busy | Guard `chatBusy` |
| Brainstorm topic switch (TTS → landing) keeps old `user_text` | Latest user turn wins; topic-switch restarts dialogue |
| Reset leaves checkpoint / running jobs | Reset/clean cancel jobs, drop checkpoint, lock pipeline |
