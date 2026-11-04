from fastapi import Depends
from sqlalchemy.orm import Session
from app.infrastructure.database.connection import get_db
from app.application.services.fabricacion_service import FabricacionService


def get_fabricacion_service(db: Session = Depends(get_db)):
    return FabricacionService(db)
