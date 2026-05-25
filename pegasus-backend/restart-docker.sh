#!/usr/bin/env bash
# Restart Pegasus backend in Docker with the correct local-path settings.
set -euo pipefail
cd "$(dirname "$0")"
cp -f .env.backend .env
docker compose down 2>/dev/null || true
docker compose up --build -d
echo ""
echo "Backend: http://127.0.0.1:8000"
echo "File picker default: /home/ansh.raj/Pegasus/test-data"
echo "Example CSVs:"
echo "  /home/ansh.raj/Pegasus/test-data/validation_source.csv"
echo "  /home/ansh.raj/Pegasus/test-data/validation_target.csv"
