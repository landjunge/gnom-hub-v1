#!/usr/bin/env bash
# Quick desk acceptance for Gnom-Hub tool/browser/DoD paths (needs hub up).
# Base: GNOM_E2E_BASE (default http://127.0.0.1:8080)
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
  ' '.join(str(x.get('name') or '') for x in (p.get('tool_log') or [])),
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

# ── UI hosts (Slice D) ──────────────────────────────────────────────
echo "▸ UI DoD hosts"
html=$(curl -s -m 10 "$BASE/" || true)
if echo "$html" | grep -q 'box3-dod-checklist' \
  && echo "$html" | grep -q 'tools-dod-fail' \
  && echo "$html" | grep -q 'box3-tool-strip'; then
  echo "  OK"
else
  echo "  FAIL (missing box3-dod-checklist / tools-dod-fail / box3-tool-strip)"
  fail=$((fail+1))
fi

check "browser nav" "navigiere zu https://www.kleinanzeigen.de" "browser"
check "bare site" "kleinanzeigen" "browser"
check "go-only" "mach jetzt das was ich gesagt habe" "browser"
check "S6 plugins" "Tool drill S6 plugins" "file_list"
check "S7 killer" "Tool drill S7 killer" "pw_goto"

# ── DoD validation + one-worker HTML (no LLM key → FEHLER is OK) ────
echo "▸ DoD validation + one-worker HTML"
# clean slate so prior tool drills do not pollute worker list
curl -s -m 15 -X POST "$BASE/api/reset" -H 'Content-Type: application/json' -d '{}' >/dev/null || true
curl -s -m 120 -X POST "$BASE/api/chat?sync=1" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Baue eine komplette Landingpage HTML mit dark theme und Hero"}' >/tmp/gnom_acc_html.json || true
# execute if needed
stage=$(python3 -c "import json; d=json.load(open('/tmp/gnom_acc_html.json')); print((d.get('pipeline') or {}).get('stage') or '')" 2>/dev/null || true)
if [ "$stage" != "done" ]; then
  curl -s -m 180 -X POST "$BASE/api/execute?sync=1" \
    -H 'Content-Type: application/json' -d '{}' >/tmp/gnom_acc_html_exec.json || true
fi
curl -s -m 15 "$BASE/api/state" >/tmp/gnom_acc_state.json || true
if python3 - <<'PY'
import json, sys
st = json.load(open("/tmp/gnom_acc_state.json"))
p = st.get("pipeline") or {}
outs = p.get("worker_outputs") or []
val = p.get("validation")
mode = (p.get("resolved_plan_mode") or "")
print("  stage=", p.get("stage"), "workers=", len(outs), "plan=", mode)
print("  validation.ok=", None if not val else val.get("ok"),
      "issues=", None if not val else (val.get("issues") or [])[:5],
      "checklist=", None if not val else len(val.get("checklist") or []))
ok = True
if p.get("stage") != "done":
    print("  FAIL stage not done")
    ok = False
# HTML page intent → one worker
if mode == "full_page_html" and len(outs) != 1:
    print("  FAIL expected 1 worker for full_page_html, got", len(outs))
    ok = False
if not val or not isinstance(val, dict):
    print("  FAIL missing pipeline.validation")
    ok = False
else:
    cl = val.get("checklist") or []
    if not cl:
        print("  FAIL validation.checklist empty")
        ok = False
    # Without key: worker_error is expected and must be visible
    issues = val.get("issues") or []
    if val.get("ok") is not False and "worker_error" not in issues:
        # allow true ok if a real key produced HTML
        if val.get("ok") is True and any(
            (o.get("result") or "").lower().find("</html>") >= 0 for o in outs
        ):
            pass
        else:
            print("  FAIL expected DoD fail (no key) or complete HTML")
            ok = False
sys.exit(0 if ok else 1)
PY
then
  echo "  OK"
else
  echo "  FAIL"
  fail=$((fail+1))
fi

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
