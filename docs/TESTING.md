# Testing

## Unit / integration

```bash
PYTHONPATH=src pytest -q
```

## Mutation testing

### Fast (CI default) — pure-helper AST mutations

Scoped to Flex/clarify helpers; **must kill all** mutants:

```bash
python scripts/mutation_check.py
# or
PYTHONPATH=src pytest -q tests/test_mutation_helpers.py
```

### Deep — mutmut

Config lives in `pyproject.toml` → `[tool.mutmut]`:

| Key | Value |
|-----|--------|
| `paths_to_mutate` | `src/gnom_hub/agents/roles_helpers.py` |
| `runner` | focused pytest + `PYTHONPATH=src` + `--assert=plain` |
| `tests_dir` | `tests/` |
| `test_time_multiplier` | `2.0` |
| `disable_mutation_types` | `decorator` |

```bash
pip install 'mutmut==2.4.5' toml   # or pip install -e ".[dev]"
./scripts/run_mutmut.sh
mutmut results
mutmut html          # optional HTML under html/
```

Override mutate paths without editing config:

```bash
MUTMUT_PATHS=src/gnom_hub/memory/warm.py ./scripts/run_mutmut.sh
# or
mutmut run --paths-to-mutate=src/gnom_hub/agents/roles_helpers.py
```

**Note:** Prefer the fast `mutation_check.py` in CI. Use mutmut for exploratory deep dives.
