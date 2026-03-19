#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Force-load .env so direct backend start uses latest keys.
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

VENV_UVICORN="${VENV_UVICORN:-$ROOT_DIR/.venv/bin/uvicorn}"

if [ ! -x "$VENV_UVICORN" ]; then
  echo "[error] uvicorn introuvable: $VENV_UVICORN"
  echo "[hint] Creez/installez le venv:"
  echo "  cd $ROOT_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

cd "$ROOT_DIR"
exec "$VENV_UVICORN" src.main:app --host 0.0.0.0 --port 8000
