# Python cache strategies (Gnom-Hub)

How we cache Python tooling **locally** and in **GitHub Actions** so CI stays fast without stale/wrong wheels.

---

## Goals

| Goal | Approach |
|------|----------|
| Fast CI reinstalls | pip wheel cache keyed by OS + Python + dependency hash |
| No matrix races | **per-Python-version** cache keys (never share 3.10/3.11/3.12) |
| Small lint job | Separate **lint-only** requirements (ruff) |
| Reproducible | Pins in `pyproject.toml`; CI helper files under `requirements/` |
| Safe local dev | Project `.venv` + user pip cache; never commit caches |

---

## Layers (what can be cached)

```text
┌─────────────────────────────────────────────┐
│ 1. pip download/wheel cache                 │  ~/.cache/pip  or CI cache
│ 2. virtualenv site-packages                 │  .venv/        (local only)
│ 3. bytecode                                 │  __pycache__/  (ephemeral)
│ 4. tool caches                              │  .ruff_cache, .pytest_cache
└─────────────────────────────────────────────┘
```

| Layer | Commit? | CI? | Local? |
|-------|---------|-----|--------|
| pip wheels | ❌ | ✅ `setup-python` / `actions/cache` | ✅ automatic |
| `.venv` | ❌ | ❌ recreate each job | ✅ |
| `__pycache__` | ❌ | ❌ `PYTHONDONTWRITEBYTECODE=1` in CI | optional |
| `.pytest_cache` | ❌ | ❌ (not reused across jobs) | ok gitignored |
| `.ruff_cache` | ❌ | ❌ | ok gitignored |

---

## Local development

### Virtualenv (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

- One venv per clone; recreate after major Python upgrades.
- `./scripts/install.sh` should create/use `.venv` the same way.

### pip cache (user-level)

```bash
pip cache dir          # usually ~/.cache/pip
pip cache info
pip cache purge        # nuclear — only if corrupt wheels
```

Env overrides:

```bash
export PIP_CACHE_DIR="$HOME/.cache/pip"          # default-ish
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_DEFAULT_TIMEOUT=60
```

Prefer binaries when available:

```bash
pip install -e ".[dev]" --prefer-binary
```

### Tool caches

| Tool | Location | Clear |
|------|----------|--------|
| Ruff | `.ruff_cache/` | `rm -rf .ruff_cache` |
| Pytest | `.pytest_cache/` | `rm -rf .pytest_cache` |
| mutmut | `.mutmut-cache` / local | see `docs/MUTMUT.md` |

Add to `.gitignore` if missing: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/`.

### When to invalidate locally

| Change | Action |
|--------|--------|
| `pyproject.toml` deps | `pip install -e ".[dev]"` again |
| Python minor upgrade | new `.venv` |
| Weird import/build errors | `pip cache purge` + reinstall |
| Ruff false positives after upgrade | clear `.ruff_cache` |

---

## GitHub Actions (this repo)

Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

### Design

```text
lint job                          test matrix (3.10 / 3.11 / 3.12)
────────                          ───────────────────────────────
ruff-action (binary, no pip)      1) cache .venv  (exact key only)
mermaid stdlib                    2) on miss: cache pip downloads
no pip cache                      then venv + pip install -e ".[dev]"
                                  pytest (+ smoke only 3.12)
```

### Rules we follow

1. **`setup-python` `cache: pip`** — official, version-scoped when `python-version` differs.
2. **`cache-dependency-path`** lists **only** files that change installs:
   - lint → `requirements/ci-lint.txt`
   - test → `pyproject.toml` + `requirements/ci-dev.txt`
3. **Never** one shared cache key across matrix cells without `${{ matrix.python-version }}` (setup-python already scopes by version).
4. **Do not cache** `.venv` across jobs (path + runner image drift).
5. **Do not cache** `data/`, Playwright browsers in default CI (computer extra is optional).
6. Lint stays **tiny** so its cache rarely invalidates when app deps move.

### Helper requirement files

| File | Purpose |
|------|---------|
| [`requirements/ci-lint.txt`](../requirements/ci-lint.txt) | ruff pin only |
| [`requirements/ci-dev.txt`](../requirements/ci-dev.txt) | hash companion for test cache (pins mirror dev extras) |

Source of truth for versions remains **`pyproject.toml`**. When you bump `ruff`/`pytest` there, update the matching line in `requirements/ci-*.txt`.

### Optional: manual `actions/cache` (when to use)

Use only if `setup-python` cache is insufficient (custom paths, multi-ecosystem):

```yaml
- uses: actions/cache@v4
  with:
    path: ${{ env.PIP_CACHE_DIR }}
    key: ${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('pyproject.toml', 'requirements/ci-dev.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-${{ matrix.python-version }}-
      ${{ runner.os }}-pip-
```

We prefer **setup-python’s built-in** pip cache to avoid double-caching.

### Nightly mutation

Same pip cache pattern; longer job. mutmut may write local mutation caches — keep them **off** the shared pip key (workspace artifact only).

---

## Invalidation cheat sheet

| Event | Lint cache | Test cache |
|-------|------------|------------|
| Edit app `.py` only | hit | hit (reinstall -e still quick) |
| Bump `ruff` pin | miss | miss if ci-dev updated |
| Bump `fastapi` | hit | miss |
| Change workflow YAML only | hit | hit |
| New Python in matrix | n/a | new key |

---

---

## Deep CI cache (current)

Implemented in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

### Lint — zero pip

| Piece | Strategy |
|-------|----------|
| Ruff | [`astral-sh/ruff-action@v3`](https://github.com/astral-sh/ruff-action) pin **0.16.1** (binary download, action-cached) |
| Mermaid | CPython 3.12 + stdlib script — **no** package install |
| Pip cache | **Disabled** on purpose (nothing to install) |

Cold lint stays on the order of **seconds**, not minutes.

### Test — two-tier cache

```text
1) actions/cache → .venv
     key = OS + CACHE_SEED + pyX.Y + hash(pyproject.toml, requirements/ci-dev.txt)
     restore-keys: NONE (exact match only)

2) on venv MISS only → actions/cache → $PIP_CACHE_DIR (wheel downloads)
     key = OS + CACHE_SEED + pipdl + pyX.Y + same hash
     restore-keys = same py prefix, then generic pipdl
```

| Event | venv | pipdl |
|-------|------|-------|
| Same deps, 2nd push | **HIT** → skip install | skipped |
| Bump pytest pin | MISS | often partial HIT via restore-keys |
| Edit only `src/**/*.py` | HIT | skipped |
| Bump `CACHE_SEED` (e.g. v2→v3) | global miss | global miss |

### Cache hit install path

- **Miss:** `python -m venv .venv` → `pip install -e ".[dev]"` (`--prefer-binary`, `--upgrade-strategy only-if-needed`)
- **Hit:** verify imports → `pip install --no-deps -e .` (rebinds editable path; **no** dependency resolve)

### What we refuse to cache

| Path | Why |
|------|-----|
| Partial venv restore-keys | Wrong site-packages / silent skew |
| Playwright browsers in PR CI | Huge; computer extra optional |
| `data/` | runtime state, not deps |
| Nested `setup-python` pip cache **and** manual pip path | Double write, confusing hits |

### Bust everything

1. Bump workflow `env.CACHE_SEED` (`v2` → `v3`), or  
2. Change hash inputs (`pyproject.toml` / `requirements/ci-dev.txt`).

### Observability

Each test job writes a summary table:

| Cache | Hit |
|-------|-----|
| venv | true/false |
| pip downloads | true/false/skipped |

### Local parity (not identical)

CI uses **ephemeral `.venv` + Actions cache**. Locally keep a long-lived `.venv` and user pip cache — see above. Same pins via `pip install -e ".[dev]"`.

## Anti-patterns

| Don’t | Why |
|-------|-----|
| Cache entire `$HOME` | Huge, leaky, slow restore |
| Share one pip cache across 3.10+3.11+3.12 without version in key | Wheel ABI mismatches / races |
| Commit `.venv` or wheels | Repo bloat, platform skew |
| `pip install` without pins in CI lint | Random ruff rule drift |
| Cache Playwright browsers in default PR CI | Minutes of download for unused extra |
| Docker image as dev/runtime | **Out of scope** — no Dockerfile; use `.venv` + scripts |

---

## Commands (CI parity local)

```bash
# Lint-class install
pip install -r requirements/ci-lint.txt
ruff check . && ruff format --check .
python scripts/mermaid_check.py

# Full dev (matches test job)
pip install -e ".[dev]"
pytest tests/ -q
```

See also: [TESTING.md](TESTING.md) · [AGENTS.md](../AGENTS.md) · [MERMAID.md](MERMAID.md) automation.
