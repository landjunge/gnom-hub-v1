# mutmut configuration (deep)

Gnom-Hub uses **two layers** of mutation testing:

| Layer | Command | When |
|-------|---------|------|
| Fast AST | `python scripts/mutation_check.py` | Every PR / CI |
| Deep mutmut | `./scripts/run_mutmut.sh [profile]` | Manual / release |

## Config source

All default mutmut keys live in `pyproject.toml` → `[tool.mutmut]`.

### Key settings

| Key | Purpose |
|-----|---------|
| `paths_to_mutate` | Default: `roles_helpers.py` only |
| `paths_to_exclude` | tests, UI static, data, venv |
| `runner` | pytest + `PYTHONPATH=src` + `--assert=plain` + focused tests |
| `enable_mutation_types` | operator/keyword/name/string/and/or… (no decorator noise) |
| `test_time_multiplier` / `test_time_base` | Timeout = baseline×2.5 + 1s |
| `pre_mutation` / `post_mutation` | `scripts/mutmut_hooks.py` clears `__pycache__` |
| `simple_output` / `no_progress` / `swallow_output` | Quiet CI logs |

### Runner suite (core)

- `test_flex_wish_filter`
- `test_needs_clarify`
- `test_flex_pipeline`
- `test_warm` / `test_warm_trim`
- `test_vector_bm25`

## Profiles (`run_mutmut.sh`)

| Profile | Paths | Suite |
|---------|-------|--------|
| `core` (default) | `roles_helpers.py` | core suite |
| `flex` | same as core | same |
| `memory` | helpers + `warm.py` + `facade.py` | + sqlite/memory tests |
| `wide` | helpers + `roles.py` + memory + sqlite_store | + pipeline/agents |

```bash
./scripts/run_mutmut.sh
./scripts/run_mutmut.sh memory
./scripts/run_mutmut.sh wide
MUTMUT_PATHS=src/gnom_hub/memory/warm.py ./scripts/run_mutmut.sh core
./scripts/run_mutmut.sh results
./scripts/run_mutmut.sh html
./scripts/run_mutmut.sh show 12
./scripts/run_mutmut.sh junit
```

## Interpreting results

```text
killed     — tests caught the mutant (good)
survived   — strengthen tests
timeout    — treated as killed (runaway mutant)
suspicious — slow but not fatal
```

Workflow for a survivor:

1. `mutmut show <id>` — see the diff  
2. Add/adjust a unit test that would fail on that change  
3. Re-run `./scripts/run_mutmut.sh` or the fast `mutation_check.py`

## Artifacts (gitignored)

- `.mutmut-cache` — mutant database  
- `html/` — from `mutmut html`  
- `mutmut-junit.xml` — CI export  

## Relation to Stryker

No Stryker-Python. mutmut ≈ Stryker’s role for this repo; see chat notes / TESTING.md.


## Hooks (implementation)

### Shell — `scripts/mutmut_hooks.py`

| Phase | Action |
|-------|--------|
| **pre** | clear `gnom_hub/**/__pycache__` + `*.pyc`, remove orphan `*.bak`, require `src/gnom_hub` |
| **post** | same cleanup after mutmut restores the source file |

```toml
pre_mutation = "python scripts/mutmut_hooks.py pre"
post_mutation = "python scripts/mutmut_hooks.py post"
```

`MUTMUT_HOOK_QUIET=1` silences log lines (stdout still ok for mutmut).

### In-process — `mutmut_config.py` (repo root)

mutmut imports this automatically. `pre_mutation(context)` can set `context.skip = True` for:

- empty / comment lines
- `mutmut skip` / `pragma: no mutmut` markers
- single-line docstrings
- debug `print(...)` lines

Skips are **not** killed/survived — they are excluded from the score.
