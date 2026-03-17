#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_PY="${VENV_PY:-$ROOT_DIR/.venv/bin/python}"
VENV_UVICORN="${VENV_UVICORN:-$ROOT_DIR/.venv/bin/uvicorn}"
export PATH="$ROOT_DIR/.venv/bin:$PATH"

if [ ! -x "$VENV_PY" ]; then
  echo "[error] Missing venv python: $VENV_PY"
  exit 1
fi

echo "[restart] stopping services..."
"$ROOT_DIR/scripts/stop_services.sh"

echo "[restart] starting services..."
"$ROOT_DIR/scripts/start_services.sh"

echo "[restart] done."
