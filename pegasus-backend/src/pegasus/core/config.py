from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pegasus import __version__ as package_version


def _resolved_dotenv_files() -> tuple[Path, ...]:
    """Dotenv paths that do not depend on the process working directory.

    Files are loaded in order; **later files override earlier ones** for the same key
    (see pydantic-settings). We load ``<repo>/.env`` first, then ``pegasus-backend/.env``
    so the backend-local file wins when both exist.
    """
    backend_root = Path(__file__).resolve().parents[3]
    repo_root = backend_root.parent
    paths: list[Path] = []
    for candidate in (repo_root / ".env", backend_root / ".env"):
        if candidate.is_file():
            paths.append(candidate)
    return tuple(paths)


DOTENV_FILES_LOADED: tuple[Path, ...] = _resolved_dotenv_files()


def loaded_dotenv_files() -> tuple[Path, ...]:
    """Return ``.env`` paths used to build :class:`Settings` (repo root, then ``pegasus-backend/``)."""
    return DOTENV_FILES_LOADED


_SETTINGS_ENV_KWARGS: dict[str, object] = {
    "env_prefix": "PEGASUS_",
    "env_file_encoding": "utf-8",
    "extra": "ignore",
}
if DOTENV_FILES_LOADED:
    _SETTINGS_ENV_KWARGS["env_file"] = DOTENV_FILES_LOADED


class Settings(BaseSettings):
    model_config = SettingsConfigDict(**_SETTINGS_ENV_KWARGS)

    app_name: str = "Pegasus"
    version: str = package_version
    environment: str = Field(default="development", description="e.g. development, staging, production")
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = Field(
        default="postgresql+asyncpg://pegasus:pegasus@localhost:5432/pegasus",
        description="SQLAlchemy async URL (e.g. postgresql+asyncpg://...)",
    )

    cors_origins: str = Field(
        default="",
        description=(
            "Comma-separated allowed browser origins for cross-origin requests (e.g. the Vite dev URL). "
            "Required when the UI and API use different host/port (e.g. UI on :5173, API on :8000). "
            "Include both http://localhost:5173 and http://127.0.0.1:5173 if you use either in the browser. "
            "When empty and environment is development, defaults to those two origins so local dev works."
        ),
    )

    validation_max_upload_bytes: int = Field(
        default=100 * 1024 * 1024 * 1024,
        ge=1,
        description="Max bytes per individual CSV upload on POST /validate (each file checked separately)",
    )
    validation_mismatch_sample_limit: int = Field(
        default=100,
        ge=0,
        le=10_000,
        description=(
            "Max mismatch sample rows returned across mismatch_sample_groups (split by category). "
            "If set to 0, the API uses an automatic cap (up to 10_000) so the UI still receives samples."
        ),
    )
    enable_validation_persistence: bool = Field(
        default=False,
        description="Persist validation runs and mismatch rows to PostgreSQL",
    )

    validation_reconciliation_strategy: str = Field(
        default="auto",
        description="Reconciliation engine: auto | hash_partition | ordered_stream | sliding_window | external_sort",
    )
    validation_reconciliation_backend: str = Field(
        default="duckdb",
        description="duckdb (default) or polars spill/hash pipeline for single-character CSV reconciliation",
    )
    validation_force_external_reconciliation: bool = Field(
        default=True,
        description="When True, never load full single-char CSV pair into RAM for reconciliation (uses spill/DuckDB).",
    )
    validation_stream_mismatches_to_disk: bool = Field(
        default=True,
        description="Stream mismatch rows to NDJSON during spill/DuckDB runs instead of one giant Polars frame.",
    )
    validation_reconciliation_chunk_rows: int = Field(
        default=50_000,
        ge=1024,
        le=5_000_000,
        description="Rows per Polars batch for streaming / spill paths",
    )
    validation_reconciliation_partition_buckets: int = Field(
        default=512,
        ge=1,
        le=4096,
        description="Hash buckets for HASH_PARTITION and AUTO-unsorted spill mode",
    )
    validation_reconciliation_sliding_window: int = Field(
        default=0,
        ge=0,
        le=1_000_000,
        description="Look-ahead rows for sliding-window merge after external sort (0 = strict merge)",
    )
    validation_reconciliation_assume_sorted: bool = Field(
        default=False,
        description="Hint that CSV rows are globally sorted by UID (ordered_stream / AUTO)",
    )
    validation_external_memory_threshold_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=0,
        description=(
            "AUTO selects Polars spill reconciliation when combined CSV size exceeds this (single-char delim). "
            "Multi-character delimiters use chunked pandas spill when combined size exceeds this (avoids OOM)."
        ),
    )
    validation_reconciliation_temp_dir: str | None = Field(
        default=None,
        description="Optional directory for spill/sort temp files (default: system temp)",
    )
    validation_reconciliation_retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Retries for transient I/O failures during spill/sort phases",
    )
    validation_reconciliation_sub_partition_buckets: int = Field(
        default=1,
        ge=1,
        le=256,
        description="Secondary hash buckets per primary partition (1 = off); reduces skewed bucket size",
    )
    validation_reconciliation_parallel_spill: bool = Field(
        default=True,
        description="Spill source and target CSV concurrently in hash-partition mode",
    )
    validation_reconciliation_disk_headroom_multiplier: float = Field(
        default=2.0,
        ge=1.0,
        le=10.0,
        description="Require free disk >= multiplier × (source+target bytes) before spill/sort",
    )
    validation_reconciliation_mismatch_ndjson_mirror: bool = Field(
        default=False,
        description="Append mismatch rows to mismatch_mirror.ndjson under the temp workspace (hash runs)",
    )
    validation_duckdb_memory_limit_ratio: float = Field(
        default=1.00,
        ge=0.10,
        le=1.00,
        description="Fraction of machine RAM assigned to DuckDB memory_limit for reconciliation jobs.",
    )
    validation_duckdb_network_threads: int = Field(
        default=2,
        ge=1,
        le=64,
        description="DuckDB thread cap when CSVs are on network filesystems (avoid I/O saturation).",
    )
    validation_duckdb_local_threads: int = Field(
        default=0,
        ge=0,
        le=256,
        description="DuckDB thread cap for local disks (0 => auto cpu_count).",
    )
    validation_duckdb_enable_object_cache: bool = Field(
        default=True,
        description="Enable DuckDB object cache for local-file validation jobs.",
    )
    validation_duckdb_explain_analyze: bool = Field(
        default=False,
        description="Enable EXPLAIN ANALYZE logging for DuckDB reconciliation stages (diagnostic; slower).",
    )
    validation_allow_local_paths: bool = Field(
        default=False,
        description="When True, POST /validate/local may read CSVs from server paths (see local_path_roots)",
    )
    validation_local_path_roots: str = Field(
        default="",
        description="Comma-separated absolute directory prefixes allowed for /validate/local (e.g. /data/csv,/bulk)",
    )
    validation_value_mismatch_column_stats_max_rows: int = Field(
        default=250_000,
        ge=0,
        le=10_000_000,
        description=(
            "If value_mismatch row count exceeds this, skip per-column value_mismatch_by_column aggregation "
            "(saves RAM on huge reports). Set 0 to disable the cap."
        ),
    )
    validation_jobs_directory: str | None = Field(
        default=None,
        description="Base directory for background validation jobs (default: system temp / pegasus_validation_jobs)",
    )
    validation_memory_log_interval_seconds: int = Field(
        default=30,
        ge=0,
        le=3600,
        description="RSS logging interval in validation worker subprocesses; 0 disables the memory monitor thread.",
    )

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw:
            return [o.strip() for o in raw.split(",") if o.strip()]
        if self.environment.strip().lower() == "development":
            return [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
            ]
        return []

    def validation_local_path_root_list(self) -> list[Path]:
        """Allowlist roots for :func:`pegasus.api.v1.validation.resolve_local_csv_path`."""
        raw = self.validation_local_path_roots.strip()
        if not raw:
            return []
        return [Path(p.strip()).expanduser() for p in raw.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
