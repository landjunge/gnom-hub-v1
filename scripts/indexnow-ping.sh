#!/usr/bin/env bash
# Ping IndexNow after Pages deploy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE="$ROOT/site"
META="$SITE/indexnow.json"
KEY=$(python3 -c "import json; print(json.load(open('$META'))['key'])")
KEY_LOC=$(python3 -c "import json; print(json.load(open('$META'))['keyLocation'])")
HOST="landjunge.github.io"
BASE="https://landjunge.github.io/gnom-hub-v1"

URLS=(
  "$BASE/"
  "$BASE/de.html"
  "$BASE/docs.html"
  "$BASE/ecosystem.html"
  "$BASE/blog/launch.html"
  "$BASE/press/"
  "$BASE/llms.txt"
  "$BASE/sitemap.xml"
)

python3 - <<PY
import json, urllib.request
urls = """$(printf '%s\n' "${URLS[@]}")""".strip().splitlines()
body = {
  "host": "$HOST",
  "key": "$KEY",
  "keyLocation": "$KEY_LOC",
  "urlList": urls,
}
data = json.dumps(body).encode()
req = urllib.request.Request(
  "https://api.indexnow.org/indexnow",
  data=data,
  headers={"Content-Type": "application/json; charset=utf-8"},
  method="POST",
)
try:
  with urllib.request.urlopen(req, timeout=30) as r:
    print("indexnow", r.status, r.read()[:200])
except Exception as e:
  print("indexnow response:", e)
  if hasattr(e, "code"):
    print("code", e.code)
  if hasattr(e, "read"):
    try:
      print(e.read()[:500])
    except Exception:
      pass
print("urls:", len(urls))
for u in urls:
  print(" ", u)
PY
