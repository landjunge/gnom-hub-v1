# Real-user quality suite (fixed development gate)

Three **absolute real** frontend journeys. The runner **is the user** (mouse + keyboard on the live Web UI). You watch in real time when headed mode is on.

## What is measured

| Dimension | What “good” means |
|-----------|-------------------|
| **Brainstorm** | Box 2 dialogue is useful, on-topic, structured |
| **Flex** | Personal notes / wishes appear and influence requirements |
| **Result** | Real Box 3 deliverable (length, HTML, interactions when expected) |

Each scenario scores **0–10** per dimension → **% overall**.  
Each run is compared to `data/e2e-real/LATEST/scores.json` → **↑ better / ↓ worse / → same**.

## Scenarios (fixed)

| ID | Role-play | Intent |
|----|-----------|--------|
| **R1** | Soft café idea → decide landing → execute | Brainstorm dialogue + commit |
| **R2** | Clear todo-app build order | Hard intent → strong result |
| **R3** | Warm wish (dark + German) + portfolio page | Flex notices preference |

## Run (watchable)

```bash
./scripts/start.sh          # hub :8080, real LLM preferred
source .venv/bin/activate
python scripts/real_user_quality_e2e.py
```

- **Headed by default** (`GNOM_E2E_HEADED=1`) — Chromium window, slow typing.
- Headless: `GNOM_E2E_HEADED=0 python scripts/real_user_quality_e2e.py`
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
