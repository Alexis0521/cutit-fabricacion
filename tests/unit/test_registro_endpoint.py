"""POST /fabricaciones de punta a punta: ruta + servicio + repositorio (SQLite), Materiales simulado."""

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.services import fabricacion_service as service_module
from app.core.security import current_user
from app.infrastructure.database.connection import Base, get_db
from app.infrastructure.database.models import FabricacionModel
from app.main import app

PAYLOAD = {
    "tipoProducto": "Cadena",
    "referenciaProducto": "CAD-3/8-050",
    "cantidad": 20,
    "especificaciones": {"paso": "3/8", "calibre": "0.050"},
    "insumosTerceros": [{"tipo": "Motosierra", "cantidad": 20}],
    "observaciones": "texto",
}


class MaterialesSimulado:
    resultado: object = {"id": "CAD-3/8-050", "formula": {"estado": "APROBADA", "version": "1"}}

    async def obtener_material(self, referencia: str):
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


def http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://materials/materiales/X")
    return httpx.HTTPStatusError(
        "error", request=request, response=httpx.Response(status, request=request)
    )


@pytest.fixture
def entorno(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    materiales = MaterialesSimulado()
    materiales.resultado = {"id": "CAD-3/8-050", "formula": {"estado": "APROBADA", "version": "1"}}

    def get_db_test():
        with session_factory() as db:
            yield db

    monkeypatch.setattr(service_module, "MaterialesClient", lambda: materiales)
    anterior = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = get_db_test
    app.dependency_overrides[current_user] = lambda: {"role": "FABRICANTE"}

    yield TestClient(app), materiales, session_factory

    app.dependency_overrides.clear()
    app.dependency_overrides.update(anterior)
    engine.dispose()


def test_registro_exitoso_devuelve_201_y_persiste_la_orden(entorno):
    client, _, session_factory = entorno

    response = client.post("/fabricaciones", json=PAYLOAD)

    assert response.status_code == 201
    assert response.json() == {
        "mensaje": "Orden de fabricación registrada correctamente",
        "id": "ORD-000001",
        "estado": "Registrada",
    }
    with session_factory() as db:
        orden = db.get(FabricacionModel, "ORD-000001")
        assert orden is not None
        assert orden.especificaciones == PAYLOAD["especificaciones"]
        assert orden.insumos_terceros == PAYLOAD["insumosTerceros"]
        assert orden.observaciones == "texto"
        assert orden.created_at is not None


def test_los_identificadores_son_consecutivos_y_no_cambian(entorno):
    client, _, _ = entorno

    ids = [client.post("/fabricaciones", json=PAYLOAD).json()["id"] for _ in range(3)]
    assert ids == ["ORD-000001", "ORD-000002", "ORD-000003"]

    detalle = client.get("/fabricaciones/ORD-000002", headers={})
    assert detalle.status_code == 200
    assert detalle.json()["id"] == "ORD-000002"
    assert detalle.json()["estado"] == "Registrada"


def test_una_orden_rechazada_no_consume_identificador(entorno):
    client, _, _ = entorno

    assert client.post("/fabricaciones", json={**PAYLOAD, "cantidad": 0}).status_code == 422
    assert client.post("/fabricaciones", json=PAYLOAD).json()["id"] == "ORD-000001"


@pytest.mark.parametrize(
    ("cambios", "mensaje"),
    [
        ({"tipoProducto": "Motosierra"}, "El tipo de producto no es válido"),
        ({"cantidad": 0}, "La cantidad debe ser un número entero mayor que cero"),
        ({"cantidad": 2.5}, "La cantidad debe ser un número entero mayor que cero"),
        ({"especificaciones": {}}, "Faltan las especificaciones técnicas"),
        ({"observaciones": "x" * 251}, "Las observaciones no pueden superar 250 caracteres"),
    ],
)
def test_datos_invalidos_devuelven_422_y_no_crean_orden(entorno, cambios, mensaje):
    client, _, session_factory = entorno

    response = client.post("/fabricaciones", json={**PAYLOAD, **cambios})

    assert response.status_code == 422
    assert response.json() == {"detail": mensaje}
    with session_factory() as db:
        assert db.query(FabricacionModel).count() == 0


def test_datos_faltantes_indican_cual_falta(entorno):
    client, _, _ = entorno

    response = client.post("/fabricaciones", json={"tipoProducto": "Cadena"})

    assert response.status_code == 422
    cuerpo = response.json()
    assert cuerpo["detail"] == "Faltan datos obligatorios"
    assert [f["campo"] for f in cuerpo["faltantes"]] == [
        "referenciaProducto",
        "cantidad",
        "especificaciones",
    ]


def test_cuerpo_vacio_devuelve_422_con_todos_los_faltantes(entorno):
    client, _, _ = entorno

    response = client.post("/fabricaciones", json={})

    assert response.status_code == 422
    assert len(response.json()["faltantes"]) == 4


def test_referencia_inexistente_devuelve_422(entorno):
    client, materiales, _ = entorno
    materiales.resultado = http_error(404)

    response = client.post("/fabricaciones", json=PAYLOAD)

    assert response.status_code == 422
    assert response.json() == {"detail": "La referencia de producto no es válida"}


@pytest.mark.parametrize(
    ("estado", "mensaje"),
    [
        ("BORRADOR", "La fórmula de la referencia aún no está aprobada"),
        ("EVALUANDO_PATENTE", "La fórmula de la referencia aún no está aprobada"),
        (
            "RECHAZADA_POR_INFRACCION",
            "La fórmula de la referencia fue rechazada por infracción de patente y no puede fabricarse",
        ),
    ],
)
def test_formula_no_aprobada_devuelve_409(entorno, estado, mensaje):
    client, materiales, session_factory = entorno
    materiales.resultado = {"id": "CAD-3/8-050", "formula": {"estado": estado}}

    response = client.post("/fabricaciones", json=PAYLOAD)

    assert response.status_code == 409
    assert response.json() == {"detail": mensaje}
    with session_factory() as db:
        assert db.query(FabricacionModel).count() == 0


@pytest.mark.parametrize(
    "falla", [httpx.ConnectError("caído"), httpx.ReadTimeout("lento"), http_error(502)]
)
def test_materiales_no_disponible_devuelve_503(entorno, falla):
    client, materiales, _ = entorno
    materiales.resultado = falla

    response = client.post("/fabricaciones", json=PAYLOAD)

    assert response.status_code == 503
    assert response.json() == {"detail": "El módulo de Materiales no está disponible por el momento"}


def test_error_inesperado_devuelve_500(entorno):
    client, materiales, _ = entorno
    materiales.resultado = RuntimeError("fallo inesperado")

    response = client.post("/fabricaciones", json=PAYLOAD)

    assert response.status_code == 500
    assert response.json() == {
        "detail": "La operación no pudo completarse, intente nuevamente más tarde"
    }


def test_rol_sin_permiso_devuelve_403(entorno):
    client, _, _ = entorno
    app.dependency_overrides[current_user] = lambda: {"role": "GERENTE_FABRICACION"}

    response = client.post("/fabricaciones", json=PAYLOAD)

    assert response.status_code == 403
    assert response.json() == {"detail": "No tiene autorización para realizar esta operación"}


def test_sin_credenciales_devuelve_401(entorno):
    client, _, _ = entorno
    del app.dependency_overrides[current_user]

    response = client.post("/fabricaciones", json=PAYLOAD)

    assert response.status_code == 401
    assert response.json() == {"detail": "Acceso no autorizado"}
