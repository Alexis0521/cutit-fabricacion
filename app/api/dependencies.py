from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services.fabricacion_service import FabricacionService
from app.infrastructure.database.connection import get_db


def get_fabricacion_service(db: Session = Depends(get_db)) -> FabricacionService:
    return FabricacionService(db)
