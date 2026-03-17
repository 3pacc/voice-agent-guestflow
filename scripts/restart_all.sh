#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[restart_all] stopping current services..."
bash scripts/stop_all.sh || true

echo "[restart_all] starting all services..."
exec bash scripts/start_all.sh
