#!/usr/bin/env bash
# Point this clone at versioned hooks under .githooks/ (pre-push runs ruff).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .git ]; then
  echo "Not a git repository: $ROOT" >&2
  exit 1
fi

HOOKS_DIR="${ROOT}/.githooks"
if [ ! -d "$HOOKS_DIR" ]; then
  echo "Missing $HOOKS_DIR" >&2
  exit 1
fi

chmod +x "${HOOKS_DIR}"/* 2>/dev/null || true
git config core.hooksPath .githooks

echo "Installed git hooks path: core.hooksPath=.githooks"
echo "  pre-push → ruff check . && ruff format --check ."
echo ""
echo "Verify:  git config --get core.hooksPath"
echo "Skip:    git push --no-verify   (emergency only)"
