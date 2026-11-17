from datetime import datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_fabricacion_service
from app.application.services.fabricacion_service import FabricacionService
from app.core.exceptions import DomainError
from app.core.security import current_user
from app.domain.entities.fabricacion import Fabricacion
from app.domain.enums.estados import (
    EstadoFabricacion,
    EstadoSincronizacion,
    TipoProducto,
)
from app.main import app


@pytest.fixture
def api_client():
    previous_overrides = app.dependency_overrides.copy()
    service = Mock(spec=FabricacionService)
    app.dependency_overrides[get_fabricacion_service] = lambda: service
    app.dependency_overrides[current_user] = lambda: {"role": "GERENTE_FABRICACION"}

    yield TestClient(app), service

    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def make_fabricacion(
    estado: EstadoFabricacion = EstadoFabricacion.REGISTRADA,
    sincronizacion: EstadoSincronizacion = EstadoSincronizacion.PENDIENTE,
    formula_snapshot: dict | None = None,
) -> Fabricacion:
    return Fabricacion(
        referencia_material="MAT-1",
        tipo_producto=TipoProducto.CADENA,
        cantidad=3,
        observaciones="Orden urgente",
        id=uuid4(),
        estado=estado,
        sincronizacion=sincronizacion,
        formula_version="2" if formula_snapshot else None,
        formula_snapshot=formula_snapshot,
    )


def fabricacion_json(entity: Fabricacion) -> dict:
    def serialize_datetime(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    return {
        "id": str(entity.id),
        "referencia_material": entity.referencia_material,
        "tipo_producto": entity.tipo_producto.value,
        "cantidad": entity.cantidad,
        "observaciones": entity.observaciones,
        "estado": entity.estado.value,
        "sincronizacion": entity.sincronizacion.value,
        "formula_version": entity.formula_version,
        "created_at": serialize_datetime(entity.created_at),
        "started_at": serialize_datetime(entity.started_at) if entity.started_at else None,
        "closed_at": serialize_datetime(entity.closed_at) if entity.closed_at else None,
        "sync_attempts": entity.sync_attempts,
    }


def test_registrar_returns_created_fabricacion(api_client):
    client, service = api_client
    entity = make_fabricacion()
    service.registrar.return_value = entity
    payload = {
        "referencia_material": "MAT-1",
        "tipo_producto": "Cadena",
        "cantidad": 3,
        "observaciones": "Orden urgente",
    }

    response = client.post("/fabricaciones", json=payload)

    assert response.status_code == 201
    assert response.json() == fabricacion_json(entity)
    service.registrar.assert_awaited_once()
    assert service.registrar.await_args.args[0].model_dump() == {
        **payload,
        "tipo_producto": TipoProducto.CADENA,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"referencia_material": "MAT-1", "tipo_producto": "Cadena", "cantidad": 0},
        {"referencia_material": "MAT-1", "tipo_producto": "No existe", "cantidad": 1},
        {"tipo_producto": "Cadena", "cantidad": 1},
    ],
)
def test_registrar_rejects_invalid_payload(api_client, payload):
    client, service = api_client

    response = client.post("/fabricaciones", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]
    service.registrar.assert_not_awaited()


def test_registrar_maps_service_domain_error(api_client):
    client, service = api_client
    service.registrar.side_effect = DomainError("Fórmula no aprobada", 409)

    response = client.post(
        "/fabricaciones",
        json={"referencia_material": "MAT-1", "tipo_producto": "Cadena", "cantidad": 1},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Fórmula no aprobada"}


def test_validar_returns_available_result(api_client):
    client, service = api_client
    entity = make_fabricacion(estado=EstadoFabricacion.VALIDADA)
    service.validar.return_value = (entity, [])

    response = client.post(f"/fabricaciones/{entity.id}/validacion")

    assert response.status_code == 200
    assert response.json() == {"disponible": True, "faltantes": []}
    service.validar.assert_awaited_once_with(entity.id)


def test_validar_returns_missing_inventory_items(api_client):
    client, service = api_client
    entity = make_fabricacion()
    missing = {
        "codigo": "ACERO",
        "descripcion": "Acero",
        "requerido": 10.0,
        "disponible": 7.0,
        "diferencia": 3.0,
    }
    service.validar.return_value = (entity, [missing])

    response = client.post(f"/fabricaciones/{entity.id}/validacion")

    assert response.status_code == 200
    assert response.json() == {"disponible": False, "faltantes": [missing]}


def test_validar_maps_missing_fabricacion_to_404(api_client):
    client, service = api_client
    fabricacion_id = uuid4()
    service.validar.side_effect = DomainError("Fabricación no encontrada", 404)

    response = client.post(f"/fabricaciones/{fabricacion_id}/validacion")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fabricación no encontrada"}


def test_iniciar_returns_updated_fabricacion(api_client):
    client, service = api_client
    entity = make_fabricacion(
        estado=EstadoFabricacion.EN_PROCESO,
        formula_snapshot={"version": "2", "items": [{"codigo": "ACERO"}]},
    )
    service.iniciar.return_value = entity

    response = client.patch(f"/fabricaciones/{entity.id}/inicio")

    assert response.status_code == 200
    assert response.json() == fabricacion_json(entity)
    service.iniciar.assert_awaited_once_with(entity.id)


def test_iniciar_returns_service_conflict(api_client):
    client, service = api_client
    entity_id = uuid4()
    service.iniciar.side_effect = DomainError("Solo se pueden iniciar órdenes Validadas", 409)

    response = client.patch(f"/fabricaciones/{entity_id}/inicio")

    assert response.status_code == 409
    assert response.json() == {"detail": "Solo se pueden iniciar órdenes Validadas"}


def test_formula_returns_formula_snapshot(api_client):
    client, service = api_client
    entity_id = uuid4()
    formula = {"version": "2", "items": [{"codigo": "ACERO", "cantidad": 10}]}
    service.formula.return_value = formula

    response = client.get(f"/fabricaciones/{entity_id}/formula")

    assert response.status_code == 200
    assert response.json() == formula
    service.formula.assert_awaited_once_with(entity_id)


def test_formula_returns_service_conflict_for_unavailable_formula(api_client):
    client, service = api_client
    entity_id = uuid4()
    service.formula.side_effect = DomainError("La fórmula está incompleta", 409)

    response = client.get(f"/fabricaciones/{entity_id}/formula")

    assert response.status_code == 409
    assert response.json() == {"detail": "La fórmula está incompleta"}


def test_cerrar_returns_closed_fabricacion(api_client):
    client, service = api_client
    entity = make_fabricacion(
        estado=EstadoFabricacion.CERRADA,
        sincronizacion=EstadoSincronizacion.SINCRONIZADO,
        formula_snapshot={"version": "2", "items": [{"codigo": "ACERO"}]},
    )
    service.cerrar.return_value = entity

    response = client.post(f"/fabricaciones/{entity.id}/cierre")

    assert response.status_code == 200
    assert response.json() == fabricacion_json(entity)
    service.cerrar.assert_awaited_once_with(entity.id)


def test_cerrar_returns_service_conflict(api_client):
    client, service = api_client
    entity_id = uuid4()
    service.cerrar.side_effect = DomainError("Solo se pueden cerrar órdenes En Proceso", 409)

    response = client.post(f"/fabricaciones/{entity_id}/cierre")

    assert response.status_code == 409
    assert response.json() == {"detail": "Solo se pueden cerrar órdenes En Proceso"}


def test_sincronizar_returns_synchronized_fabricacion(api_client):
    client, service = api_client
    entity = make_fabricacion(
        estado=EstadoFabricacion.CERRADA,
        sincronizacion=EstadoSincronizacion.SINCRONIZADO,
        formula_snapshot={"version": "2", "items": [{"codigo": "ACERO"}]},
    )
    service.sincronizar.return_value = entity

    response = client.post(f"/fabricaciones/{entity.id}/sincronizacion")

    assert response.status_code == 200
    assert response.json() == fabricacion_json(entity)
    service.sincronizar.assert_awaited_once_with(entity.id)


def test_sincronizar_returns_not_found_for_missing_fabricacion(api_client):
    client, service = api_client
    entity_id = uuid4()
    service.sincronizar.side_effect = DomainError("Fabricación no encontrada", 404)

    response = client.post(f"/fabricaciones/{entity_id}/sincronizacion")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fabricación no encontrada"}


def test_listar_returns_items_and_passes_filters(api_client):
    client, service = api_client
    entities = [make_fabricacion(), make_fabricacion(estado=EstadoFabricacion.VALIDADA)]
    service.listar.return_value = entities

    response = client.get("/fabricaciones?page=2&estado=Validada&modo=urgencia")

    assert response.status_code == 200
    assert response.json() == [fabricacion_json(entity) for entity in entities]
    service.listar.assert_called_once_with(2, "Validada")


def test_listar_rejects_page_less_than_one(api_client):
    client, service = api_client

    response = client.get("/fabricaciones?page=0")

    assert response.status_code == 422
    service.listar.assert_not_called()


def test_listar_maps_service_domain_error(api_client):
    client, service = api_client
    service.listar.side_effect = DomainError("Filtro inválido", 400)

    response = client.get("/fabricaciones")

    assert response.status_code == 400
    assert response.json() == {"detail": "Filtro inválido"}


def test_detalle_returns_fabricacion(api_client):
    client, service = api_client
    entity = make_fabricacion()
    service.obtener.return_value = entity

    response = client.get(f"/fabricaciones/{entity.id}")

    assert response.status_code == 200
    assert response.json() == fabricacion_json(entity)
    service.obtener.assert_called_once_with(entity.id)


def test_detalle_returns_not_found_for_missing_fabricacion(api_client):
    client, service = api_client
    entity_id = uuid4()
    service.obtener.side_effect = DomainError("Fabricación no encontrada", 404)

    response = client.get(f"/fabricaciones/{entity_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fabricación no encontrada"}


def test_endpoints_reject_invalid_fabricacion_id(api_client):
    client, service = api_client

    response = client.get("/fabricaciones/no-es-un-uuid")

    assert response.status_code == 422
    service.obtener.assert_not_called()


def test_endpoint_enforces_role_permissions(api_client):
    client, service = api_client
    app.dependency_overrides[current_user] = lambda: {"role": "FABRICANTE"}

    response = client.post(f"/fabricaciones/{uuid4()}/sincronizacion")

    assert response.status_code == 403
    assert response.json() == {"detail": "Permisos insuficientes"}
    service.sincronizar.assert_not_awaited()
