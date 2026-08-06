# Testing

## Unit / integration

```bash
PYTHONPATH=src pytest -q
```

## Mutation testing

Fast (CI-friendly) pure-helper mutations:

```bash
python scripts/mutation_check.py
# or
PYTHONPATH=src pytest -q tests/test_mutation_helpers.py
```

Deep (optional, mutmut):

```bash
pip install 'mutmut==2.4.5'   # or pip install -e ".[dev]"
./scripts/run_mutmut.sh
mutmut results
mutmut html   # optional HTML report
```

Config: `[tool.mutmut]` in `pyproject.toml` (roles_helpers + facade).
Targets: Flex-wish filter, clarify heuristics, related pure functions.
