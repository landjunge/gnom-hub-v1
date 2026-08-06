#!/bin/sh
# Deep mutation testing via mutmut (optional, slower).
# Prefer: python scripts/mutation_check.py  (fast pure-helper AST check)
#
# Usage:
#   ./scripts/run_mutmut.sh              # uses [tool.mutmut] from pyproject.toml
#   ./scripts/run_mutmut.sh --help
#   ./scripts/run_mutmut.sh 42           # re-check single mutant id
#   MUTMUT_PATHS=src/gnom_hub/memory/warm.py ./scripts/run_mutmut.sh
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONDONTWRITEBYTECODE=1

if ! command -v mutmut >/dev/null 2>&1; then
  echo "mutmut not installed. pip install 'mutmut==2.4.5' or: pip install -e '.[dev]'"
  exit 1
fi

# Ensure tomli/toml available for pyproject read (mutmut uses toml)
python -c "import toml" 2>/dev/null || pip install -q toml

ARGS=""
if [ -n "${MUTMUT_PATHS:-}" ]; then
  ARGS="$ARGS --paths-to-mutate=${MUTMUT_PATHS}"
fi

# Default: respect pyproject [tool.mutmut]; pass through extra CLI args
# --CI keeps exit 0 unless fatal (survived mutants still show in results)
mutmut run --CI $ARGS "$@"
echo ""
echo "=== mutmut results ==="
mutmut results || true
echo ""
echo "Tip: mutmut show <id> | mutmut apply <id> | mutmut html"
