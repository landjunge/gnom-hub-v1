#!/usr/bin/env bash
# Minimal install for Gnom-Hub v1 (USB-friendly, relative paths)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      PY="$c"
      break
    fi
  done
fi
if [ -z "$PY" ]; then
  echo "Python 3.10+ required" >&2
  exit 1
fi

echo "Using $PY"
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

if [ ! -f Key.txt ] && [ -f Key.txt.example ]; then
  cp Key.txt.example Key.txt
  echo "Created Key.txt from example — add DEEPSEEK_API_KEY"
fi

echo ""
echo "OK. Start with:"
echo "  source .venv/bin/activate"
echo "  ./scripts/start.sh"
echo "  → http://127.0.0.1:8080/"
