#!/usr/bin/env bash
# Mark this repo (and optional extras) as a Git safe.directory.
#
# Fixes:  fatal: detected dubious ownership in repository at '…'
# Cause:  repo owner ≠ current user (containers, mounted volumes, multi-user USB).
#
# Usage:
#   ./scripts/ensure_git_safe_directory.sh           # this clone only (global add)
#   ./scripts/ensure_git_safe_directory.sh --local    # repo-local config only
#   GNOM_SAFE_DIRECTORY_STAR=1 ./scripts/ensure_git_safe_directory.sh  # add '*' (dev VMs only)
#
# Safe: idempotent; never removes other safe.directory entries.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Resolve real path when possible (symlinks / USB mounts)
if command -v realpath >/dev/null 2>&1; then
  ROOT="$(realpath "$ROOT")"
fi

SCOPE="--global"
for arg in "$@"; do
  case "$arg" in
    --local) SCOPE="--local" ;;
    --global) SCOPE="--global" ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
  esac
done

if [ "$SCOPE" = "--local" ]; then
  cd "$ROOT"
  if [ ! -e .git ]; then
    echo "ensure_git_safe_directory: not a git repo: $ROOT" >&2
    exit 1
  fi
fi

already() {
  # list may be multi-line; exact path match
  git config $SCOPE --get-all safe.directory 2>/dev/null | grep -Fx "$1" >/dev/null 2>&1
}

add_safe() {
  local path="$1"
  if already "$path"; then
    echo "safe.directory already set ($SCOPE): $path"
    return 0
  fi
  git config $SCOPE --add safe.directory "$path"
  echo "safe.directory added ($SCOPE): $path"
}

add_safe "$ROOT"

# Worktrees / bare-adjacent: also mark if GIT_DIR points elsewhere
if [ -n "${GIT_WORK_TREE:-}" ]; then
  wt="$GIT_WORK_TREE"
  if command -v realpath >/dev/null 2>&1; then
    wt="$(realpath "$wt")"
  fi
  add_safe "$wt"
fi

# Optional: trust all directories (only when explicitly requested — agents/CI sandboxes)
if [ "${GNOM_SAFE_DIRECTORY_STAR:-}" = "1" ] || [ "${GNOM_SAFE_DIRECTORY_STAR:-}" = "true" ]; then
  if already "*"; then
    echo "safe.directory already set ($SCOPE): *"
  else
    git config $SCOPE --add safe.directory "*"
    echo "safe.directory added ($SCOPE): *   (GNOM_SAFE_DIRECTORY_STAR=1)"
  fi
fi

# Verify git can read this repo
cd "$ROOT"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "✅ git accepts ownership for: $ROOT"
else
  echo "❌ still dubious — try: git config --global --add safe.directory '*'" >&2
  exit 1
fi
