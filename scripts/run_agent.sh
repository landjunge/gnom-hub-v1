#!/usr/bin/env bash
# Launch one Grok headless session for an agent role.
# Prompt file = agents/<role>.md plus optional stdin (poll/webhook extra).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROLE="${1:-${GNOM_AGENT_ROLE:-builder}}"
WORKDIR="${GNOM_AGENT_WORKDIR:-$ROOT}"
GROK_BIN="${GNOM_GROK_BIN:-grok}"
MAX_TURNS="${GNOM_AGENT_MAX_TURNS:-80}"

case "$ROLE" in
  builder|reviewer|planer|koordinator|test-agent) ;;
  *)
    echo "run_agent: unknown role '$ROLE'" >&2
    exit 2
    ;;
esac

if [[ "$ROLE" == "test-agent" ]]; then
  PROMPT_SRC="$ROOT/agents/test-agent.md"
else
  PROMPT_SRC="$ROOT/agents/${ROLE}.md"
fi

if [[ ! -f "$PROMPT_SRC" ]]; then
  echo "run_agent: missing prompt $PROMPT_SRC" >&2
  exit 2
fi

if ! command -v "$GROK_BIN" >/dev/null 2>&1; then
  echo "run_agent: grok not found ($GROK_BIN). Set GNOM_GROK_BIN." >&2
  exit 2
fi

tmp="$(mktemp "${TMPDIR:-/tmp}/gnom-agent-prompt.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

{
  cat "$PROMPT_SRC"
  echo
  echo "---"
  echo "Repo: ${GNOM_GITHUB_REPO:-landjunge/gnom-hub-v1}"
  echo "Baseline-Branch: ${GNOM_JOB_BASE:-baseline}"
  echo "Arbeitsverzeichnis: $WORKDIR"
  echo "Rolle: $ROLE"
  [[ -n "${ISSUE_NUMBER:-}" ]] && echo "ISSUE_NUMBER=$ISSUE_NUMBER"
  [[ -n "${PR_NUMBER:-}" ]] && echo "PR_NUMBER=$PR_NUMBER"
  [[ -n "${GNOM_JOB_SHA:-}" ]] && echo "SHA=$GNOM_JOB_SHA"
  [[ -n "${GNOM_JOB_REASON:-}" ]] && echo "Grund: $GNOM_JOB_REASON"
  if [[ ! -t 0 ]]; then
    extra="$(cat)"
    if [[ -n "$extra" ]]; then
      echo
      echo "$extra"
    fi
  fi
} >"$tmp"

exec "$GROK_BIN" --prompt-file "$tmp" --cwd "$WORKDIR" --yolo --max-turns "$MAX_TURNS"
