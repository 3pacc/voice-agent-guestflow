#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONT_DIR="$ROOT_DIR/frontend"

if ! command -v npm >/dev/null 2>&1; then
  echo "[error] npm introuvable dans PATH"
  echo "[hint] Installez Node.js + npm puis relancez. Exemple Ubuntu:"
  echo "  apt-get update && apt-get install -y nodejs npm"
  exit 1
fi

if [ ! -d "$FRONT_DIR" ]; then
  echo "[error] dossier frontend introuvable: $FRONT_DIR"
  exit 1
fi

FRONT_NODE_OPTIONS="${FRONT_NODE_OPTIONS:---max-old-space-size=1024}"

cd "$FRONT_DIR"
npm install
exec env NODE_OPTIONS="$FRONT_NODE_OPTIONS" NEXT_TELEMETRY_DISABLED=1 npm run dev -- --hostname 0.0.0.0 --port 3000
