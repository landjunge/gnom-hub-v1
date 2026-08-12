#!/usr/bin/env bash
# Ping IndexNow after Pages deploy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
META="$ROOT/site/indexnow.json"

python3 - "$META" <<'PY'
import json, sys, urllib.request

meta = json.load(open(sys.argv[1]))
key = meta["key"]
key_loc = meta["keyLocation"]
host = "landjunge.github.io"
base = "https://landjunge.github.io/gnom-hub-v1"
urls = [
    f"{base}/",
    f"{base}/de.html",
    f"{base}/docs.html",
    f"{base}/ecosystem.html",
    f"{base}/blog/launch.html",
    f"{base}/press/",
    f"{base}/llms.txt",
    f"{base}/sitemap.xml",
]
body = {
    "host": host,
    "key": key,
    "keyLocation": key_loc,
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
    if hasattr(e, "read"):
        try:
            print(e.read()[:500])
        except Exception:
            pass
print("urls:", len(urls))
for u in urls:
    print(" ", u)
PY
