#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Force-load .env so restarted services always use latest keys.
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
fi

VENV_PY="${VENV_PY:-$ROOT_DIR/.venv/bin/python}"
VENV_UVICORN="${VENV_UVICORN:-$ROOT_DIR/.venv/bin/uvicorn}"
API_PORT="${API_PORT:-8000}"
FRONT_PORT="${FRONT_PORT:-3000}"
API_LOG="${API_LOG:-uvicorn.log}"
FRONT_LOG="${FRONT_LOG:-frontend_dev.log}"
MAX_TRIES="${START_ALL_MAX_TRIES:-60}"
SLEEP_S="${START_ALL_SLEEP_S:-1}"
FRONT_NODE_OPTIONS="${FRONT_NODE_OPTIONS:---max-old-space-size=1024}"

if [ ! -x "$VENV_PY" ] || [ ! -x "$VENV_UVICORN" ]; then
  echo "[error] venv incomplet (.venv/bin/python ou .venv/bin/uvicorn introuvable)"
  echo "[hint] cd $ROOT_DIR && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[error] npm introuvable dans PATH"
  echo "[hint] apt-get update && apt-get install -y nodejs npm"
  exit 1
fi

if [ ! -d "$ROOT_DIR/frontend" ]; then
  echo "[error] dossier frontend introuvable: $ROOT_DIR/frontend"
  exit 1
fi

echo "[start_all] stop anciens process backend/frontend..."
pkill -f "uvicorn src.main:app" >/dev/null 2>&1 || true
pkill -f "next dev --hostname 0.0.0.0 --port $FRONT_PORT" >/dev/null 2>&1 || true
pkill -f "npm --prefix .*frontend.* run dev -- --hostname 0.0.0.0 --port $FRONT_PORT" >/dev/null 2>&1 || true
pkill -f "npm run dev -- --hostname 0.0.0.0 --port $FRONT_PORT" >/dev/null 2>&1 || true
sleep 1

echo "[start_all] start backend sur :$API_PORT ..."
nohup "$VENV_UVICORN" src.main:app --host 0.0.0.0 --port "$API_PORT" > "$API_LOG" 2>&1 &

# Nettoyage cache dev Next pour eviter les erreurs webpack stale.
rm -rf "$ROOT_DIR/frontend/.next" || true

echo "[start_all] start frontend sur :$FRONT_PORT ..."
nohup env NODE_OPTIONS="$FRONT_NODE_OPTIONS" NEXT_TELEMETRY_DISABLED=1 npm --prefix "$ROOT_DIR/frontend" run dev -- --hostname 0.0.0.0 --port "$FRONT_PORT" > "$FRONT_LOG" 2>&1 &

echo "[start_all] process actifs:"
ps -ww -ef | awk '/uvicorn src.main:app|next dev --hostname 0.0.0.0 --port|npm --prefix .*frontend.* run dev/ && !/awk/ {print}' || true

check_http() {
  local url="$1"
  "$VENV_PY" - "$url" <<'PY2'
import sys
import httpx
url = sys.argv[1]
try:
    r = httpx.get(url, timeout=3.0)
    if 200 <= r.status_code < 500:
        print(r.status_code)
        raise SystemExit(0)
    raise SystemExit(1)
except Exception:
    raise SystemExit(1)
PY2
}

echo "[start_all] attente readiness (max=${MAX_TRIES}, sleep=${SLEEP_S}s)..."
api_ok=0
front_ok=0
for i in $(seq 1 "$MAX_TRIES"); do
  if [ "$api_ok" -eq 0 ] && check_http "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    api_ok=1
    echo "[start_all] API ready (try $i/$MAX_TRIES)"
  fi
  if [ "$front_ok" -eq 0 ] && check_http "http://127.0.0.1:${FRONT_PORT}/login" >/dev/null 2>&1; then
    front_ok=1
    echo "[start_all] Frontend ready (try $i/$MAX_TRIES)"
  fi

  if [ "$api_ok" -eq 1 ] && [ "$front_ok" -eq 1 ]; then
    break
  fi
  sleep "$SLEEP_S"
done

echo
printf '[start_all] checks: '
if [ "$api_ok" -eq 1 ]; then
  printf 'API=UP '
else
  printf 'API=DOWN '
fi
if [ "$front_ok" -eq 1 ]; then
  printf 'Frontend=UP\n'
else
  printf 'Frontend=DOWN\n'
fi

if [ "$api_ok" -ne 1 ] || [ "$front_ok" -ne 1 ]; then
  echo "[start_all] warning: un service n'a pas demarre a temps. Extrait logs:"
  echo "--- $API_LOG (last 20) ---"
  "$VENV_PY" - <<'PY3'
from pathlib import Path
p=Path('uvicorn.log')
if p.exists():
    for l in p.read_text(encoding='utf-8',errors='replace').splitlines()[-20:]:
        print(l)
else:
    print('(missing)')
PY3
  echo "--- $FRONT_LOG (last 20) ---"
  "$VENV_PY" - <<'PY4'
from pathlib import Path
p=Path('frontend_dev.log')
if p.exists():
    for l in p.read_text(encoding='utf-8',errors='replace').splitlines()[-20:]:
        print(l)
else:
    print('(missing)')
PY4
fi

echo "[start_all] logs: $API_LOG | $FRONT_LOG"
echo "[start_all] termine"
