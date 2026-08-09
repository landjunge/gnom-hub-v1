#!/usr/bin/env bash
# Point this clone at versioned hooks under .githooks/
# (pre-commit + pre-push → scripts/prepush_gate.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .git ] && [ ! -f .git ]; then
  # .git can be a file in worktrees
  if [ ! -e .git ]; then
    echo "Not a git repository: $ROOT" >&2
    exit 1
  fi
fi

HOOKS_DIR="${ROOT}/.githooks"
if [ ! -d "$HOOKS_DIR" ]; then
  echo "Missing $HOOKS_DIR" >&2
  exit 1
fi

chmod +x "${HOOKS_DIR}"/* 2>/dev/null || true
chmod +x "${ROOT}/scripts/prepush_gate.sh" 2>/dev/null || true
chmod +x "${ROOT}/scripts/install_git_hooks.sh" 2>/dev/null || true

git config core.hooksPath .githooks

echo "Installed git hooks: core.hooksPath=.githooks"
echo "  pre-commit → scripts/prepush_gate.sh  (when .py staged)"
echo "  pre-push   → scripts/prepush_gate.sh  (always)"
echo ""
echo "Verify:  git config --get core.hooksPath"
echo "Dry-run: ./scripts/prepush_gate.sh"
echo "Auto-fix format: ./scripts/prepush_gate.sh --fix"
echo "Skip:    git push --no-verify   /  git commit --no-verify  (emergency only)"

# Self-test config
if [ "$(git config --get core.hooksPath)" != ".githooks" ]; then
  echo "WARNING: core.hooksPath not set to .githooks" >&2
  exit 1
fi
