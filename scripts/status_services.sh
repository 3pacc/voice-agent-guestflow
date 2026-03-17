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

echo "[status] process list:"
ps -ef | awk '/uvicorn src.main:app|vllm.entrypoints.openai.api_server|VLLM::EngineCore/ && !/awk/ {print}' || true

echo
echo "[status] endpoint checks:"
"$VENV_PY" - <<'PY2'
import httpx

checks = [
    ("API /health", "http://localhost:8000/health", {}),
    ("vLLM /v1/models", "http://localhost:8002/v1/models", {"Authorization": "Bearer EMPTY"}),
]

for name, url, headers in checks:
    try:
        r = httpx.get(url, headers=headers, timeout=5.0)
        print(f"- {name}: {r.status_code}")
    except Exception as e:
        print(f"- {name}: DOWN ({e})")
PY2
