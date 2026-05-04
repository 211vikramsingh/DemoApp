"""
FastAPI application factory.

Lifespan:
  - startup: create first-run admin if FIRST_RUN_ADMIN_USERNAME is set and no admin exists
  - shutdown: close Redis pool
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import get_settings
from app.core.database import _get_engine, Base

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    eng = _get_engine()
    # Create tables (dev convenience — use alembic in production)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # First-run admin seeding
    if settings.first_run_admin_username and settings.first_run_admin_password:
        await _seed_admin()

    yield

    await eng.dispose()


async def _seed_admin() -> None:
    from sqlalchemy import select
    from app.core.database import _get_session_maker
    from app.core.security import hash_password
    from app.models.user import User

    async with _get_session_maker()() as db:
        result = await db.execute(select(User).where(User.role == "admin"))
        if result.scalars().first():
            return  # admin already exists

        admin = User(
            username=settings.first_run_admin_username,
            email=f"{settings.first_run_admin_username}@localhost",
            hashed_password=hash_password(settings.first_run_admin_password),
            role="admin",
        )
        db.add(admin)
        await db.commit()
        logger.info("First-run admin created: %s", settings.first_run_admin_username)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Bot API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://frontend:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
