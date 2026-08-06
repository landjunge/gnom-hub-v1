#!/bin/sh
# Deep mutation testing via mutmut (optional, slower).
# Prefer: python scripts/mutation_check.py  (fast pure-helper AST check)
#
# Usage:
#   ./scripts/run_mutmut.sh                 # profile=core (default, pyproject)
#   ./scripts/run_mutmut.sh core
#   ./scripts/run_mutmut.sh flex            # helpers + roles Flex bits (same helpers file)
#   ./scripts/run_mutmut.sh memory          # warm + facade + helpers
#   ./scripts/run_mutmut.sh wide            # broader agents/memory (slow)
#   ./scripts/run_mutmut.sh results         # print cache results only
#   ./scripts/run_mutmut.sh html            # HTML report
#   ./scripts/run_mutmut.sh show 12
#   MUTMUT_PATHS=path1,path2 ./scripts/run_mutmut.sh
#   ./scripts/run_mutmut.sh core -- --swallow-output  # extra mutmut flags after --
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-src}"
export PYTHONDONTWRITEBYTECODE=1

if ! command -v mutmut >/dev/null 2>&1; then
  echo "mutmut not installed. pip install 'mutmut==2.4.5' toml  or: pip install -e '.[dev]'"
  exit 1
fi
python -c "import toml" 2>/dev/null || pip install -q toml

PROFILE="core"
if [ "$#" -gt 0 ]; then
  case "$1" in
    core|flex|memory|wide|results|html|show|junit)
      PROFILE="$1"
      shift
      ;;
  esac
fi

# Extra args after -- go to mutmut; without --, remaining go to mutmut run
EXTRA=""
if [ "$#" -gt 0 ]; then
  if [ "$1" = "--" ]; then
    shift
  fi
  EXTRA="$*"
fi

PATHS_CORE="src/gnom_hub/agents/roles_helpers.py"
PATHS_MEMORY="src/gnom_hub/agents/roles_helpers.py,src/gnom_hub/memory/warm.py,src/gnom_hub/memory/facade.py"
PATHS_WIDE="src/gnom_hub/agents/roles_helpers.py,src/gnom_hub/agents/roles.py,src/gnom_hub/memory/warm.py,src/gnom_hub/memory/facade.py,src/gnom_hub/memory/sqlite_store.py"

case "$PROFILE" in
  results)
    mutmut results
    exit 0
    ;;
  html)
    mutmut html
    echo "HTML written (see mutmut html output / html/)."
    exit 0
    ;;
  show)
    # shellcheck disable=SC2086
    mutmut show $EXTRA
    exit 0
    ;;
  junit)
    mutmut junitxml > mutmut-junit.xml
    echo "Wrote mutmut-junit.xml"
    exit 0
    ;;
  core|flex)
    PATHS="${MUTMUT_PATHS:-$PATHS_CORE}"
    ;;
  memory)
    PATHS="${MUTMUT_PATHS:-$PATHS_MEMORY}"
    # wider suite for memory modules
    export MUTMUT_RUNNER_OVERRIDE="env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m pytest -x -q --tb=line --assert=plain -p no:cacheprovider tests/test_flex_wish_filter.py tests/test_needs_clarify.py tests/test_flex_pipeline.py tests/test_warm.py tests/test_warm_trim.py tests/test_vector_bm25.py tests/test_sqlite_storage.py tests/test_memory.py"
    ;;
  wide)
    PATHS="${MUTMUT_PATHS:-$PATHS_WIDE}"
    export MUTMUT_RUNNER_OVERRIDE="env PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -m pytest -x -q --tb=line --assert=plain -p no:cacheprovider tests/test_flex_wish_filter.py tests/test_needs_clarify.py tests/test_flex_pipeline.py tests/test_pipeline.py tests/test_warm.py tests/test_warm_trim.py tests/test_vector_bm25.py tests/test_sqlite_storage.py tests/test_memory.py tests/test_agents.py"
    ;;
  *)
    echo "Unknown profile: $PROFILE"
    exit 2
    ;;
esac

echo "mutmut profile=$PROFILE paths=$PATHS"
echo "Note: pyproject [tool.mutmut] supplies runner/types/timeouts; profile may override paths."

RUNNER_ARGS=""
if [ -n "${MUTMUT_RUNNER_OVERRIDE:-}" ]; then
  RUNNER_ARGS="--runner=${MUTMUT_RUNNER_OVERRIDE}"
fi

# shellcheck disable=SC2086
mutmut run --CI --paths-to-mutate="$PATHS" $RUNNER_ARGS $EXTRA

echo ""
echo "=== mutmut results (profile=$PROFILE) ==="
mutmut results || true
echo ""
echo "Tips:"
echo "  mutmut show <id>     # diff for a survivor"
echo "  ./scripts/run_mutmut.sh html"
echo "  ./scripts/run_mutmut.sh junit"
echo "  python scripts/mutation_check.py   # fast scoped check"
