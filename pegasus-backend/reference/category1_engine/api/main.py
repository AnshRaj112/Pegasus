# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:26:33Z
# --- END GENERATED FILE METADATA ---

"""FastAPI application for Category-1 Reconciliation Platform."""

from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from category1.config import ReconciliationConfig
from category1.models.schemas import (
    ConnectionConfig,
    DataSourceType,
    FileFormat,
    JobStatus,
    KeyStrategy,
    ReconciliationJobConfig,
)
from category1.pipeline.job_manager import JobManager

app = FastAPI(
    title="Category-1 Reconciliation Platform",
    description="Enterprise tabular data reconciliation with external-memory processing",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = ReconciliationConfig()
job_manager = JobManager(config)

UPLOAD_DIR = config.work_dir / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/api/config/defaults")
async def get_defaults():
    from category1.config import DEFAULT_CHUNK_SIZES, DEFAULT_PARTITION_COUNTS
    return {
        "chunk_sizes": DEFAULT_CHUNK_SIZES,
        "partition_counts": DEFAULT_PARTITION_COUNTS,
        "file_formats": [f.value for f in FileFormat],
        "source_types": [s.value for s in DataSourceType if s != DataSourceType.FILE],
        "key_strategies": [k.value for k in KeyStrategy],
    }


@app.post("/api/jobs")
async def create_job(job_config: ReconciliationJobConfig):
    summary = job_manager.submit_job(job_config)
    return summary


@app.post("/api/jobs/upload")
async def create_job_with_upload(
    source_file: UploadFile = File(...),
    target_file: UploadFile = File(...),
    key_columns: str = Form(...),
    file_format: str = Form("csv"),
    chunk_size: int = Form(10000),
    num_partitions: int = Form(4096),
    memory_limit_mb: int = Form(1024),
    key_strategy: str = Form("primary"),
):
    job_config = ReconciliationJobConfig(
        source=ConnectionConfig(
            source_type=DataSourceType.FILE,
            file_path=str(UPLOAD_DIR / f"source_{source_file.filename}"),
            file_format=FileFormat(file_format),
        ),
        target=ConnectionConfig(
            source_type=DataSourceType.FILE,
            file_path=str(UPLOAD_DIR / f"target_{target_file.filename}"),
            file_format=FileFormat(file_format),
        ),
        key_columns=[c.strip() for c in key_columns.split(",")],
        key_strategy=KeyStrategy(key_strategy),
        chunk_size=chunk_size,
        num_partitions=num_partitions,
        memory_limit_mb=memory_limit_mb,
    )

    source_path = UPLOAD_DIR / f"{job_config.job_id}_source_{source_file.filename}"
    target_path = UPLOAD_DIR / f"{job_config.job_id}_target_{target_file.filename}"
    job_config.source.file_path = str(source_path)
    job_config.target.file_path = str(target_path)

    content = await source_file.read()
    source_path.write_bytes(content)
    content = await target_file.read()
    target_path.write_bytes(content)

    summary = job_manager.submit_job(job_config)
    return summary


@app.get("/api/jobs")
async def list_jobs():
    return job_manager.list_jobs()


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: UUID):
    result = job_manager.get_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@app.get("/api/jobs/{job_id}/summary")
async def get_job_summary(job_id: UUID):
    summary = job_manager.get_summary(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Job not found")
    return summary


@app.get("/api/jobs/{job_id}/report")
async def get_job_report(job_id: UUID):
    report_path = config.work_dir / str(job_id) / "reports" / "VALIDATION_RESULTS.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not yet available")
    return FileResponse(report_path, media_type="text/markdown", filename="VALIDATION_RESULTS.md")


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: UUID):
    if not job_manager.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "deleted"}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: UUID):
    if not job_manager.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "cancelled"}


@app.post("/api/schema/preview")
async def preview_schema(connection: ConnectionConfig):
    from category1.readers.base import StreamingReader
    try:
        reader = StreamingReader.create(connection)
        schema = reader.get_schema()
        return schema
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
