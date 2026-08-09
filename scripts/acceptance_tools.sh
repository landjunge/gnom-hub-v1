#!/usr/bin/env bash
# Quick desk acceptance for Gnom-Hub tool/browser paths (needs hub :8080).
set -euo pipefail
BASE="${GNOM_E2E_BASE:-http://127.0.0.1:8080}"
fail=0

check() {
  local label="$1" text="$2" expect="$3"
  echo "▸ $label"
  local out
  out=$(curl -s -m 120 -X POST "$BASE/api/chat?sync=1" \
    -H 'Content-Type: application/json' \
    -d "$(python3 -c "import json,sys; print(json.dumps({'text':sys.argv[1]}))" "$text")" || true)
  if ! echo "$out" | python3 -c "
import sys,json
d=json.loads(sys.stdin.read() or '{}')
p=d.get('pipeline') or {}
body=' '.join([
  str(p.get('quality_notes') or ''),
  str((p.get('worker_results') or [''])[0] or ''),
  str(p.get('stage') or ''),
])
ok = p.get('stage')=='done' and ('$expect'.lower() in body.lower() or len(p.get('tool_log') or [])>0)
print('  stage=', p.get('stage'), 'tools=', len(p.get('tool_log') or []))
sys.exit(0 if ok else 1)
"; then
    echo "  FAIL ($expect)"
    fail=$((fail+1))
  else
    echo "  OK"
  fi
}

curl -sf -m 3 "$BASE/api/health" >/dev/null || { echo "Hub not up at $BASE"; exit 2; }

check "browser nav" "navigiere zu https://www.kleinanzeigen.de" "browser"
check "bare site" "kleinanzeigen" "browser"
check "go-only" "mach jetzt das was ich gesagt habe" "browser"
check "S6 plugins" "Tool drill S6 plugins" "file_list"
check "S7 killer" "Tool drill S7 killer" "pw_goto"

# busy must 409
curl -s -m 5 -X POST "$BASE/api/chat" -H 'Content-Type: application/json' \
  -d '{"text":"Landingpage Gnom-Hub v1 mit Effects jetzt bauen"}' >/tmp/gnom_acc_job.json || true
code=$(curl -s -o /tmp/gnom_acc_busy.json -w '%{http_code}' -m 5 -X POST "$BASE/api/chat" \
  -H 'Content-Type: application/json' -d '{"text":"x"}' || echo 000)
echo "▸ busy 409 → $code"
if [ "$code" != "409" ]; then echo "  FAIL"; fail=$((fail+1)); else echo "  OK"; fi
curl -s -m 5 -X POST "$BASE/api/jobs/cancel-busy" >/dev/null || true

echo "── result: $fail failures ──"
exit "$fail"
