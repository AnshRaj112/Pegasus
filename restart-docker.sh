#!/usr/bin/env bash
# Restart Pegasus backend + frontend in Docker from the repo root.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f pegasus-backend/.env.backend ]]; then
  echo "Missing pegasus-backend/.env.backend — copy from .env.example and configure the database." >&2
  exit 1
fi

docker compose down --remove-orphans 2>/dev/null || true
# Remove legacy containers from the old pegasus-backend-only compose (fixed container_name).
docker rm -f pegasus-backend pegasus-frontend 2>/dev/null || true
docker compose up --build -d

echo ""
ui_port="${PEGASUS_UI_PORT:-8080}"
echo "Frontend (UI + API proxy): http://127.0.0.1:${ui_port}"
echo "Backend (direct API):      http://127.0.0.1:8000"
echo "File picker default:       see PEGASUS_VALIDATION_LOCAL_PATH_DEFAULT_BROWSE in pegasus-backend/.env.backend"
echo "Example CSVs:"
echo "  $HOME/Pegasus/test-data/validation_source.csv"
echo "  $HOME/Pegasus/test-data/validation_target.csv"
