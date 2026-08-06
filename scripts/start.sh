#!/usr/bin/env bash
# Start Gnom-Hub v1 (desktop UI, default :8080)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Prefer project User/Key.txt + User/user.db
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
HOST="${GNOM_HUB_HOST:-127.0.0.1}"
PORT="${GNOM_HUB_PORT:-8080}"

# Personal WS (sibling) + Key + DB; selected/ only for chosen HTML
python - <<'PY'
from gnom_hub.config.user_workspace import ensure_user_workspace, format_user_workspace_report

st = ensure_user_workspace()
print(format_user_workspace_report(st))
if not st.user_dir_ok:
    raise SystemExit("personal WS User/ missing — run ./scripts/install.sh")
if not st.key_ok:
    raise SystemExit("User/Key.txt missing — run ./scripts/install.sh")
if not st.key_has_deepseek:
    print("  note: no DeepSeek key yet — edit personal WS User/Key.txt")
PY

echo "Gnom-Hub v1 → http://${HOST}:${PORT}/"
echo "  work=hub · Key/DB/selected HTML=WS-gnom-hub-v1"
exec python -m gnom_hub.main --host "$HOST" --port "$PORT"
