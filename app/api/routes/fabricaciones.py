from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.api.dependencies import get_fabricacion_service
from app.application.schemas.fabricacion_schema import (
    FabricacionCreate,
    FabricacionRead,
    FormulaRead,
    InicioResult,
    ValidacionError,
    ValidacionResult,
)
from app.application.services.fabricacion_service import FabricacionService
from app.core.exceptions import DomainError
from app.core.security import require_roles
from app.domain.entities.fabricacion import Fabricacion

router = APIRouter(prefix="/fabricaciones", tags=["Fabricaciones"])


@router.post("", response_model=FabricacionRead, status_code=201)
async def registrar(data: FabricacionCreate, service: FabricacionService = Depends(get_fabricacion_service),
                    usuario: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION"))) -> Fabricacion:
    fabricante_id = None
    if usuario.get("role") == "FABRICANTE":
        identidad_fabricante = usuario.get("sub")
        if (
            not isinstance(identidad_fabricante, str)
            or not identidad_fabricante.strip()
        ):
            raise HTTPException(
                status_code=403,
                detail="El token no identifica al fabricante",
            )
        fabricante_id = identidad_fabricante

    return await service.registrar(data, fabricante_id=fabricante_id)


@router.post(
    "/{fabricacion_id}/validacion",
    response_model=ValidacionResult,
    responses={409: {"model": ValidacionError}},
)
async def validar(
    fabricacion_id: UUID,
    service: FabricacionService = Depends(get_fabricacion_service),
    _: dict = Depends(require_roles(
        "FABRICANTE", "GERENTE_FABRICACION"
    )),
    ) -> ValidacionResult | JSONResponse:

    try:
        fabricacion, faltantes = await service.validar(
            fabricacion_id
        )

    except DomainError:
        raise

    except Exception as exc:
        raise DomainError(
            "La operación no pudo completarse, intente nuevamente más tarde",
            500,
        ) from exc

    if faltantes:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Materiales insuficientes para fabricar la orden",
                "faltantes": faltantes,
            },
        )

    return ValidacionResult(
        mensaje="Materiales disponibles: la orden puede iniciar su fabricación",
        id=fabricacion.id,
        estado=fabricacion.estado,
    )


@router.patch("/{fabricacion_id}/inicio", response_model=InicioResult)
async def iniciar(
    fabricacion_id: UUID,
    service: FabricacionService = Depends(get_fabricacion_service),
    usuario: dict = Depends(
        require_roles("FABRICANTE", "GERENTE_FABRICACION")
    ),
) -> InicioResult:
    try:
        fabricacion = await service.iniciar(fabricacion_id, usuario)

    except DomainError:
        raise

    except Exception as exc:
        raise DomainError(
            "La operación no pudo completarse, intente nuevamente más tarde",
            500,
        ) from exc

    return InicioResult(
        **FabricacionRead.model_validate(fabricacion).model_dump(),
        mensaje="La orden quedó en producción",
    )


@router.get("/{fabricacion_id}/formula", response_model=FormulaRead)
async def formula(
    fabricacion_id: UUID,
    service: FabricacionService = Depends(get_fabricacion_service),
    _: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION", "ENCARGADO_ENSAMBLAJE")),) -> dict:
    return await service.formula(fabricacion_id)


@router.post("/{fabricacion_id}/cierre", response_model=FabricacionRead)
async def cerrar(fabricacion_id: UUID, service: FabricacionService = Depends(get_fabricacion_service),
                 _: dict = Depends(require_roles("GERENTE_FABRICACION", "ENCARGADO_ENSAMBLAJE"))) -> Fabricacion:
    return await service.cerrar(fabricacion_id)


@router.post("/{fabricacion_id}/sincronizacion", response_model=FabricacionRead)
async def sincronizar(fabricacion_id: UUID, service: FabricacionService = Depends(get_fabricacion_service),
                      _: dict = Depends(require_roles("GERENTE_FABRICACION"))) -> Fabricacion:
    return await service.sincronizar(fabricacion_id)


@router.get("", response_model=list[FabricacionRead])
async def listar(page: int = Query(default=1, ge=1), estado: str | None = None,
                 modo: str | None = None,
                 service: FabricacionService = Depends(get_fabricacion_service),
                 _: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION", "ENCARGADO_ENSAMBLAJE"))) -> list[Fabricacion]:
    # modo=urgencia se deja como listado normal hasta disponer del contrato de existencias de producto terminado.
    return service.listar(page, estado)


@router.get("/{fabricacion_id}", response_model=FabricacionRead)
async def detalle(fabricacion_id: UUID, service: FabricacionService = Depends(get_fabricacion_service),
                  _: dict = Depends(require_roles("FABRICANTE", "GERENTE_FABRICACION", "ENCARGADO_ENSAMBLAJE"))) -> Fabricacion:
    return service.obtener(fabricacion_id)
