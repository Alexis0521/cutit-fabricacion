from fastapi import APIRouter, Header, HTTPException

from app.application.schemas.fabricacion_schema import (
    FabricacionCreate,
    NotificacionCreate,
)
from app.application.services.fabricacion_service import FabricacionService
from app.core.config import settings
from app.domain.entities.fabricacion import Fabricacion
from app.infrastructure.database.connection import SessionLocal

router = APIRouter(tags=["Notificaciones"])


@router.post("/fabricaciones/desde-notificacion", status_code=201)
async def desde_notificacion(data: NotificacionCreate, x_api_key: str = Header()) -> Fabricacion:
    if x_api_key != settings.callback_api_key:
        raise HTTPException(status_code=401, detail="API Key inválida")

    fabricacion_data = FabricacionCreate.model_validate(data.model_dump())
    with SessionLocal() as db:
        return await FabricacionService(db).registrar(fabricacion_data)
