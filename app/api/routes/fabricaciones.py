from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import get_fabricacion_service
from app.application.schemas.fabricacion_schema import FabricacionCreate, FabricacionRead, ValidacionResult, Faltante
from app.application.services.fabricacion_service import FabricacionService
from app.core.security import require_roles

router = APIRouter(prefix="/fabricaciones", tags=["Fabricaciones"])


@router.post("", response_model=FabricacionRead, status_code=201)
async def registrar(data: FabricacionCreate, service: FabricacionService = Depends(get_fabricacion_service),
                    _: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION"))):
    return await service.registrar(data)


@router.post("/{fabricacion_id}/validacion", response_model=ValidacionResult)
async def validar(fabricacion_id: UUID, service: FabricacionService = Depends(get_fabricacion_service),
                  _: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION"))):
    entity, faltantes = await service.validar(fabricacion_id)
    return {"disponible": not faltantes, "faltantes": faltantes}


@router.patch("/{fabricacion_id}/inicio", response_model=FabricacionRead)
async def iniciar(fabricacion_id: UUID, service: FabricacionService = Depends(get_fabricacion_service),
                  _: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION"))):
    return await service.iniciar(fabricacion_id)


@router.get("/{fabricacion_id}/formula")
async def formula(fabricacion_id: UUID, service: FabricacionService = Depends(get_fabricacion_service),
                  _: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION", "ENCARGADO_ENSAMBLAJE"))):
    return await service.formula(fabricacion_id)


@router.post("/{fabricacion_id}/cierre", response_model=FabricacionRead)
async def cerrar(fabricacion_id: UUID, service: FabricacionService = Depends(get_fabricacion_service),
                 _: dict = Depends(require_roles("GERENTE_FABRICACION", "ENCARGADO_ENSAMBLAJE"))):
    return await service.cerrar(fabricacion_id)


@router.post("/{fabricacion_id}/sincronizacion", response_model=FabricacionRead)
async def sincronizar(fabricacion_id: UUID, service: FabricacionService = Depends(get_fabricacion_service),
                      _: dict = Depends(require_roles("GERENTE_FABRICACION"))):
    return await service.sincronizar(fabricacion_id)


@router.get("", response_model=list[FabricacionRead])
async def listar(page: int = Query(default=1, ge=1), estado: str | None = None,
                 modo: str | None = None,
                 service: FabricacionService = Depends(get_fabricacion_service),
                 _: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION", "ENCARGADO_ENSAMBLAJE"))):
    # modo=urgencia se deja como listado normal hasta disponer del contrato de existencias de producto terminado.
    return service.listar(page, estado)


@router.get("/{fabricacion_id}", response_model=FabricacionRead)
async def detalle(fabricacion_id: UUID, service: FabricacionService = Depends(get_fabricacion_service),
                  _: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION", "ENCARGADO_ENSAMBLAJE"))):
    return service.obtener(fabricacion_id)
