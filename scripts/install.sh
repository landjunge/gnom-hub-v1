#!/usr/bin/env bash
# Gnom-Hub v1 install — USB-friendly, relative paths, simple detection
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Gnom-Hub v1 install ==="
echo "Root: $ROOT"

# OS
OS_NAME="$(uname -s 2>/dev/null || echo unknown)"
case "$OS_NAME" in
  Darwin) OS_LABEL="macOS" ;;
  Linux)  OS_LABEL="Linux" ;;
  *)      OS_LABEL="$OS_NAME" ;;
esac
echo "OS:   $OS_LABEL"

# USB / removable heuristic (informational only)
ON_USB="no"
if [[ "$ROOT" == /Volumes/* ]] || [[ "$ROOT" == /media/* ]] || [[ "$ROOT" == /run/media/* ]] \
  || [[ "$ROOT" == /mnt/* ]]; then
  ON_USB="likely (path under mount)"
fi
echo "USB:  $ON_USB"

# Python 3.10+
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
  echo "ERROR: Python 3.10+ required" >&2
  exit 1
fi
VER="$("$PY" -c 'import sys; print("%d.%d"%sys.version_info[:2])')"
echo "Python: $PY ($VER)"
"$PY" -c 'import sys; assert sys.version_info >= (3,10), "need 3.10+"'

# LLM profile hint
echo ""
echo "LLM profiles (pick one when you add keys):"
echo "  slim     — DeepSeek API only (cloud, smallest local footprint)"
echo "  medium   — DeepSeek + optional Telegram"
echo "  full     — + God-Mode / computer-use experiments (still local process)"
echo "  local*   — bring your own Ollama later (not bundled in v1)"

# venv
if [ ! -d .venv ]; then
  echo ""
  echo "Creating .venv …"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip -q
pip install -e ".[dev]" -q

# Key.txt
if [ ! -f Key.txt ] && [ -f Key.txt.example ]; then
  cp Key.txt.example Key.txt
  echo "Created Key.txt from example — add DEEPSEEK_API_KEY=sk-..."
elif [ ! -f Key.txt ]; then
  printf '%s\n' "DEEPSEEK_API_KEY=" > Key.txt
  echo "Created empty Key.txt — add DEEPSEEK_API_KEY"
fi

# data dirs
mkdir -p data/hot data/warm data/cold data/workspace/temp data/workspace/perm data/backups

echo ""
echo "OK — Gnom-Hub v1.0.0 ready."
echo "  source .venv/bin/activate"
echo "  ./scripts/start.sh"
echo "  → http://127.0.0.1:8080/"
echo "  ./scripts/quality_check.sh   # ruff + pytest + smoke"
