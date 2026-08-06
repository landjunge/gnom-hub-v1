#!/bin/sh
# Deep mutation testing via mutmut (optional, slower).
# Prefer: python scripts/mutation_check.py  (fast pure-helper check)
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH=src
if ! command -v mutmut >/dev/null 2>&1; then
  echo "mutmut not installed. pip install 'mutmut==2.4.5' or pip install -e '.[dev]'"
  exit 1
fi
mutmut run --paths-to-mutate="src/gnom_hub/agents/roles_helpers.py" \
  --runner="python -m pytest -x -q --tb=line tests/test_flex_wish_filter.py tests/test_needs_clarify.py tests/test_flex_pipeline.py" \
  --tests-dir=tests/ \
  --CI \
  "$@"
mutmut results || true
