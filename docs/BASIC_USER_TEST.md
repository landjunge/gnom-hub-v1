# Basic User Test (canonical)

**Purpose:** Real user-position smoke — browser + keyboard, not API-only stubs.

**Script:** `scripts/user_landing_e2e.py`  
**Last live PASS:** `data/e2e-user/20260805T172841Z/` (v3.7.1, DeepSeek v4-flash; 4× worker HTML 7/7, export ~42k)

---

## Scenario (human path)

1. Open `http://127.0.0.1:8080/`
2. **Type** (keyboard) into chat:
   > Build a modern landing page for a coffee shop called Bean & Bloom. Include hero with headline and CTA, three feature cards, and a simple footer. Output full HTML with inline CSS.
3. Press **Enter** → Brainstorm (Box 2 fills)
4. Press **Execute** (or Ctrl+Enter) → Distill → Workers → Box 3
5. Expect **Worker 1 / Worker 2** panels; ideally HTML **Preview** iframe

---

## Pass criteria

| Check | Required |
|-------|----------|
| Brainstorm Box 2 non-empty | yes (>40 chars) |
| Stage ends `done` (or clarify with content) | yes |
| ≥1 worker panel or API `worker_outputs` | yes |
| No `pipeline.error` | yes |
| HTML-ish content or preview iframe | preferred (not hard-fail) |

---

## How to run

```bash
# server must be up with LLM key
./scripts/start.sh
source .venv/bin/activate
# first time: pip install playwright && python -m playwright install chromium
python scripts/user_landing_e2e.py
# optional: watch browser
GNOM_E2E_HEADED=1 python scripts/user_landing_e2e.py
```

Artifacts: `data/e2e-user/<timestamp>/` — screenshots, `report.json`, `REPORT.md`, `export_last.md`.  
Latest summary: `data/e2e-user/latest_report.json`.

---

## Findings from first real runs (2026-08-05)

| What worked | What failed / fixed |
|-------------|---------------------|
| Keyboard type into `#chat-input` | — |
| Enter → live Brainstorm (Box 2 ~2–3k chars) | — |
| Cost badge updates | — |
| API Execute produced 2 workers | **UI Execute stayed disabled after brainstorm** |
| After fix: full path PASS, 2 panels, HTML preview, export ~15k chars | **Root cause:** `applySnapshot` set Execute disabled while `chatBusy=true`; `setChatBusy(false)` did not restore `can_execute` |

**Fix:** `lastCanExecute` flag; `setChatBusy` always sets  
`btnExecute.disabled = !lastCanExecute || chatBusy`.

---

## Agent rule

When changing chat busy, Execute enable, brainstorm/execute pipeline, or Box 3 rendering:

1. Re-run `python scripts/user_landing_e2e.py` if a live key is available.
2. Do not claim “chat UX OK” from unit tests alone.
3. Keep this document and the script as the **basic regression for user chat → landing page**.
