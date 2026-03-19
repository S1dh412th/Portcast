from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.config import settings
from app.db import init_db


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    try:
        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            try:
                init_db()
                # Test Redis connection if enabled
                if settings.redis.enabled:
                    try:
                        from app.services.cache import cache
                        cache._get_client().ping()
                        print("✅ Redis connection established")
                    except Exception as e:
                        print(f"⚠️  Redis unavailable at startup: {e}")
                        print("📝 Application will continue without caching")
                        cache.enabled = False
                yield
            except Exception as e:
                print(f"Error during application startup: {e}")
                raise

        app = FastAPI(
            title=settings.api.title,
            version=settings.api.version,
            description=settings.api.description,
            lifespan=lifespan
        )
        app.include_router(router)

        return app
    except Exception as e:
        raise RuntimeError(f"Failed to create FastAPI application: {e}") from e


app = create_app()

