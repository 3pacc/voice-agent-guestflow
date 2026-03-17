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

VLLM_LOG="${VLLM_LOG:-vllm.log}"
API_LOG="${API_LOG:-uvicorn.log}"

echo "[logs] following $VLLM_LOG and $API_LOG"
if [ ! -f "$VLLM_LOG" ]; then
  echo "[logs] warning: $VLLM_LOG does not exist yet"
fi
if [ ! -f "$API_LOG" ]; then
  echo "[logs] warning: $API_LOG does not exist yet"
fi

tail -n 80 -f "$VLLM_LOG" "$API_LOG"
