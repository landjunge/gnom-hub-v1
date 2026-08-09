# Agent notes (Gnom-Hub v1)

## Coding rules (mandatory)

1. **ALWAYS run `ruff format .` before every commit.** No exceptions.
   CI runs `ruff format --check .` and will fail on unformatted files.
   - **UI JS:** edit `src/gnom_hub/ui/static/parts/*.js`, then run `python scripts/build_ui_js.py` (rebuilds `app.js`).
2. **After every completed step: commit AND push** to `origin/main`
   (or open a PR when the user asks for a branch/PR).
   - Do not wait for an explicit “push” request unless the user wants a PR workflow.
   - Message style: `feat(0.x): …` / `fix: …` / `docs: …`
3. **Stay inside `docs/V1_SCOPE.md`.** Do not implement pre-plan features.
4. **YAGNI + KISS** — no overengineering.
5. **line-length = 100** (see `pyproject.toml`). Break long assert/expressions accordingly.
6. **Ruff + tests before every commit/push (do not skip)** — see [Ruff gate](#ruff-gate-mandatory) below.
7. Never commit `Key.txt` / `.env` / real secrets / `User/user.db`.

## Ruff gate (mandatory)

Pinned: **`ruff==0.16.1`** (`pyproject.toml` → optional-dependencies `dev`).

### Identify errors

```bash
# Activate venv if present
source .venv/bin/activate   # or: .venv/bin/ruff …

# Which files have issues (names only)
ruff check . --show-files

# Full diagnostics
ruff check .

# Counts by rule
ruff check . --statistics

# Format drift (CI fails on this)
ruff format --check .
```

### Auto-fix

```bash
# Safe auto-fixes (imports, unused, etc.)
ruff check . --fix

# Also apply “unsafe” fixes when remaining count is small and reviewable
ruff check . --fix --unsafe-fixes

# Format entire tree (always after fixes)
ruff format .

# Must be clean before push
ruff check .
ruff format --check .
```

### Full pre-push checklist

```bash
ruff check .
ruff format .
ruff format --check .
pytest tests/ -q --tb=short
# if server up: python scripts/basic_tests.py   # B1–B3
# full gate:    ./scripts/quality_check.sh
```

Never push with ruff/format/pytest red.

### Git hooks (local, automated)

Versioned hooks live in **`.githooks/`**. **Install once per clone** (agents: first step after clone):

```bash
./scripts/install_git_hooks.sh
# sets: git config core.hooksPath .githooks
```

| Hook | When | Runs |
|------|------|------|
| **pre-commit** | commit with staged `.py` / `pyproject` / `plugins/*` | `scripts/prepush_gate.sh` |
| **pre-push** | every `git push` | `scripts/prepush_gate.sh` |

Gate body (`scripts/prepush_gate.sh`) — same as CI lint:

```text
ruff check .
ruff format --check .
```

```bash
./scripts/prepush_gate.sh          # dry-run
./scripts/prepush_gate.sh --fix   # format + re-check
GNOM_PREPUSH_PYTEST=1 ./scripts/prepush_gate.sh   # optional tests
```

- **Fail** → commit/push aborted. Fix, then retry.
- **Emergency skip only:** `git push --no-verify` / `git commit --no-verify` (not normal workflow).
- Hooks do **not** replace full `quality_check.sh`; still run it before claiming done.

CI mirrors the same ruff commands (`.github/workflows/ci.yml` → job `lint`).

### Git safe.directory (dubious ownership)

If Git says **detected dubious ownership** (USB stick, container, different user than clone owner):

```bash
./scripts/ensure_git_safe_directory.sh          # this repo → global safe.directory
./scripts/install_git_hooks.sh                  # also runs the above
# Dev VM / sandbox only:
GNOM_SAFE_DIRECTORY_STAR=1 ./scripts/ensure_git_safe_directory.sh
```

- Prefer **one concrete path** over `*`.
- Idempotent; does not wipe other `safe.directory` entries.
- Does **not** replace auth/SSH — only ownership trust for local git operations.


## Product rules

- UI: Basic English; Box-1 content multi-language ready.
- Free models only when user enables them; budget protection on.
- One global Save button only.
- Pipeline target:

```
Chat → Brainstorm → Distillation → [Execute] → Coordinator → Worker(s) → Box 3 + Memory
```

- **Presets freeze:** Team/Worker presets + `plan_mode` only. No workflow engine, skill files, or second orchestrator. See [`docs/WORKFLOWS_AND_PRESETS.md`](docs/WORKFLOWS_AND_PRESETS.md).

## Real-user quality (fixed — agent plays the user)

**Primary product feel gate** — visible UI, mouse + keyboard, score Brainstorm / Flex / Result + trend:

- **Doc:** [`docs/REAL_USER_QUALITY.md`](docs/REAL_USER_QUALITY.md)
- **Suite:** `python scripts/real_user_quality_e2e.py` (**headed by default** — watch the browser)
- **Artifacts:** `data/e2e-real/LATEST/SCORECARD.md` + `TREND.md` + `scores.json`
- **When:** after pipeline / Flex / brainstorm / Box 2–3 / chat-busy changes; before claiming quality improved
- **Rule:** compare TREND to previous LATEST — document ↑/↓, do not claim better without a run

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
