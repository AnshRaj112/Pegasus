# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T11:17:59Z
# --- END GENERATED FILE METADATA ---

"""Host ↔ container path translation for local CSV validation (Docker bind mounts)."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status

from pegasus.core.config import Settings
from pegasus.core.file_pair import compute_file_pair_key, normalize_validation_path


def local_path_remap(settings: Settings) -> tuple[str, str] | None:
    """Return ``(host_prefix, container_prefix)`` when both are configured."""
    host = settings.validation_local_path_host_prefix.strip()
    container = settings.validation_local_path_container_prefix.strip()
    if not host or not container:
        return None
    return host.rstrip("/"), container.rstrip("/")


def to_container_path(raw: str, settings: Settings) -> str:
    """Map a UI/host path to the path the API worker should open inside the container."""
    text = (raw or "").strip()
    if not text:
        return text
    remap = local_path_remap(settings)
    if remap is None:
        return text
    host_prefix, container_prefix = remap
    if text == host_prefix or text.startswith(f"{host_prefix}/"):
        return f"{container_prefix}{text[len(host_prefix):]}"
    return text


def to_display_path(path: Path | str, settings: Settings) -> str:
    """Map a resolved container path to the host-facing path shown in the UI and history."""
    text = str(path).strip()
    if not text:
        return text
    remap = local_path_remap(settings)
    if remap is None:
        return text
    host_prefix, container_prefix = remap
    if text == container_prefix or text.startswith(f"{container_prefix}/"):
        return f"{host_prefix}{text[len(container_prefix):]}"
    return text


def local_path_resolve_candidates(raw: str, settings: Settings) -> list[str]:
    """Paths to try when opening a local file or directory (mapped first, then literal)."""
    text = (raw or "").strip()
    if not text:
        return []
    mapped = to_container_path(text, settings)
    ordered: list[str] = []
    if mapped:
        ordered.append(mapped)
    if text not in ordered:
        ordered.append(text)
    return ordered


def _path_exists(path: Path, *, must_be_dir: bool, must_be_file: bool) -> Path | None:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError):
        return None
    if must_be_dir and not resolved.is_dir():
        return None
    if must_be_file and not resolved.is_file():
        return None
    return resolved


def resolve_local_path_on_disk(
    raw: str,
    settings: Settings,
    *,
    must_be_dir: bool = False,
    must_be_file: bool = False,
) -> Path:
    """Resolve *raw* to an existing path, trying remap target then the literal path."""
    _ = settings  # used via candidates
    tried: list[str] = []
    for candidate in local_path_resolve_candidates(raw, settings):
        tried.append(candidate)
        resolved = _path_exists(Path(candidate), must_be_dir=must_be_dir, must_be_file=must_be_file)
        if resolved is not None:
            return resolved

    remap = local_path_remap(settings)
    hint = ""
    if remap:
        host_p, ctr_p = remap
        hint = (
            f" Path remap is enabled ({host_p} → {ctr_p}). "
            f"Mount {ctr_p} in Docker or unset PEGASUS_VALIDATION_LOCAL_PATH_HOST_PREFIX "
            f"and PEGASUS_VALIDATION_LOCAL_PATH_CONTAINER_PREFIX when using a 1:1 home mount."
        )
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail=f"Path not found: {raw!r}. Checked: {', '.join(tried) or '(empty)'}.{hint}",
    )


def _first_existing_directory(settings: Settings, *candidates: str) -> Path | None:
    for candidate in candidates:
        if not (candidate or "").strip():
            continue
        for variant in local_path_resolve_candidates(candidate, settings):
            resolved = _path_exists(Path(variant), must_be_dir=True, must_be_file=False)
            if resolved is not None:
                return resolved
    return None


def default_browse_path(settings: Settings) -> str:
    """Default directory for GET /validate/local/browse when *path* is omitted."""
    explicit = settings.validation_local_path_default_browse.strip()
    remap = local_path_remap(settings)
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    if remap:
        candidates.extend([remap[0], remap[1]])
    try:
        home = str(Path.home())
    except RuntimeError:
        home = ""
    if home:
        candidates.append(home)
    candidates.append("/")

    resolved = _first_existing_directory(settings, *candidates)
    if resolved is not None:
        return str(resolved)

    if explicit:
        return explicit
    if remap:
        return remap[0]
    return home or "/"


def default_browse_path_for_ui(settings: Settings) -> str:
    """Display-form default browse path (exists on disk when possible)."""
    raw = default_browse_path(settings)
    try:
        resolved = resolve_local_path_on_disk(raw, settings, must_be_dir=True)
        return to_display_path(resolved, settings)
    except HTTPException:
        return to_display_path(raw, settings)


def compute_file_pair_key_for_settings(
    source: str | None,
    target: str | None,
    settings: Settings,
) -> str | None:
    """Stable pair key using in-container paths so host/container aliases match."""
    if not source or not target:
        return None
    src = normalize_validation_path(to_container_path(source.strip(), settings)) or source.strip()
    tgt = normalize_validation_path(to_container_path(target.strip(), settings)) or target.strip()
    return compute_file_pair_key(src, tgt, normalize_paths=False)
