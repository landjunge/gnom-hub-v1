#!/bin/sh
# One-shot fetch + install for Gnom-Hub-V1.
# Usage: curl -fsSL https://raw.githubusercontent.com/landjunge/gnom-hub-v1/main/scripts/get.sh | sh
set -eu

REPO="https://github.com/landjunge/gnom-hub-v1.git"
DEST="${GNOM_DIR:-$HOME/gnom-hub-v1}"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: '$1' is required." >&2
    exit 1
  fi
}

need git
if ! command -v python3 >/dev/null 2>&1 && ! command -v python3.12 >/dev/null 2>&1 && ! command -v python3.11 >/dev/null 2>&1 && ! command -v python3.10 >/dev/null 2>&1; then
  echo "ERROR: Python 3.10+ is required." >&2
  exit 1
fi

if [ -d "$DEST/.git" ]; then
  echo "Updating $DEST …"
  git -C "$DEST" pull --ff-only
elif [ -e "$DEST" ]; then
  echo "ERROR: $DEST exists and is not a git clone. Set GNOM_DIR to another path." >&2
  exit 1
else
  echo "Cloning into $DEST …"
  git clone --depth 1 "$REPO" "$DEST"
fi

cd "$DEST"
chmod +x scripts/install.sh scripts/start.sh
./scripts/install.sh

echo
echo "Gnom-Hub is installed at $DEST"
echo "  1. Put a real key in  User/Key.txt  (DEEPSEEK_API_KEY=sk-…)"
echo "  2. Start the desk:    cd $DEST && ./scripts/start.sh"
echo "  3. Open               http://127.0.0.1:8080/"
echo
echo "Send = dialogue. Execute = work. No Docker."
