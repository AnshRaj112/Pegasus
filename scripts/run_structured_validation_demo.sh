#!/usr/bin/env bash
# Generate structured-compare fixtures and verify in-process.
# Usage:
#   ./scripts/run_structured_validation_demo.sh
#   ./scripts/run_structured_validation_demo.sh --no-verify   # generate only
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="${OUT_DIR:-$ROOT/test-data/structured-compare}"
ARGS=(--out-dir "$OUT")
if [[ "${1:-}" == "--no-verify" ]]; then
  shift
else
  ARGS+=(--verify)
fi

python3 scripts/generate_structured_validation_data.py "${ARGS[@]}" "$@"
