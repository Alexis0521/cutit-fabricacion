from fastapi import APIRouter
from sqlalchemy import text
from app.infrastructure.database.connection import engine

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}
