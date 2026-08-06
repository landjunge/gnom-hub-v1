# Agent notes (Gnom-Hub v1)

## Coding rules (mandatory)

1. **ALWAYS run `ruff format .` before every commit.** No exceptions.
   CI runs `ruff format --check .` and will fail on unformatted files.
   - **UI JS:** edit `src/gnom_hub/ui/static/parts/*.js`, then run `python scripts/build_ui_js.py` (rebuilds `app.js`).
2. **After every completed step: commit AND push** to `origin/main`.
   - Do not wait for an explicit “push” request.
   - Message style: `feat(0.x): …` / `fix: …` / `docs: …`
3. **Stay inside `docs/V1_SCOPE.md`.** Do not implement pre-plan features.
4. **YAGNI + KISS** — no overengineering.
5. **line-length = 100** (see `pyproject.toml`). Break long assert/expressions accordingly.
6. **Run before every commit/push (do not skip):**
   ```bash
   ruff check .
   ruff format .
   ruff format --check .
   pytest tests/ -q --tb=short
   # if server up: python scripts/basic_tests.py   # B1–B3
   ```
   Never push with ruff/format/pytest red. Never commit `Key.txt` / `.env` / real secrets.

## Product rules

- UI: Basic English; Box-1 content multi-language ready.
- Free models only when user enables them; budget protection on.
- One global Save button only.
- Pipeline target:

```
Chat → Brainstorm → Distillation → [Execute] → Coordinator → Worker(s) → Box 3 + Memory
```

- **Presets freeze:** Team/Worker presets + `plan_mode` only. No workflow engine, skill files, or second orchestrator. See [`docs/WORKFLOWS_AND_PRESETS.md`](docs/WORKFLOWS_AND_PRESETS.md).

## Basic user test (remember)

Canonical real-user regression — **Playwright on UI + Gnom Tools**:

- **Doc:** [`docs/BASIC_USER_TEST.md`](docs/BASIC_USER_TEST.md)
- **Suite:** `python scripts/user_scenarios_e2e.py` (default **S1 landing + S5 tools/computer-use**)
- **Full:** `python scripts/user_scenarios_e2e.py --all` or `GNOM_E2E_ALL=1 ./scripts/quality_check.sh`
- **Must pass:** Box 2 brainstorm, Execute after Send, ≥1 worker; S5 tools API + Tools modal + computer-use endpoint
- **Hard rule:** S1 is **not** PASS without an openable `data/e2e-scenarios/LATEST_RESULT/RESULT.html` (≥800 chars worker body). Panel chrome alone = FAIL. Agents must notice empty/missing deliverables without the user pointing it out.
- **quality_check:** with server up, user scenarios are a **hard gate** (no `|| true`). Skip only with `GNOM_E2E_SKIP=1`.
- **Known pitfall:** after brainstorm, Execute must re-enable when `chatBusy` clears (`lastCanExecute`)
- Re-run when touching chat busy, Execute, Box 3, Tools modal, or computer-use

## Keys & models (do not re-research)

**Single reference:** [`docs/KEYS_AND_MODELS.md`](docs/KEYS_AND_MODELS.md)

- Default model: **`deepseek-v4-flash`** (official DeepSeek API id)
- **Simple split:** hub = work/Clear; sibling `WS-gnom-hub-v1` (or `GNOM_WS=`) = Key + live DB + selected HTML
- **No legacy seed chains** (no `~/.local`, no hub/User live store)
- **Copy:** HTML → `{WS}/selected/` · **Clear** does not touch WS
- Keys: `DEEPSEEK_API_KEY` (system) + `WORKER_API_KEY` (workers) + `DEEPSEEK_MODEL`
- Thinking **off** by default (`DEEPSEEK_THINKING=0`) — empty content with v4-flash was a real issue
- Never commit real keys / `User/user.db`; never invent model ids — update that doc when DeepSeek changes IDs

## Stability (track A)

**Checklist:** [`docs/STABILITY.md`](docs/STABILITY.md)

Before calling work “done” on chat/LLM/pipeline: `quality_check.sh` + when relevant `user_landing_e2e.py`.
