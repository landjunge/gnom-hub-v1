#!/usr/bin/env bash
# Start Gnom-Hub v1 (desktop UI, default :8080)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Prefer project Key.txt / .env
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
HOST="${GNOM_HUB_HOST:-127.0.0.1}"
PORT="${GNOM_HUB_PORT:-8080}"

echo "Gnom-Hub v1 → http://${HOST}:${PORT}/"
echo "  Send = brainstorm · Execute = workers · System = keys/backup/clean"
exec python -m gnom_hub.main --host "$HOST" --port "$PORT"
