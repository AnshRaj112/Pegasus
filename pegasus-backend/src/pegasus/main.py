# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:25:15Z
# --- END GENERATED FILE METADATA ---

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pegasus.api.exception_handlers import register_exception_handlers
from pegasus.api.router import api_router
from pegasus.core.config import get_settings, loaded_dotenv_files

logger = logging.getLogger(__name__)


def _fmt_upload_limit(n: int) -> str:
    gib = 1024**3
    if n >= gib and n % gib == 0:
        return f"{n // gib} GiB"
    if n >= gib:
        return f"{n / gib:.1f} GiB"
    mib = 1024**2
    if n >= mib:
        return f"{n / mib:.0f} MiB"
    return f"{n} B"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    from pegasus.core.db_health_check import log_database_connection_status
    from pegasus.services.validation_job_queue import get_validation_queue

    await log_database_connection_status()

    settings = get_settings()
    # Start the concurrency-limited validation job queue drain loop
    queue = get_validation_queue(settings)
    queue.start_drain_loop()

    pool_n = int(settings.validation_worker_pool_size or 0)
    if pool_n > 0:
        from pegasus.services.validation_worker_pool import get_validation_pool

        get_validation_pool(pool_n)
        logger.info("Validation worker pool warmed max_workers=%d", pool_n)

    yield

    from pegasus.core.database import dispose_engine
    from pegasus.services.validation_worker_pool import shutdown_validation_worker_pool

    await queue.shutdown(wait=True)
    shutdown_validation_worker_pool(wait=True)
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    dotenv_list = [str(p) for p in loaded_dotenv_files()]
    logger.info(
        "Pegasus API starting. Dotenv files: %s.",
        dotenv_list or "(none — code defaults only)",
    )
    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    cors_origins = settings.cors_origin_list()
    if cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info("CORS enabled for origins: %s", cors_origins)
    else:
        logger.warning(
            "CORS disabled (PEGASUS_CORS_ORIGINS empty and not using development defaults). "
            "Browser requests from another origin (e.g. Vite on :5173 to API on :8000) will fail with "
            "\"Failed to fetch\" unless you use a reverse proxy or set PEGASUS_CORS_ORIGINS."
        )

    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()
