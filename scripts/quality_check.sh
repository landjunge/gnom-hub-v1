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

echo ""
echo "✅ quality_check OK"
