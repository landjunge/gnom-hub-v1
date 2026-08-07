#!/usr/bin/env bash
# Install git hooks for this repository.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS_DIR="$ROOT/.git/hooks"

cat > "$HOOKS_DIR/pre-push" << 'HOOK'
#!/usr/bin/env bash
# Pre-push hook: run ruff check + format --check before every push.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
if [ -d .venv ]; then source .venv/bin/activate; fi
echo "▸ ruff check"
ruff check .
echo "▸ ruff format --check"
ruff format --check .
echo "✓ ruff OK"
HOOK

chmod +x "$HOOKS_DIR/pre-push"
echo "✓ pre-push hook installed at $HOOKS_DIR/pre-push"
