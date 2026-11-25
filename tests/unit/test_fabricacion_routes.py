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
    fabricante_id: str | None = None,
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
        fabricante_id=fabricante_id,
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


def test_registrar_assigns_order_to_authenticated_manufacturer(api_client):
    client, service = api_client
    service.registrar.return_value = make_fabricacion(fabricante_id="fab-1")
    app.dependency_overrides[current_user] = lambda: {
        "role": "FABRICANTE",
        "sub": "fab-1",
    }

    response = client.post(
        "/fabricaciones",
        json={
            "referencia_material": "MAT-1",
            "tipo_producto": "Cadena",
            "cantidad": 3,
            "fabricante_id": "fab-otro",
        },
    )

    assert response.status_code == 201
    assert service.registrar.await_args.args[0].model_dump().get(
        "fabricante_id"
    ) is None
    assert service.registrar.await_args.kwargs["fabricante_id"] == "fab-1"


def test_gerente_cannot_assign_unverified_manufacturer_when_registering(api_client):
    client, service = api_client
    service.registrar.return_value = make_fabricacion()

    response = client.post(
        "/fabricaciones",
        json={
            "referencia_material": "MAT-1",
            "tipo_producto": "Cadena",
            "cantidad": 3,
            "fabricante_id": "fab-1",
        },
    )

    assert response.status_code == 201
    assert service.registrar.await_args.args[0].model_dump().get(
        "fabricante_id"
    ) is None
    assert service.registrar.await_args.kwargs["fabricante_id"] is None


def test_manufacturer_without_subject_cannot_register_order(api_client):
    client, service = api_client
    app.dependency_overrides[current_user] = lambda: {
        "role": "FABRICANTE"
    }

    response = client.post(
        "/fabricaciones",
        json={
            "referencia_material": "MAT-1",
            "tipo_producto": "Cadena",
            "cantidad": 3,
        },
    )

    assert response.status_code == 403
    service.registrar.assert_not_awaited()


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

    entity = make_fabricacion(
        estado=EstadoFabricacion.VALIDADA
    )

    service.validar.return_value = (entity, [])

    response = client.post(
        f"/fabricaciones/{entity.id}/validacion"
    )

    assert response.status_code == 200

    assert response.json() == {
        "mensaje": "Materiales disponibles: la orden puede iniciar su fabricación",
        "id": str(entity.id),
        "estado": "Validada",
    }

    service.validar.assert_awaited_once_with(entity.id)


def test_validar_returns_missing_inventory_items(api_client):
    client, service = api_client

    entity = make_fabricacion()

    missing = {
        "codigoMaterial": "MP-001",
        "requerido": 5000,
        "disponible": 3200,
        "faltante": 1800,
    }

    service.validar.return_value = (entity, [missing])

    response = client.post(
        f"/fabricaciones/{entity.id}/validacion"
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Materiales insuficientes para fabricar la orden",
        "faltantes": [missing],
    }


def test_validar_rechaza_estado_incorrecto(api_client):
    client, service = api_client

    service.validar.side_effect = DomainError(
        "Solo se pueden validar órdenes en estado Registrada",
        409,
    )

    response = client.post(
        f"/fabricaciones/{uuid4()}/validacion"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Solo se pueden validar órdenes en estado Registrada"
    }


@pytest.mark.parametrize(
    "modulo",
    ["Materiales", "Inventario"],
)
def test_validar_modulo_no_disponible(api_client, modulo):
    client, service = api_client

    mensaje = (
        f"El módulo de {modulo} no está disponible por el momento"
    )

    service.validar.side_effect = DomainError(mensaje, 503)

    response = client.post(
        f"/fabricaciones/{uuid4()}/validacion"
    )

    assert response.status_code == 503
    assert response.json() == {"detail": mensaje}


def test_validar_error_inesperado(api_client):
    client, service = api_client

    service.validar.side_effect = RuntimeError(
        "Error inesperado"
    )

    response = client.post(
        f"/fabricaciones/{uuid4()}/validacion"
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail": "La operación no pudo completarse, intente nuevamente más tarde"
    }


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
    assert response.json() == {
        **fabricacion_json(entity),
        "mensaje": "La orden quedó en producción",
    }
    service.iniciar.assert_awaited_once_with(
        entity.id,
        {"role": "GERENTE_FABRICACION"},
    )


def test_iniciar_returns_service_conflict(api_client):
    client, service = api_client
    entity_id = uuid4()
    service.iniciar.side_effect = DomainError("Solo se pueden iniciar órdenes Validadas", 409)

    response = client.patch(f"/fabricaciones/{entity_id}/inicio")

    assert response.status_code == 409
    assert response.json() == {"detail": "Solo se pueden iniciar órdenes Validadas"}


def test_iniciar_maps_missing_order_to_404(api_client):
    client, service = api_client
    service.iniciar.side_effect = DomainError("Fabricación no encontrada", 404)

    response = client.patch(f"/fabricaciones/{uuid4()}/inicio")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fabricación no encontrada"}


def test_iniciar_maps_materiales_unavailable_to_503(api_client):
    client, service = api_client
    service.iniciar.side_effect = DomainError(
        "El módulo de Materiales no está disponible por el momento",
        503,
    )

    response = client.patch(f"/fabricaciones/{uuid4()}/inicio")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "El módulo de Materiales no está disponible por el momento"
    }


def test_iniciar_maps_unexpected_error_to_500(api_client):
    client, service = api_client
    service.iniciar.side_effect = RuntimeError("Error interno")

    response = client.patch(f"/fabricaciones/{uuid4()}/inicio")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "La operación no pudo completarse, intente nuevamente más tarde"
    }


def test_iniciar_rechaza_fabricante_no_asignado(api_client):
    client, service = api_client
    entity_id = uuid4()
    app.dependency_overrides[current_user] = lambda: {
        "role": "FABRICANTE",
        "sub": "fab-2",
    }
    service.iniciar.side_effect = DomainError(
        "Solo el fabricante asignado puede iniciar esta orden",
        403,
    )

    response = client.patch(f"/fabricaciones/{entity_id}/inicio")

    assert response.status_code == 403
    service.iniciar.assert_awaited_once_with(
        entity_id,
        {"role": "FABRICANTE", "sub": "fab-2"},
    )


def test_formula_returns_current_formula(api_client):
    client, service = api_client

    app.dependency_overrides[current_user] = lambda: {
        "role": "FABRICANTE"
    }

    entity_id = uuid4()

    formula = {
        "referenciaProducto": "MAT-1",
        "insumos": [
            {
                "codigoMaterial": "MP-001",
                "descripcion": "Acero",
                "cantidadPorUnidad": 250.5,
                "unidadMedida": "g",
            }
        ],
    }

    service.formula.return_value = formula

    response = client.get(f"/fabricaciones/{entity_id}/formula")

    assert response.status_code == 200
    assert response.json() == formula
    service.formula.assert_awaited_once_with(entity_id)


def test_formula_returns_service_conflict_for_unavailable_formula(api_client):
    client, service = api_client
    app.dependency_overrides[current_user] = lambda: {
    "role": "FABRICANTE"
    }
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
    assert response.json() == {
        "detail": "No tiene autorización para realizar esta operación"
    }
    service.sincronizar.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "endpoint"),
    [
        ("GET", "formula"),
        ("POST", "validacion"),
        ("PATCH", "inicio"),
    ],
)
def test_hu03_hu04_rechazan_acceso_sin_credenciales(
    api_client, method, endpoint
):
    client, service = api_client

    app.dependency_overrides.pop(current_user, None)

    response = client.request(
        method,
        f"/fabricaciones/{uuid4()}/{endpoint}",
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Acceso no autorizado"
    }

    service.formula.assert_not_awaited()
    service.validar.assert_not_awaited()
    service.iniciar.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "endpoint"),
    [
        ("GET", "formula"),
        ("POST", "validacion"),
        ("PATCH", "inicio"),
    ],
)
def test_hu03_hu04_rechazan_token_invalido(
    api_client, method, endpoint
):
    client, service = api_client

    app.dependency_overrides.pop(current_user, None)

    response = client.request(
        method,
        f"/fabricaciones/{uuid4()}/{endpoint}",
        headers={"Authorization": "Bearer token-invalido"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Acceso no autorizado"
    }

    service.formula.assert_not_awaited()
    service.validar.assert_not_awaited()
    service.iniciar.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "endpoint"),
    [
        ("GET", "formula"),
        ("POST", "validacion"),
        ("PATCH", "inicio"),
    ],
)
def test_hu03_hu04_rechazan_rol_no_autorizado(
    api_client, method, endpoint
):
    client, service = api_client

    app.dependency_overrides[current_user] = lambda: {
        "role": "SIN_PERMISOS"
    }

    response = client.request(
        method,
        f"/fabricaciones/{uuid4()}/{endpoint}",
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "No tiene autorización para realizar esta operación"
    }

    service.formula.assert_not_awaited()
    service.validar.assert_not_awaited()
    service.iniciar.assert_not_awaited()