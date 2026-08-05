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
6. **Run before committing:**
   ```bash
   ruff check .
   ruff format .
   pytest tests/ -v --tb=short
   ```

## Product rules

- UI: Basic English; Box-1 content multi-language ready.
- Free models only when user enables them; budget protection on.
- One global Save button only.
- Pipeline target:

```
Chat → Brainstorm → Distillation → [Execute] → Coordinator → Worker(s) → Box 3 + Memory
```
