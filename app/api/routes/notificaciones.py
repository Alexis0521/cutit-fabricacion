from fastapi import APIRouter, Header, HTTPException
from app.core.config import settings
from app.application.schemas.fabricacion_schema import NotificacionCreate
from app.infrastructure.database.connection import SessionLocal
from app.application.services.fabricacion_service import FabricacionService

router = APIRouter(tags=["Notificaciones"])


@router.post("/fabricaciones/desde-notificacion", status_code=201)
async def desde_notificacion(data: NotificacionCreate, x_api_key: str = Header()):
    if x_api_key != settings.callback_api_key:
        raise HTTPException(status_code=401, detail="API Key inválida")
    with SessionLocal() as db:
        return await FabricacionService(db).registrar(data)
