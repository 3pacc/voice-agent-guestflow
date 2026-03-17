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

echo "[stop] stopping FastAPI and vLLM..."
pkill -f "uvicorn src.main:app" >/dev/null 2>&1 || true
pkill -f "vllm.entrypoints.openai.api_server|vllm serve" >/dev/null 2>&1 || true
sleep 1

echo "[stop] remaining processes:"
ps -ef | awk '/uvicorn src.main:app|vllm.entrypoints.openai.api_server|VLLM::EngineCore/ && !/awk/ {print}' || true
