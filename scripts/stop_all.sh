#!/usr/bin/env bash
set -euo pipefail

API_PORT="${API_PORT:-8000}"
FRONT_PORT="${FRONT_PORT:-3000}"

echo "[stop_all] stop backend/frontend..."
pkill -f "uvicorn src.main:app" >/dev/null 2>&1 || true
pkill -f "next dev --hostname 0.0.0.0 --port $FRONT_PORT" >/dev/null 2>&1 || true
pkill -f "npm --prefix .*frontend.* run dev -- --hostname 0.0.0.0 --port $FRONT_PORT" >/dev/null 2>&1 || true
pkill -f "npm run dev -- --hostname 0.0.0.0 --port $FRONT_PORT" >/dev/null 2>&1 || true
sleep 1

echo "[stop_all] verification process:" 
ps -ww -ef | awk '/uvicorn src.main:app|next dev --hostname 0.0.0.0 --port|npm --prefix .*frontend.* run dev/ && !/awk/ {print}' || true

echo "[stop_all] done"
