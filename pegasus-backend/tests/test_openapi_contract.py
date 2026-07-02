# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T10:19:19Z
# --- END GENERATED FILE METADATA ---

"""Ensure the FastAPI app matches the committed OpenAPI contract."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_openapi_contract.py"


def test_backend_matches_openapi_contract() -> None:
    result = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--check-backend"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_openapi_contract_is_valid() -> None:
    result = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--validate"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
