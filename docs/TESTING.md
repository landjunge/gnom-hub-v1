# Testing

## Unit / integration

```bash
PYTHONPATH=src pytest -q
```

## Mutation testing

### Fast (CI default)

```bash
PYTHONPATH=src python scripts/mutation_check.py
```

### Nightly (mutmut + rank-eval)

Workflow: `.github/workflows/mutation-nightly.yml`

```bash
./scripts/run_mutmut.sh core
PYTHONPATH=src python scripts/vector_rank_eval.py
```

Rank-eval includes **phrase distractors** (same adjacent phrase, wrong sense),
`source_ok@1`, and **avg margin** (top1−top2). Defaults must stay above the
script thresholds — do not weaken the gold set to green CI.


## Smoke

```bash
PYTHONPATH=src python scripts/smoke_e2e.py
```

## User scenarios (server required)

```bash
python scripts/user_scenarios_e2e.py          # S1 + S5
python scripts/user_scenarios_e2e.py --all
```

## CI concurrency (parallel runs)

| Workflow | Rule |
|----------|------|
| `CI/CD` | `concurrency.group = ci-…-{PR\|ref}` — **cancel-in-progress** so only the latest push runs |
| Matrix `test` | `fail-fast: false`; pip cache via `setup-python` (version-scoped, no shared-key race) |
| Lint | Single job (not matrix) — avoids 3× ruff races |
| `ci-ok` | Aggregate gate for branch protection / release |
| Mutation Nightly | Single group `mutation-nightly`, no cancel mid-run |

Do **not** use a bare `actions/cache` key without `${{ matrix.python-version }}` for matrix jobs — parallel cells overwrite each other.

## CI pipeline

| Job | What | Notes |
|-----|------|--------|
| **lint** | Ruff + Mermaid + inventory drift | **Fast install** (`ruff` only) · ∥ with test |
| **test** | Pytest 3.10–3.12 | Full `pip install -e ".[dev]"` |
| **smoke / live** | `smoke_e2e` · optional DeepSeek | **Only Py3.12** |
| **ci-ok** | Branch-protection gate | needs lint + test |
| **mutation-nightly** | mutmut + rank-eval | schedule, not PR |

Local parity:

```bash
ruff check . && ruff format --check .
python scripts/mermaid_check.py
./scripts/prepush_gate.sh          # ruff + mermaid
pytest tests/ -q
python scripts/smoke_e2e.py        # optional local
```

Optimizations: lint ∥ test · no `build` on matrix · junit artifact only on failure · smoke once.

Python/pip caching: [PYTHON_CACHE.md](PYTHON_CACHE.md) · `requirements/ci-lint.txt` · `requirements/ci-dev.txt`.

