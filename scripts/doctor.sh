#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_PORT="${API_PORT:-8000}"
FRONT_PORT="${FRONT_PORT:-3000}"
VLLM_PORT="${VLLM_PORT:-8002}"
VENV_PY="${VENV_PY:-$ROOT_DIR/.venv/bin/python}"

section() {
  echo
  echo "========== $1 =========="
}

ok() { echo "[OK] $1"; }
warn() { echo "[WARN] $1"; }
err() { echo "[ERR] $1"; }

section "Contexte"
echo "ROOT_DIR=$ROOT_DIR"
date

section "Prerequis"
if [ -x "$VENV_PY" ]; then
  ok "venv python present: $VENV_PY"
else
  err "venv python missing: $VENV_PY"
  echo "      hint: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
fi

if command -v npm >/dev/null 2>&1; then
  ok "npm present: $(command -v npm)"
else
  err "npm missing in PATH"
  echo "      hint: apt-get update && apt-get install -y nodejs npm"
fi

if command -v node >/dev/null 2>&1; then
  ok "node present: $(command -v node)"
else
  warn "node missing in PATH"
fi

section "Fichiers"
for f in .env scripts/start_all.sh scripts/stop_all.sh scripts/restart_all.sh scripts/start_backend.sh scripts/start_frontend.sh; do
  if [ -e "$f" ]; then
    ok "$f present"
  else
    err "$f missing"
  fi
done

section "Process"
ps -ww -ef | awk '/uvicorn src.main:app|next dev --hostname 0.0.0.0 --port|vllm.entrypoints.openai.api_server|VLLM::EngineCore|ngrok start --all/ && !/awk/ {print}' || true

section "Health checks"
if [ -x "$VENV_PY" ]; then
  "$VENV_PY" - <<'PY2'
import httpx

checks = [
    ("API /health", "http://127.0.0.1:8000/health", {}),
    ("Admin /admin/live/health", "http://127.0.0.1:8000/admin/live/health", {}),
    ("Inventory rooms", "http://127.0.0.1:8000/admin/live/inventory/rooms", {}),
    ("Frontend /dashboard", "http://127.0.0.1:3000/dashboard", {}),
    ("Frontend /settings", "http://127.0.0.1:3000/settings", {}),
    ("Frontend /inventory", "http://127.0.0.1:3000/inventory", {}),
    ("vLLM /v1/models", "http://127.0.0.1:8002/v1/models", {"Authorization": "Bearer EMPTY"}),
]

for name, url, headers in checks:
    try:
        r = httpx.get(url, headers=headers, timeout=5.0)
        print(f"[HTTP {r.status_code}] {name} -> {url}")
    except Exception as e:
        print(f"[DOWN] {name} -> {url} ({e})")
PY2
else
  warn "health checks skipped: venv python missing"
fi

section "Ports"
for p in "$API_PORT" "$FRONT_PORT" "$VLLM_PORT"; do
  if ss -ltn | awk '{print $4}' | grep -E ":${p}$" >/dev/null 2>&1; then
    ok "port $p listening"
  else
    warn "port $p not listening"
  fi
done

section "Resume"
echo "- Si npm/node manquent: installez-les puis relancez start_all.sh"
echo "- Si API/Frontend DOWN: bash scripts/restart_all.sh"
echo "- Si erreur webpack: rm -rf frontend/.next puis restart_all.sh"
echo "- Si routes admin 404: redemarrer backend"
