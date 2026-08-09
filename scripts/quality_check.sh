#!/usr/bin/env bash
# Lint + unit tests + in-process smoke (no server, no live LLM required)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Ruff gate (same as pre-push)
bash "$ROOT/scripts/prepush_gate.sh"

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

echo "▸ mermaid_check"
python scripts/mermaid_check.py --write-inventory docs/generated/mermaid_inventory.md

echo "▸ pytest"
pytest tests/ -q --tb=short
echo "▸ smoke e2e"
python scripts/smoke_e2e.py
echo "▸ smoke live (optional — skips without key)"
python scripts/smoke_live.py || true

# Live hub gates (need server on :8080)
# User scenarios FAIL the gate when server is up — do not swallow with || true.
# Soft-skip only when GNOM_E2E_SKIP=1 (e.g. no LLM budget / no playwright).
if curl -sf -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1; then
  echo "▸ basic tests B1–B3 (API + light UI)"
  python scripts/basic_tests.py
  if [ "${GNOM_E2E_SKIP:-0}" = "1" ] || [ "${GNOM_E2E_SKIP:-}" = "true" ]; then
    echo "▸ user scenarios E2E skipped (GNOM_E2E_SKIP=1)"
  else
    echo "▸ user scenarios E2E (Playwright + Tools) — hard gate"
    if [ "${GNOM_E2E_ALL:-0}" = "1" ] || [ "${GNOM_E2E_ALL:-}" = "true" ]; then
      python scripts/user_scenarios_e2e.py --all
    else
      python scripts/user_scenarios_e2e.py --only 1,5
    fi
    # Human-visible deliverable must exist after S1
    if [ ! -f data/e2e-scenarios/LATEST_RESULT/RESULT.html ]; then
      echo "FAIL: no data/e2e-scenarios/LATEST_RESULT/RESULT.html after E2E"
      exit 1
    fi
    echo "▸ deliverable: data/e2e-scenarios/LATEST_RESULT/RESULT.html"
  fi
else
  echo "▸ basic tests + user scenarios skipped (no server on :8080)"
fi

echo ""
echo "✅ quality_check OK"
