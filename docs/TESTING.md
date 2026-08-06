# Testing

## Unit / integration

```bash
PYTHONPATH=src pytest -q
```

## Mutation testing

### Fast (CI default)

```bash
python scripts/mutation_check.py
PYTHONPATH=src pytest -q tests/test_mutation_helpers.py
```

Scoped AST mutants on Flex/clarify helpers — **all must be killed**.

### Deep (mutmut)

Full config: **[docs/MUTMUT.md](MUTMUT.md)** and `pyproject.toml` `[tool.mutmut]`.

```bash
pip install 'mutmut==2.4.5' toml   # or pip install -e ".[dev]"
./scripts/run_mutmut.sh            # profile core
./scripts/run_mutmut.sh memory     # warm + facade
./scripts/run_mutmut.sh wide       # broader (slow)
./scripts/run_mutmut.sh results
./scripts/run_mutmut.sh html
```

**CI:** keep the fast check. mutmut is optional/manual unless you add a nightly job.
