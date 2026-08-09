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
cache key: OS + py3.12            cache key: OS + pyX.Y
           + hash(ci-lint.txt)               + hash(pyproject + ci-dev.txt)
pip install -r requirements/      pip install -e ".[dev]"
  ci-lint.txt                     (wheels come from cache)
ruff + mermaid_check              pytest  (+ smoke only 3.12)
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

## Anti-patterns

| Don’t | Why |
|-------|-----|
| Cache entire `$HOME` | Huge, leaky, slow restore |
| Share one pip cache across 3.10+3.11+3.12 without version in key | Wheel ABI mismatches / races |
| Commit `.venv` or wheels | Repo bloat, platform skew |
| `pip install` without pins in CI lint | Random ruff rule drift |
| Cache Playwright browsers in default PR CI | Minutes of download for unused extra |

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
