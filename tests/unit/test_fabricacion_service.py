from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest

from app.application.schemas.fabricacion_schema import FabricacionCreate
from app.application.services import fabricacion_service as service_module
from app.core.exceptions import DomainError
from app.domain.entities.fabricacion import Fabricacion
from app.domain.enums.estados import (
    EstadoFabricacion,
    EstadoSincronizacion,
    TipoProducto,
)
from app.infrastructure.external.inventario_client import InventarioClient
from app.infrastructure.external.materiales_client import MaterialesClient
from app.infrastructure.repositories.fabricacion_repository import FabricacionRepository

FORMULA = {
    "estado": "APROBADA",
    "version": "2",
    "items": [{"codigo": "ACERO", "cantidad": 100}],
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_fabricacion(
    estado: EstadoFabricacion = EstadoFabricacion.REGISTRADA,
    sincronizacion: EstadoSincronizacion = EstadoSincronizacion.PENDIENTE,
    formula_snapshot: dict | None = None,
) -> Fabricacion:
    return Fabricacion(
        referencia_material="MAT-1",
        tipo_producto=TipoProducto.CADENA,
        cantidad=3,
        estado=estado,
        sincronizacion=sincronizacion,
        formula_snapshot=formula_snapshot,
    )


@pytest.fixture
def make_service(monkeypatch: pytest.MonkeyPatch):
    def factory(fabricacion: Fabricacion | None = None):
        repository = Mock(spec=FabricacionRepository)
        repository.get.return_value = fabricacion
        repository.save.side_effect = lambda entity: entity

        materiales = Mock(spec=MaterialesClient)
        materiales.obtener_material = AsyncMock()
        materiales.obtener_formula = AsyncMock()

        inventario = Mock(spec=InventarioClient)
        inventario.consultar_disponibilidad = AsyncMock()
        inventario.descontar = AsyncMock()

        monkeypatch.setattr(service_module, "FabricacionRepository", lambda _: repository)
        monkeypatch.setattr(service_module, "MaterialesClient", lambda: materiales)
        monkeypatch.setattr(service_module, "InventarioClient", lambda: inventario)

        return service_module.FabricacionService(Mock()), repository, materiales, inventario

    return factory


@pytest.mark.anyio
async def test_registrar_crea_y_guarda_una_fabricacion_con_formula_aprobada(make_service):
    service, repository, materiales, _ = make_service()
    materiales.obtener_material.return_value = {"formula": FORMULA}
    data = FabricacionCreate(
        referencia_material="MAT-1",
        tipo_producto=TipoProducto.CADENA,
        cantidad=3,
        observaciones="Orden urgente",
    )

    result = await service.registrar(data)

    materiales.obtener_material.assert_awaited_once_with("MAT-1")
    repository.save.assert_called_once()
    saved = repository.save.call_args.args[0]
    assert result is saved
    assert (saved.referencia_material, saved.tipo_producto, saved.cantidad) == (
        "MAT-1",
        TipoProducto.CADENA,
        3,
    )
    assert saved.observaciones == "Orden urgente"


@pytest.mark.anyio
@pytest.mark.parametrize("formula", [{}, {"estado": "BORRADOR"}])
async def test_registrar_rechaza_formula_no_aprobada_sin_guardar(make_service, formula):
    service, repository, materiales, _ = make_service()
    materiales.obtener_material.return_value = {"formula": formula}
    data = FabricacionCreate(
        referencia_material="MAT-1",
        tipo_producto=TipoProducto.CADENA,
        cantidad=3,
    )

    with pytest.raises(DomainError, match="no está aprobada") as error:
        await service.registrar(data)

    assert error.value.status_code == 409
    repository.save.assert_not_called()


@pytest.mark.anyio
async def test_registrar_propaga_error_del_cliente_de_materiales(make_service):
    service, repository, materiales, _ = make_service()
    materiales.obtener_material.side_effect = httpx.ConnectError("materials unavailable")
    data = FabricacionCreate(
        referencia_material="MAT-1",
        tipo_producto=TipoProducto.CADENA,
        cantidad=3,
    )

    with pytest.raises(httpx.ConnectError, match="materials unavailable"):
        await service.registrar(data)

    repository.save.assert_not_called()


@pytest.mark.anyio
async def test_validar_con_faltantes_devuelve_la_entidad_sin_cambiarla(make_service):
    entity = make_fabricacion()
    faltantes = [{"codigo": "ACERO", "diferencia": 2}]
    service, repository, _, inventario = make_service(entity)
    inventario.consultar_disponibilidad.return_value = faltantes

    result, result_faltantes = await service.validar(entity.id)

    assert result is entity
    assert result_faltantes == faltantes
    assert entity.estado == EstadoFabricacion.REGISTRADA
    inventario.consultar_disponibilidad.assert_awaited_once_with("MAT-1", {}, 3)
    repository.save.assert_not_called()


@pytest.mark.anyio
async def test_validar_sin_faltantes_transiciona_y_guarda_como_validada(make_service):
    entity = make_fabricacion()
    service, repository, _, inventario = make_service(entity)
    inventario.consultar_disponibilidad.return_value = []

    result, faltantes = await service.validar(entity.id)

    assert result is entity
    assert faltantes == []
    assert entity.estado == EstadoFabricacion.VALIDADA
    repository.save.assert_called_once_with(entity)


@pytest.mark.anyio
async def test_validar_falla_si_no_existe_la_fabricacion(make_service):
    service, repository, _, inventario = make_service()

    with pytest.raises(DomainError, match="Fabricación no encontrada") as error:
        await service.validar(uuid4())

    assert error.value.status_code == 404
    inventario.consultar_disponibilidad.assert_not_awaited()
    repository.save.assert_not_called()


@pytest.mark.anyio
async def test_iniciar_obtiene_formula_aprobada_y_guarda_transicion(make_service):
    entity = make_fabricacion(estado=EstadoFabricacion.VALIDADA)
    service, repository, materiales, _ = make_service(entity)
    materiales.obtener_formula.return_value = FORMULA

    result = await service.iniciar(entity.id)

    materiales.obtener_formula.assert_awaited_once_with("MAT-1")
    assert result is entity
    assert entity.estado == EstadoFabricacion.EN_PROCESO
    assert entity.formula_version == "2"
    assert entity.formula_snapshot == FORMULA
    assert entity.started_at is not None
    repository.save.assert_called_once_with(entity)


@pytest.mark.anyio
async def test_iniciar_propaga_error_de_entidad_si_no_esta_validada(make_service):
    entity = make_fabricacion()
    service, repository, materiales, _ = make_service(entity)
    materiales.obtener_formula.return_value = FORMULA

    with pytest.raises(DomainError, match="Solo se pueden iniciar"):
        await service.iniciar(entity.id)

    assert entity.estado == EstadoFabricacion.REGISTRADA
    repository.save.assert_not_called()


@pytest.mark.anyio
async def test_formula_devuelve_snapshot_durante_fabricacion(make_service):
    entity = make_fabricacion(
        estado=EstadoFabricacion.EN_PROCESO,
        formula_snapshot=FORMULA,
    )
    service, _, _, _ = make_service(entity)

    result = await service.formula(entity.id)

    assert result is FORMULA


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("estado", "snapshot", "message"),
    [
        (EstadoFabricacion.REGISTRADA, FORMULA, "solo está disponible"),
        (EstadoFabricacion.EN_PROCESO, None, "fórmula está incompleta"),
        (EstadoFabricacion.CERRADA, {"version": "2"}, "fórmula está incompleta"),
    ],
)
async def test_formula_rechaza_estado_o_snapshot_incompleto(
    make_service, estado, snapshot, message
):
    entity = make_fabricacion(estado=estado, formula_snapshot=snapshot)
    service, _, _, _ = make_service(entity)

    with pytest.raises(DomainError, match=message):
        await service.formula(entity.id)


@pytest.mark.anyio
async def test_cerrar_descuenta_inventario_y_guarda_estado_cerrado(make_service):
    entity = make_fabricacion(
        estado=EstadoFabricacion.EN_PROCESO,
        formula_snapshot=FORMULA,
    )
    service, repository, _, inventario = make_service(entity)

    result = await service.cerrar(entity.id)

    assert result is entity
    inventario.descontar.assert_awaited_once_with(
        str(entity.id), "MAT-1", FORMULA, 3
    )
    assert repository.save.call_count == 2
    assert entity.estado == EstadoFabricacion.CERRADA
    assert entity.sincronizacion == EstadoSincronizacion.SINCRONIZADO
    assert entity.sync_attempts == 1
    assert entity.closed_at is not None


@pytest.mark.anyio
async def test_cerrar_marca_no_sincronizada_si_inventario_falla_por_http(make_service):
    entity = make_fabricacion(
        estado=EstadoFabricacion.EN_PROCESO,
        formula_snapshot=FORMULA,
    )
    service, repository, _, inventario = make_service(entity)
    inventario.descontar.side_effect = httpx.ConnectError("inventory unavailable")

    result = await service.cerrar(entity.id)

    assert result is entity
    assert repository.save.call_count == 2
    assert entity.estado == EstadoFabricacion.EN_PROCESO
    assert entity.sincronizacion == EstadoSincronizacion.NO_SINCRONIZADO
    assert entity.sync_attempts == 1
    assert entity.closed_at is None


@pytest.mark.anyio
async def test_cerrar_propaga_errores_no_http(make_service):
    entity = make_fabricacion(estado=EstadoFabricacion.EN_PROCESO)
    service, repository, _, inventario = make_service(entity)
    inventario.descontar.side_effect = RuntimeError("unexpected failure")

    with pytest.raises(RuntimeError, match="unexpected failure"):
        await service.cerrar(entity.id)

    assert repository.save.call_count == 1
    assert entity.estado == EstadoFabricacion.EN_PROCESO
    assert entity.sync_attempts == 1


@pytest.mark.anyio
async def test_cerrar_rechaza_fabricacion_fuera_de_proceso(make_service):
    entity = make_fabricacion()
    service, repository, _, inventario = make_service(entity)

    with pytest.raises(DomainError, match="Solo se pueden cerrar"):
        await service.cerrar(entity.id)

    inventario.descontar.assert_not_awaited()
    repository.save.assert_not_called()


@pytest.mark.anyio
async def test_sincronizar_cierra_orden_no_sincronizada(make_service):
    entity = make_fabricacion(
        estado=EstadoFabricacion.EN_PROCESO,
        sincronizacion=EstadoSincronizacion.NO_SINCRONIZADO,
        formula_snapshot=FORMULA,
    )
    service, repository, _, inventario = make_service(entity)

    result = await service.sincronizar(entity.id)

    assert result is entity
    inventario.descontar.assert_awaited_once_with(
        str(entity.id), "MAT-1", FORMULA, 3
    )
    assert entity.estado == EstadoFabricacion.CERRADA
    assert entity.sincronizacion == EstadoSincronizacion.SINCRONIZADO
    assert entity.closed_at is not None
    repository.save.assert_called_once_with(entity)


@pytest.mark.anyio
async def test_sincronizar_rechaza_orden_que_no_necesita_sincronizacion(make_service):
    entity = make_fabricacion()
    service, repository, _, inventario = make_service(entity)

    with pytest.raises(DomainError, match="no requiere sincronización"):
        await service.sincronizar(entity.id)

    inventario.descontar.assert_not_awaited()
    repository.save.assert_not_called()


@pytest.mark.anyio
async def test_sincronizar_propaga_fallo_de_inventario_y_conserva_estado(make_service):
    entity = make_fabricacion(
        estado=EstadoFabricacion.EN_PROCESO,
        sincronizacion=EstadoSincronizacion.NO_SINCRONIZADO,
        formula_snapshot=FORMULA,
    )
    service, repository, _, inventario = make_service(entity)
    inventario.descontar.side_effect = httpx.ConnectError("inventory unavailable")

    with pytest.raises(httpx.ConnectError, match="inventory unavailable"):
        await service.sincronizar(entity.id)

    assert entity.estado == EstadoFabricacion.EN_PROCESO
    assert entity.sincronizacion == EstadoSincronizacion.NO_SINCRONIZADO
    repository.save.assert_not_called()


def test_obtener_devuelve_entidad_existente(make_service):
    entity = make_fabricacion()
    service, repository, _, _ = make_service(entity)

    assert service.obtener(entity.id) is entity
    repository.get.assert_called_once_with(entity.id)


def test_obtener_falla_si_no_existe_la_fabricacion(make_service):
    service, _, _, _ = make_service()

    with pytest.raises(DomainError, match="Fabricación no encontrada") as error:
        service.obtener(uuid4())

    assert error.value.status_code == 404


def test_listar_calcula_offset_de_pagina_y_devuelve_resultados(make_service):
    first = make_fabricacion()
    second = make_fabricacion(estado=EstadoFabricacion.VALIDADA)
    service, repository, _, _ = make_service()
    repository.list.return_value = [first, second]

    result = service.listar(page=3, estado="Validada")

    assert result == [first, second]
    repository.list.assert_called_once_with(40, 20, "Validada")
