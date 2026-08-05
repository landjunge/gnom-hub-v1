#!/usr/bin/env bash
# Start Gnom-Hub v1 (desktop UI on :8080 by default)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export PYTHONPATH="${PYTHONPATH:-}:src"
HOST="${GNOM_HUB_HOST:-127.0.0.1}"
PORT="${GNOM_HUB_PORT:-8080}"

exec python -m gnom_hub.main --host "$HOST" --port "$PORT"
