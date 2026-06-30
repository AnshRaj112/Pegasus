#!/usr/bin/env python3
"""Export, validate, and check the Pegasus OpenAPI contract.

The canonical contract lives at ``api/openapi.yaml``. Backend routes and Pydantic
models must match it; frontend HTTP clients must only call paths declared in it.

Usage:
  python scripts/sync_openapi_contract.py --check     # fail if backend drifted
  python scripts/sync_openapi_contract.py --write     # refresh api/openapi.yaml
  python scripts/sync_openapi_contract.py --validate  # validate spec only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from openapi_spec_validator import validate
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = REPO_ROOT / "pegasus-backend" / "src"
CONTRACT_PATH = REPO_ROOT / "api" / "openapi.yaml"
FRONTEND_ROOT = REPO_ROOT / "pegasus-frontend"
FRONTEND_CLIENT_FILES = (
    FRONTEND_ROOT / "src" / "shared" / "api" / "Api.ts",
    FRONTEND_ROOT / "src" / "shared" / "api" / "adminAuth.ts",
)

# Placeholder pages that call routes not yet implemented on the backend.
FRONTEND_CLIENT_EXCLUDE = (
    FRONTEND_ROOT / "src" / "pages" / "test" / "Test.service.ts",
    FRONTEND_ROOT / "src" / "pages" / "admin" / "sections" / "setting" / "Setting.service.ts",
)

API_V1_PREFIX = "/api/v1"


def _sort_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _sort_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        if value and all(isinstance(item, str) for item in value):
            return sorted(value)
        return [_sort_value(item) for item in value]
    return value


def normalize_openapi(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical dict suitable for stable comparison."""
    cleaned = dict(spec)
    cleaned.pop("servers", None)
    return _sort_value(cleaned)  # type: ignore[return-value]


def load_contract() -> dict[str, Any]:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise SystemExit(f"Contract at {CONTRACT_PATH} is not a mapping.")
    return loaded


def export_backend_openapi() -> dict[str, Any]:
    sys.path.insert(0, str(BACKEND_SRC))
    from pegasus.main import app  # noqa: PLC0415

    exported = app.openapi()
    if not isinstance(exported, dict):
        raise SystemExit("FastAPI app.openapi() did not return a mapping.")
    return exported


def write_contract(spec: Mapping[str, Any]) -> None:
    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONTRACT_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            spec,
            handle,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
            width=120,
        )


def validate_contract(spec: Mapping[str, Any]) -> None:
    try:
        validate(spec)
    except OpenAPIValidationError as exc:
        raise SystemExit(f"OpenAPI contract is invalid: {exc}") from exc


def diff_summary(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> str:
    expected_paths = set(expected.get("paths", {}))
    actual_paths = set(actual.get("paths", {}))
    added = sorted(actual_paths - expected_paths)
    removed = sorted(expected_paths - actual_paths)

    lines = ["OpenAPI contract drift detected."]
    if added:
        lines.append("Paths in backend but missing from contract:")
        lines.extend(f"  + {path}" for path in added)
    if removed:
        lines.append("Paths in contract but missing from backend:")
        lines.extend(f"  - {path}" for path in removed)
    if not added and not removed:
        lines.append("Path list matches; schemas or operation details differ.")
        lines.append("Run: python scripts/sync_openapi_contract.py --write")
    else:
        lines.append("After intentional API changes run: python scripts/sync_openapi_contract.py --write")
    return "\n".join(lines)


def check_backend_contract() -> None:
    if not CONTRACT_PATH.is_file():
        raise SystemExit(f"Missing contract file: {CONTRACT_PATH}")

    contract = normalize_openapi(load_contract())
    backend = normalize_openapi(export_backend_openapi())

    if contract != backend:
        raise SystemExit(diff_summary(contract, backend))


def _openapi_path_matches(actual_path: str, template_path: str) -> bool:
    actual_parts = [part for part in actual_path.strip("/").split("/") if part]
    template_parts = [part for part in template_path.strip("/").split("/") if part]
    if len(actual_parts) != len(template_parts):
        return False
    for actual_part, template_part in zip(actual_parts, template_parts, strict=True):
        if template_part.startswith("{") and template_part.endswith("}"):
            continue
        if actual_part != template_part:
            return False
    return True


def _resolve_frontend_path(raw_path: str) -> str:
    path = raw_path.strip()
    if path.startswith(API_V1_PREFIX):
        return path
    if path.startswith("/"):
        return f"{API_V1_PREFIX}{path}"
    return f"{API_V1_PREFIX}/{path}"


def _extract_http_calls(source: str) -> list[tuple[str, str]]:
    """Return (METHOD, path) pairs from axios/httpClient usage."""
    calls: list[tuple[str, str]] = []

    # httpClient.get('/foo') or httpClient.post(E.bar, ...)
    for match in re.finditer(
        r"httpClient\.(get|post|put|patch|delete)\(\s*([^,\)]+)",
        source,
        flags=re.IGNORECASE,
    ):
        method = match.group(1).upper()
        arg = match.group(2).strip()
        path = _literal_or_template_path(arg, source)
        if path:
            calls.append((method, path))

    # axios.get(`${PELICAN_BASE_PATH}${SERVICE_ENDPOINT.X}`)
    for match in re.finditer(
        r"axios\.(get|post|put|patch|delete)\(\s*`?\$\{PELICAN_BASE_PATH\}\$\{SERVICE_ENDPOINT\.([A-Z0-9_]+)\}`?",
        source,
        flags=re.IGNORECASE,
    ):
        method = match.group(1).upper()
        endpoint_key = match.group(2)
        endpoint_match = re.search(
            rf"{endpoint_key}:\s*'([^']+)'",
            source,
        )
        if endpoint_match:
            calls.append((method, _resolve_frontend_path(endpoint_match.group(1))))

    return calls


def _literal_or_template_path(arg: str, source: str) -> str | None:
    if arg.startswith("E."):
        key = arg.removeprefix("E.").split("(")[0]
        if "(" in arg:
            # E.validateJob(jobId) → /validate/jobs/{job_id}
            template_match = re.search(rf"{re.escape(key)}:\s*\([^)]*\)\s*=>\s*`([^`]+)`", source)
            if template_match:
                template = template_match.group(1)
                return _resolve_frontend_path(template.replace("${jobId}", "{job_id}").replace("${runId}", "{run_id}"))
            fn_match = re.search(rf"{re.escape(key)}:\s*\([^)]*\)\s*=>\s*'([^']+)'", source)
            if fn_match:
                return _resolve_frontend_path(fn_match.group(1))
        const_match = re.search(rf"{re.escape(key)}:\s*'([^']+)'", source)
        if const_match:
            return _resolve_frontend_path(const_match.group(1))
        return None

    if arg.startswith("'") and arg.endswith("'"):
        return _resolve_frontend_path(arg[1:-1])
    if arg.startswith('"') and arg.endswith('"'):
        return _resolve_frontend_path(arg[1:-1])
    if arg.startswith("`") and arg.endswith("`"):
        inner = arg[1:-1]
        if "${" in inner:
            normalized = (
                inner.replace("${E.cloudConnections}", "/admin/cloud-connections")
                .replace("${connectionId}", "{connection_id}")
            )
            return _resolve_frontend_path(normalized)
        return _resolve_frontend_path(inner)
    return None


def _operation_exists(spec: Mapping[str, Any], path: str, method: str) -> bool:
    paths = spec.get("paths", {})
    method = method.lower()
    for template_path, operations in paths.items():
        if not isinstance(operations, dict):
            continue
        if method not in operations:
            continue
        if _openapi_path_matches(path, template_path):
            return True
    return False


def check_frontend_contract() -> None:
    if not CONTRACT_PATH.is_file():
        raise SystemExit(f"Missing contract file: {CONTRACT_PATH}")

    spec = load_contract()
    missing: list[str] = []

    for client_file in FRONTEND_CLIENT_FILES:
        if not client_file.is_file():
            raise SystemExit(f"Frontend client file not found: {client_file}")
        source = client_file.read_text(encoding="utf-8")
        for method, path in _extract_http_calls(source):
            if not _operation_exists(spec, path, method):
                missing.append(f"{client_file.relative_to(REPO_ROOT)}: {method} {path}")

    if missing:
        lines = [
            "Frontend calls paths/methods that are not declared in api/openapi.yaml:",
            *(f"  - {item}" for item in missing),
            "Update the contract (and backend) or fix the client.",
        ]
        raise SystemExit("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Verify backend + frontend match the contract")
    group.add_argument("--write", action="store_true", help="Write api/openapi.yaml from the FastAPI app")
    group.add_argument("--validate", action="store_true", help="Validate api/openapi.yaml only")
    group.add_argument(
        "--check-frontend",
        action="store_true",
        help="Verify frontend HTTP clients only (skip backend export)",
    )
    group.add_argument(
        "--check-backend",
        action="store_true",
        help="Verify FastAPI app matches api/openapi.yaml only",
    )
    args = parser.parse_args()

    if args.write:
        spec = export_backend_openapi()
        validate_contract(spec)
        write_contract(spec)
        print(f"Wrote {CONTRACT_PATH}")
        return

    if args.validate:
        validate_contract(load_contract())
        print(f"Valid OpenAPI contract: {CONTRACT_PATH}")
        return

    if args.check_backend or args.check:
        check_backend_contract()
        print("Backend matches api/openapi.yaml")

    if args.check_frontend or args.check:
        check_frontend_contract()
        print("Frontend clients are covered by api/openapi.yaml")

    if not any((args.check, args.validate, args.write, args.check_frontend, args.check_backend)):
        parser.print_help()
        raise SystemExit(2)


if __name__ == "__main__":
    main()
