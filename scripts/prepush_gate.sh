#!/usr/bin/env bash
# Shared pre-push / local gate (matches CI lint job + AGENTS.md Ruff gate).
#
# Usage:
#   ./scripts/prepush_gate.sh           # check only (default)
#   ./scripts/prepush_gate.sh --fix    # ruff format . then re-check
#   GNOM_PREPUSH_PYTEST=1 ./scripts/prepush_gate.sh   # also pytest -q
#
# Called by: .githooks/pre-push
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FIX=0
for arg in "$@"; do
  case "$arg" in
    --fix|-f) FIX=1 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
  esac
done

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Prefer venv ruff, then PATH, then python -m ruff
run_ruff() {
  if [ -x .venv/bin/ruff ]; then
    .venv/bin/ruff "$@"
  elif command -v ruff >/dev/null 2>&1; then
    ruff "$@"
  else
    python -m ruff "$@"
  fi
}

if ! run_ruff --version >/dev/null 2>&1; then
  echo "prepush_gate: ruff not found." >&2
  echo "  pip install -e '.[dev]'   # pins ruff==0.16.1" >&2
  exit 1
fi

if [ "$FIX" -eq 1 ]; then
  echo "▸ prepush_gate: ruff check . --fix"
  run_ruff check . --fix || true
  echo "▸ prepush_gate: ruff format ."
  run_ruff format .
fi

echo "▸ prepush_gate: ruff check ."
if ! run_ruff check .; then
  echo "" >&2
  echo "❌ ruff check failed. Fix with:" >&2
  echo "  ruff check . --fix" >&2
  echo "  ruff check . --fix --unsafe-fixes   # if still red" >&2
  echo "  ./scripts/prepush_gate.sh --fix" >&2
  exit 1
fi

echo "▸ prepush_gate: ruff format --check ."
if ! run_ruff format --check .; then
  echo "" >&2
  echo "❌ ruff format drift. Fix with:" >&2
  echo "  ruff format ." >&2
  echo "  ./scripts/prepush_gate.sh --fix" >&2
  exit 1
fi

# Mermaid docs gate (static). Skip with GNOM_PREPUSH_MERMAID=0
if [ "${GNOM_PREPUSH_MERMAID:-1}" != "0" ] && [ "${GNOM_PREPUSH_MERMAID:-}" != "false" ]; then
  echo "▸ prepush_gate: mermaid_check"
  if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
  else
    PY=python
  fi
  if ! "$PY" scripts/mermaid_check.py; then
    echo "" >&2
    echo "❌ mermaid_check failed. See docs/MERMAID.md" >&2
    echo "  python scripts/mermaid_check.py --list" >&2
    exit 1
  fi
fi


# ESLint UI gate (max-warnings 0). Skip with GNOM_PREPUSH_ESLINT=0
if [ "${GNOM_PREPUSH_ESLINT:-1}" != "0" ] && [ "${GNOM_PREPUSH_ESLINT:-}" != "false" ]; then
  if [ -f package.json ] && command -v npm >/dev/null 2>&1; then
    if [ ! -d node_modules/eslint ]; then
      echo "▸ prepush_gate: npm ci (eslint)"
      npm ci --silent
    fi
    echo "▸ prepush_gate: npm run lint:js"
    if ! npm run lint:js; then
      echo "" >&2
      echo "❌ ESLint failed (max-warnings 0). Fix UI JS, then:" >&2
      echo "  npm run lint:js" >&2
      echo "  python3 scripts/build_ui_js.py   # after editing parts/" >&2
      exit 1
    fi
  else
    echo "▸ prepush_gate: eslint skipped (no npm)"
  fi
fi

if [ "${GNOM_PREPUSH_PYTEST:-}" = "1" ] || [ "${GNOM_PREPUSH_PYTEST:-}" = "true" ]; then
  echo "▸ prepush_gate: pytest (GNOM_PREPUSH_PYTEST=1)"
  export PYTHONPATH="${PYTHONPATH:-}:src"
  if [ -x .venv/bin/pytest ]; then
    .venv/bin/pytest tests/ -q --tb=line
  else
    python -m pytest tests/ -q --tb=line
  fi
fi

echo "✅ prepush_gate: OK"
exit 0
