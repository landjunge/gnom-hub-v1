#!/usr/bin/env bash
# Smoke-test scripts/github_pr_webhook.py over HTTP.
# Fake HMAC → 401. Matching HMAC → 200.
#
#   ./scripts/webhook_smoke.sh
#   ./scripts/webhook_smoke.sh http://127.0.0.1:8088
#
# With no URL, starts an ephemeral listener (needs GNOM_WEBHOOK_SECRET only
# for a running server; the ephemeral path sets its own smoke secret).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${GNOM_WEBHOOK_SMOKE_PORT:-18088}"
SECRET="${GNOM_WEBHOOK_SECRET:-smoke-webhook-secret}"
BASE="${1:-}"
STARTED=0
PID=""
STATE_DIR=""
OUT_BAD=""
OUT_OK=""

cleanup() {
  if [[ "$STARTED" -eq 1 && -n "${PID}" ]]; then
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -f "$OUT_BAD" "$OUT_OK"
  if [[ -n "$STATE_DIR" && -d "$STATE_DIR" ]]; then
    rm -rf "$STATE_DIR"
  fi
}
trap cleanup EXIT

if [[ -z "$BASE" ]]; then
  STATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/gnom-webhook-smoke.XXXXXX")"
  export GNOM_WEBHOOK_SECRET="$SECRET"
  unset GNOM_BUILDER_CMD || true
  python3 "$ROOT/scripts/github_pr_webhook.py" \
    --host 127.0.0.1 \
    --port "$PORT" \
    --state "$STATE_DIR/state.json" \
    --prompt "$STATE_DIR/builder.md" \
    >"$STATE_DIR/server.out" 2>"$STATE_DIR/server.err" &
  PID=$!
  STARTED=1
  BASE="http://127.0.0.1:${PORT}"
  ok=0
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if curl -fsS "$BASE/health" >/dev/null 2>&1; then
      ok=1
      break
    fi
    if ! kill -0 "$PID" 2>/dev/null; then
      echo "FAIL: webhook process exited before listen" >&2
      cat "$STATE_DIR/server.err" >&2 || true
      exit 1
    fi
    sleep 0.2
  done
  if [[ "$ok" -ne 1 ]]; then
    echo "FAIL: $BASE/health did not come up" >&2
    cat "$STATE_DIR/server.err" >&2 || true
    exit 1
  fi
fi

WEBHOOK="${BASE%/}/webhook"
BODY='{"action":"opened","number":1,"pull_request":{"number":1}}'
OUT_BAD="$(mktemp "${TMPDIR:-/tmp}/gnom-wh-bad.XXXXXX")"
OUT_OK="$(mktemp "${TMPDIR:-/tmp}/gnom-wh-ok.XXXXXX")"

echo "POST $WEBHOOK  (fake signature, expect 401)"
code_bad="$(
  curl -sS -o "$OUT_BAD" -w '%{http_code}' \
    -X POST "$WEBHOOK" \
    -H 'Content-Type: application/json' \
    -H 'X-GitHub-Event: pull_request' \
    -H 'X-Hub-Signature-256: sha256=deadbeef' \
    --data-binary "$BODY"
)"
echo "  HTTP $code_bad  $(cat "$OUT_BAD")"
if [[ "$code_bad" != "401" ]]; then
  echo "FAIL: expected 401 for fake signature, got $code_bad" >&2
  exit 1
fi

SIG="$(
  printf '%s' "$BODY" | SECRET="$SECRET" python3 -c '
import hashlib, hmac, os, sys
secret = os.environ["SECRET"].encode("utf-8")
body = sys.stdin.buffer.read()
print("sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest())
'
)"

echo "POST $WEBHOOK  (valid signature, expect 200)"
code_ok="$(
  curl -sS -o "$OUT_OK" -w '%{http_code}' \
    -X POST "$WEBHOOK" \
    -H 'Content-Type: application/json' \
    -H 'X-GitHub-Event: pull_request' \
    -H "X-Hub-Signature-256: $SIG" \
    --data-binary "$BODY"
)"
echo "  HTTP $code_ok  $(cat "$OUT_OK")"
if [[ "$code_ok" != "200" ]]; then
  echo "FAIL: expected 200 for valid signature, got $code_ok" >&2
  echo "If you pointed at a running server, GNOM_WEBHOOK_SECRET must match." >&2
  exit 1
fi

echo "ok  fake signature → 401, valid signature → 200"
