#!/usr/bin/env bash
# One-command optional neural embeddings (fastembed). Super simple.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "No .venv yet. Run first:"
  echo "  ./scripts/install.sh"
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "=== Neural embeddings (optional) ==="
echo "Installing fastembed into .venv …"
pip install -q -r requirements-embeddings.txt

python - <<'PY'
from gnom_hub.memory.neural_embed import probe_neural
p = probe_neural()
print("fastembed:", "OK" if p.get("fastembed") else "MISSING")
if not p.get("fastembed"):
    raise SystemExit(1)
print("")
print("Done. Next (pick one):")
print("  1) Desk → Vector badge → embedder: fastembed → Apply + reindex")
print("  2) Or restart hub; then same click in Vector modal")
print("")
print("Default without this step stays: bow (no install needed).")
PY
