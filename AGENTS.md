# Agent notes (Gnom-Hub v1)

## Coding rules (mandatory)

1. **ALWAYS run `ruff format .` before every commit.** No exceptions.
   CI runs `ruff format --check .` and will fail on unformatted files.
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

## Basic user test (remember)

Canonical real-user regression (keyboard chat → landing page):

- **Doc:** [`docs/BASIC_USER_TEST.md`](docs/BASIC_USER_TEST.md)
- **Script:** `python scripts/user_landing_e2e.py` (Playwright + live server + LLM key)
- **Must pass criteria:** brainstorm Box 2 non-empty, Execute works after Send, ≥1 worker panel, no pipeline error
- **Known pitfall fixed in 3.7.1:** after brainstorm, Execute must re-enable when `chatBusy` clears (`lastCanExecute`)
- Re-run this script when touching chat busy, Execute button, pipeline stages, or Box 3

## Keys & models (do not re-research)

**Single reference:** [`docs/KEYS_AND_MODELS.md`](docs/KEYS_AND_MODELS.md)

- Default model: **`deepseek-v4-flash`** (official DeepSeek API id)
- `Key.txt`: `DEEPSEEK_API_KEY` (system) + `WORKER_API_KEY` (workers) + `DEEPSEEK_MODEL`
- Thinking **off** by default (`DEEPSEEK_THINKING=0`) — empty content with v4-flash was a real issue
- Never commit real keys; never invent model ids — update that doc when DeepSeek changes IDs

## Stability (track A)

**Checklist:** [`docs/STABILITY.md`](docs/STABILITY.md)

Before calling work “done” on chat/LLM/pipeline: `quality_check.sh` + when relevant `user_landing_e2e.py`.
