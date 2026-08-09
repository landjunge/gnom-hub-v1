# Real-user quality suite (fixed development gate)

Three **absolute real** frontend journeys. The runner **is the user** (mouse + keyboard on the live Web UI). You watch in real time when headed mode is on.

**Language:** All prompts and UI preference are **German** (`ui_lang=de`). TTS prefers **de-DE** and speaks **one agent fully before the next** (queue, no cut-off).

## What is measured

| Dimension | What “good” means |
|-----------|-------------------|
| **Brainstorm** | Box 2 dialogue is useful, on-topic, structured |
| **Flex** | Personal notes / wishes appear and influence requirements |
| **Result** | Real Box 3 deliverable (length, HTML, interactions when expected) |

Each scenario scores **0–10** per dimension → **% overall**.  
Each run is compared to `data/e2e-real/LATEST/scores.json` → **↑ better / ↓ worse / → same**.

## Scenarios

| ID | Role-play | Intent |
|----|-----------|--------|
| **G1** (`g`, **default**) | User tippt nur: **Landingpage Gnom-Hub v1** | Pipeline macht den Rest (Brainstorm/Flex/Execute/Worker) |
| **R1** | Soft café idea → decide landing → execute | Legacy |
| **R2** | Clear todo-app build order | Legacy |
| **R3** | Warm wish (dark + German) + portfolio page | Legacy |

```bash
python scripts/real_user_quality_e2e.py           # G1 only
python scripts/real_user_quality_e2e.py --only 1,2,3   # legacy suite
```

## Run (watchable — your Chrome tab)

```bash
./scripts/start.sh          # hub :8080, real LLM preferred
source .venv/bin/activate

# Optional once: real Chrome with CDP so the test reuses your Gnom tab
# /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
# open http://127.0.0.1:8080  (or let the script open a tab)

python scripts/gnom_chrome_tab.py   # find tab with Gnom IP, else new tab
python scripts/real_user_quality_e2e.py
```

**Tab rule (user):** search Chrome for a tab whose URL has the Gnom IP (`127.0.0.1:8080`); **reuse** it; **only** open a new tab if none exists. No separate «Chrome for Testing» when CDP/Chrome is available.

- **Headed by default** (`GNOM_E2E_HEADED=1`) — live, slow typing.
- Prefer CDP: `GNOM_E2E_CDP=http://127.0.0.1:9222`
- Headless (CI only): `GNOM_E2E_HEADED=0 python scripts/real_user_quality_e2e.py`
- One scenario: `python scripts/real_user_quality_e2e.py --only 2`
- Slower/faster: `GNOM_E2E_SLOW_MS=120 GNOM_E2E_TYPE_DELAY=25 …`

## Artifacts

```
data/e2e-real/<timestamp>/
  SCORECARD.md   # human report
  TREND.md       # vs previous run
  scores.json    # machine scores
  *.png          # screenshots
  RESULT.html    # best worker deliverable (when HTML)
data/e2e-real/LATEST/   # always last run
```

## Gate rule (agents / you)

Before claiming “pipeline/Flex/UI is better”:

1. Run `python scripts/real_user_quality_e2e.py` (hub up, real key).
2. Open `data/e2e-real/LATEST/SCORECARD.md` + `TREND.md`.
3. Overall **≥ ~45%** and no hard FAIL on all three is the soft bar; push quality scores up over runs.

This suite is **not** a substitute for `pytest` / `ruff` — it is the **real product feel** gate.
