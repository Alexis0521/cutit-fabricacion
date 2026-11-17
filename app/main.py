from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import fabricaciones, health, notificaciones
from app.core.exceptions import register_exception_handlers
from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.connection import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Bootstrap convenience for the basic archetype. Use Alembic migrations in managed environments.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="CUTIT - Fabricación", version="1.0.0", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(fabricaciones.router)
app.include_router(notificaciones.router)
app.include_router(health.router)
