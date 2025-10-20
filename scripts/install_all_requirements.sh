#!/usr/bin/env bash
set -euo pipefail
VENV=${1:-.venv}

if [ ! -d "$VENV" ]; then
  python -m venv "$VENV"
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r requirements-all.txt

echo "Installed runtime requirements. For dev/test packages run: pip install -r requirements-all-dev.txt"
