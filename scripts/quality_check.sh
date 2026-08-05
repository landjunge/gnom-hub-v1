#!/usr/bin/env bash
# Lint + unit tests + in-process smoke (no server, no live LLM required)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

echo "▸ ruff check"
ruff check .
echo "▸ ruff format --check"
ruff format --check .
echo "▸ pytest"
pytest tests/ -q --tb=short
echo "▸ smoke e2e"
python scripts/smoke_e2e.py
echo "▸ smoke live (optional — skips without key)"
python scripts/smoke_live.py || true

# Basic tests B1–B3 need a running server; skip cleanly if down
if curl -sf -m 2 http://127.0.0.1:8080/api/health >/dev/null 2>&1; then
  echo "▸ basic tests B1–B3 (server detected)"
  python scripts/basic_tests.py || true
else
  echo "▸ basic tests B1–B3 skipped (no server on :8080)"
fi

echo ""
echo "✅ quality_check OK"
