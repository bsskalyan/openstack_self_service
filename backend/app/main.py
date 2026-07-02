from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, status

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.middleware.cors import configure_cors


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s", settings.app_name)
    yield
    logger.info("Stopping %s", settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    configure_cors(app, settings.cors_origins)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", status_code=status.HTTP_200_OK, tags=["health"])
    async def health_check() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment,
        }

    return app


app = create_app()
