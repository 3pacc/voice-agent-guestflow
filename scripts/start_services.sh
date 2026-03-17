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

VLLM_MODEL="${VLLM_MODEL:-meta-llama/Llama-3.1-8B-Instruct}"
VLLM_PORT="${VLLM_PORT:-8002}"
API_PORT="${API_PORT:-8000}"
VLLM_API_KEY="${LLM_API_KEY:-EMPTY}"

VLLM_LOG="${VLLM_LOG:-vllm.log}"
API_LOG="${API_LOG:-uvicorn.log}"

echo "[start] ROOT_DIR=$ROOT_DIR"
echo "[start] model=$VLLM_MODEL, vllm_port=$VLLM_PORT, api_port=$API_PORT"

echo "[start] stopping previous processes (if any)..."
pkill -f "vllm.entrypoints.openai.api_server|vllm serve" >/dev/null 2>&1 || true
pkill -f "uvicorn src.main:app" >/dev/null 2>&1 || true
sleep 1

echo "[start] starting vLLM..."
nohup "$VENV_PY" -m vllm.entrypoints.openai.api_server \
  --model "$VLLM_MODEL" \
  --served-model-name "$VLLM_MODEL" \
  --host 0.0.0.0 \
  --port "$VLLM_PORT" \
  --dtype auto \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.85 \
  --enforce-eager \
  --attention-backend FLASHINFER \
  --api-key "$VLLM_API_KEY" \
  > "$VLLM_LOG" 2>&1 &

VLLM_PID=$!
echo "[start] vLLM PID=$VLLM_PID"

echo "[start] waiting for vLLM /v1/models..."
"$VENV_PY" - <<'PY2'
import time
import httpx
import sys

url = "http://localhost:8002/v1/models"
headers = {"Authorization": "Bearer EMPTY"}

for i in range(420):
    try:
        r = httpx.get(url, headers=headers, timeout=5.0)
        if r.status_code == 200:
            print("[start] vLLM is ready.")
            sys.exit(0)
    except Exception:
        pass
    time.sleep(1)

print("[start] ERROR: vLLM did not become ready in time.")
sys.exit(1)
PY2

echo "[start] starting FastAPI..."
nohup "$VENV_UVICORN" src.main:app --host 0.0.0.0 --port "$API_PORT" > "$API_LOG" 2>&1 &
API_PID=$!
echo "[start] API PID=$API_PID"

echo "[start] waiting for /health..."
"$VENV_PY" - <<'PY3'
import time
import httpx
import sys

url = "http://localhost:8000/health"
for i in range(60):
    try:
        r = httpx.get(url, timeout=5.0)
        if r.status_code == 200:
            print("[start] API is healthy:", r.text)
            sys.exit(0)
    except Exception:
        pass
    time.sleep(1)

print("[start] ERROR: API did not become healthy in time.")
sys.exit(1)
PY3

echo "[start] done."
echo "[start] tail logs with: tail -f $VLLM_LOG $API_LOG"
