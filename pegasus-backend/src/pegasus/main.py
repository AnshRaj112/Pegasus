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
    yield
    from pegasus.core.database import dispose_engine

    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    dotenv_list = [str(p) for p in loaded_dotenv_files()]
    logger.info(
        "POST /validate upload limit (per file): %s bytes (~%s). Dotenv files: %s. "
        "Shell env PEGASUS_VALIDATION_MAX_UPLOAD_BYTES overrides .env. Remove 52428800 (50 MiB) from .env or export.",
        settings.validation_max_upload_bytes,
        _fmt_upload_limit(settings.validation_max_upload_bytes),
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
