# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-10T15:48:52+05:30
# --- END GENERATED FILE METADATA ---

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from pegasus import __version__ as package_version
from pegasus.core.resource_tuning import recommended_reconciliation_partition_buckets


def _resolved_dotenv_files() -> tuple[Path, ...]:
    """Dotenv paths that do not depend on the process working directory.

    Files are loaded in order; **later files override earlier ones** for the same key
    (see pydantic-settings). We load ``<repo>/.env`` first, then ``pegasus-backend/.env``,
    then ``pegasus-backend/.env.backend`` so the backend-local files win when both exist.
    """
    backend_root = Path(__file__).resolve().parents[3]
    repo_root = backend_root.parent
    paths: list[Path] = []
    for candidate in (repo_root / ".env", backend_root / ".env", backend_root / ".env.backend"):
        if candidate.is_file():
            paths.append(candidate)
    return tuple(paths)


DOTENV_FILES_LOADED: tuple[Path, ...] = _resolved_dotenv_files()


def loaded_dotenv_files() -> tuple[Path, ...]:
    """Return ``.env`` paths used to build :class:`Settings` (repo root, backend, backend override)."""
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
    database_encryption_key: str | None = Field(
        default=None,
        description=(
            "Fernet key used to encrypt validation history payloads before they are written to PostgreSQL."
        ),
    )
    admin_api_token: str | None = Field(
        default=None,
        description=(
            "Static admin token required for privileged admin APIs "
            "(for example cloud connection management)."
        ),
    )
    admin_session_ttl_hours: int = Field(
        default=24 * 7,
        ge=1,
        le=24 * 365,
        description="Admin session lifetime in hours.",
    )
    admin_session_cookie_secure: bool = Field(
        default=False,
        description="Set True to mark the admin session cookie as Secure (HTTPS-only).",
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
        default=0,
        ge=0,
        description=(
            "Max value_mismatch sample rows in mismatch_sample_groups.value_mismatch "
            "(stratified across columns when > 0). 0 returns every value mismatch."
        ),
    )
    validation_presence_mismatch_response_max_rows: int = Field(
        default=2_000_000,
        ge=0,
        le=50_000_000,
        description=(
            "Max rows returned per side for missing_in_target and extra_in_target in the validation API. "
            "0 means unlimited (full scan of mismatch NDJSON). Value mismatches are not affected."
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
    validation_force_external_reconciliation: bool = Field(
        default=True,
        description="When True, never load full single-char CSV pair into RAM for reconciliation (uses Polars spill).",
    )
    validation_stream_mismatches_to_disk: bool = Field(
        default=True,
        description="Stream mismatch rows to NDJSON during spill runs instead of one giant Polars frame.",
    )
    validation_reconciliation_chunk_rows: int = Field(
        default=500_000,
        ge=1024,
        le=5_000_000,
        description="Rows per Polars batch for streaming / spill paths (larger batches use more RAM, fewer passes)",
    )
    validation_reconciliation_partition_buckets: int = Field(
        default_factory=recommended_reconciliation_partition_buckets,
        ge=1,
        le=8192,
        description=(
            "Hash buckets for HASH_PARTITION, AUTO spill, and Category-1 tabular pipeline. "
            "Default is host-sized. Values above the host cap are clamped at runtime."
        ),
    )
    validation_tabular_partition_preset: str | None = Field(
        default=None,
        description="Optional pipeline preset: small|medium|large|xlarge (1024–8192 buckets).",
    )
    validation_tabular_enable_column_drilldown: bool = Field(
        default=True,
        description="Stage 6 column-level diff for changed rows in the tabular pipeline.",
    )
    validation_tabular_decimal_equivalence: bool = Field(
        default=True,
        description="Treat 100 and 100.00 as equal when canonicalizing for fingerprints.",
    )
    validation_tabular_decimal_scale: int = Field(default=2, ge=0, le=18)
    validation_tabular_enable_hll_precheck: bool = Field(
        default=False,
        description="Use HyperLogLog sketch in Stage 3 for fast inequality detection (approximate).",
    )
    validation_columnar_spill_threshold_bytes: int = Field(
        default=50 * 1024 * 1024,
        ge=0,
        description=(
            "When combined columnar file size exceeds this, spill Parquet batches to hash "
            "partitions before compare (uses pipeline adapters when enabled)."
        ),
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
        default=1.5,
        ge=1.0,
        le=10.0,
        description="Require free disk >= multiplier × (source+target bytes) before spill/sort",
    )
    validation_reconciliation_mismatch_ndjson_mirror: bool = Field(
        default=False,
        description="Append mismatch rows to mismatch_mirror.ndjson under the temp workspace (hash runs)",
    )
    validation_allow_local_paths: bool = Field(
        default=False,
        description="When True, POST /validate/local and GET /validate/local/browse may use any server path",
    )
    validation_local_path_roots: str = Field(
        default="",
        description="Deprecated (ignored). Paths are chosen at runtime via the UI or API request body.",
    )
    validation_local_path_host_prefix: str = Field(
        default="",
        description=(
            "When set with validation_local_path_container_prefix, API paths under this host "
            "prefix are translated before opening files (Docker bind mounts)."
        ),
    )
    validation_local_path_container_prefix: str = Field(
        default="",
        description="In-container mount point paired with validation_local_path_host_prefix.",
    )
    validation_local_path_default_browse: str = Field(
        default="",
        description=(
            "Default directory for GET /validate/local/browse when path is omitted. "
            "Use the in-container path (e.g. /data/pegasus) when running in Docker."
        ),
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
    validation_partition_reconcile_workers: int = Field(
        default=0,
        ge=0,
        le=32,
        description=(
            "Process pool size for partition reconcile (0=auto up to cpu-1, 1=sequential)."
        ),
    )
    validation_skip_artifact_report: bool = Field(
        default=True,
        description="Skip writing VALIDATION_RESULTS.md under job_dir (saves I/O on background jobs).",
    )
    validation_progress_status_interval_seconds: float = Field(
        default=2.5,
        ge=0.5,
        le=60.0,
        description=(
            "Minimum seconds between status.json progress writes during validation "
            "(stage metrics still go to worker.log and stage_metrics.log)."
        ),
    )
    validation_enable_content_digest_precheck: bool = Field(
        default=True,
        description="Compare precomputed content digests before reconcile (GCS metadata MD5/CRC32C).",
    )
    validation_worker_pool_size: int = Field(
        default=2,
        ge=0,
        le=32,
        description=(
            "When >0, reuse a ProcessPoolExecutor of that size for validation jobs (warmer imports). "
            "When 0, spawn a fresh subprocess per job (slow cold start)."
        ),
    )
    validation_max_concurrency: int = Field(
        default=2,
        ge=1,
        description=(
            "Maximum parallel validation jobs (FIFO queue). "
            "Users can override at runtime via PATCH /api/v1/validate/queue."
        ),
    )
    validation_auto_tune_enabled: bool = Field(
        default=False,
        description=(
            "When true, cap effective concurrency using live RAM/disk/CPU probes. "
            "When false (default), only max_concurrency is used."
        ),
    )
    validation_auto_detect_format: bool = Field(
        default=True,
        description=(
            "When true, local validation uses multi-layer file detection to resolve "
            "file_format=auto and to warn when declared format disagrees with content."
        ),
    )
    validation_auto_extract_archives: bool = Field(
        default=True,
        description=(
            "When true, gzip/bzip2/zip/tar inputs are materialized to a bounded temp "
            "file under the job directory before validation runs."
        ),
    )
    validation_archive_max_extract_bytes: int = Field(
        default=512 * 1024 * 1024,
        ge=1024 * 1024,
        description="Maximum uncompressed bytes per archive member when auto-extracting.",
    )

    @model_validator(mode="after")
    def _validate_encryption_key(self) -> "Settings":
        key = (self.database_encryption_key or "").strip()
        if self.enable_validation_persistence and not key:
            raise ValueError(
                "PEGASUS_DATABASE_ENCRYPTION_KEY is required when PEGASUS_ENABLE_VALIDATION_PERSISTENCE=true"
            )
        return self
    validation_queue_ram_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        le=32.0,
        description=(
            "RAM multiplier for small in-memory jobs; large streaming jobs use chunk-based estimates."
        ),
    )
    validation_queue_ram_reserve_bytes: int = Field(
        default=1 * 1024**3,
        ge=0,
        description="RAM kept free for OS and other processes when computing safe parallel job slots.",
    )
    validation_queue_min_ram_per_job_bytes: int = Field(
        default=100 * 1024**2,
        ge=1 * 1024**2,
        description="Floor for per-job RAM estimate used by the resource advisor.",
    )
    validation_queue_min_disk_per_job_bytes: int = Field(
        default=50 * 1024**2,
        ge=1 * 1024**2,
        description="Floor for per-job disk estimate used by the resource advisor.",
    )
    validation_queue_disk_reserve_bytes: int = Field(
        default=500 * 1024**2,
        ge=0,
        description="Disk kept free beyond per-job spill estimates when computing safe parallel job slots.",
    )
    validation_queue_threads_per_job: int = Field(
        default=0,
        ge=0,
        le=128,
        description=(
            "Startup default for worker parallelism inside each validation job (partition compare). "
            "0 = auto (use all logical CPUs). Users override at runtime via PATCH /api/v1/validate/queue."
        ),
    )
    validation_queue_disk_headroom_multiplier: float | None = Field(
        default=None,
        ge=1.0,
        le=10.0,
        description=(
            "Startup default disk headroom per job for queue/UI (multiplier × combined CSV bytes). "
            "None uses validation_reconciliation_disk_headroom_multiplier."
        ),
    )
    validation_memory_budget_bytes: int = Field(
        default=10 * 1024 * 1024 * 1024,
        ge=256 * 1024 * 1024,
        description="Hard RAM cap per validation job (default 10 GiB).",
    )
    validation_target_duration_seconds: int = Field(
        default=15 * 60,
        ge=60,
        le=24 * 60 * 60,
        description="Target completion time used to tune reconciliation runtime settings.",
    )
    validation_enable_merkle_fast_path: bool = Field(
        default=True,
        description="Enable streaming Merkle precheck to skip full reconciliation when files are identical.",
    )
    validation_enable_in_memory_reconcile: bool = Field(
        default=True,
        description=(
            "Load both files into RAM for a Polars join fast path when size allows. "
            "Set false to prefer disk spill for all workloads."
        ),
    )
    validation_gcs_streaming_only: bool = Field(
        default=True,
        description=(
            "When true (default), GCS validation streams objects via open_gcs_binary / PyArrow CSV only."
        ),
    )
    validation_auto_in_memory_max_bytes: int = Field(
        default=256 * 1024 * 1024,
        ge=1024 * 1024,
        le=512 * 1024 * 1024,
        description=(
            "When combined source+target size is at or below this threshold, "
            "use the Polars in-memory reconcile fast path even if "
            "validation_enable_in_memory_reconcile is false."
        ),
    )
    validation_global_memory_budget_bytes: int = Field(
        default=10 * 1024 * 1024 * 1024,
        ge=512 * 1024 * 1024,
        description=(
            "Global RAM budget for all concurrent validation jobs combined. "
            "Queue admission splits this across running slots."
        ),
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
        """Legacy helper; roots are no longer enforced for local path access."""
        raw = self.validation_local_path_roots.strip()
        if not raw:
            return []
        return [Path(p.strip()).expanduser() for p in raw.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
