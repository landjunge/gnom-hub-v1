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

# Check workspace + Key + DB before serving
python - <<'PY'
from gnom_hub.config.user_workspace import ensure_user_workspace, format_user_workspace_report

st = ensure_user_workspace()
print(format_user_workspace_report(st))
if not st.workspace_ok or not st.user_dir_ok:
    raise SystemExit("User workspace missing — run ./scripts/install.sh")
if not st.key_ok:
    raise SystemExit("User/Key.txt missing — run ./scripts/install.sh")
if not st.key_has_deepseek:
    print("  note: no DeepSeek key yet — LLM calls will stub until you edit User/Key.txt")
PY

echo "Gnom-Hub v1 → http://${HOST}:${PORT}/"
echo "  User/ = Key.txt + user.db · Send = brainstorm · Execute = workers"
exec python -m gnom_hub.main --host "$HOST" --port "$PORT"
