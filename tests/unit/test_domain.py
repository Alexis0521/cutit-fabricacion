import pytest

from app.core.exceptions import DomainError
from app.domain.entities.fabricacion import Fabricacion
from app.domain.enums.estados import (
    EstadoFabricacion,
    EstadoSincronizacion,
    TipoProducto,
)


def make_order():
    return Fabricacion("MAT-1", TipoProducto.CADENA, 2)


def test_quantity_must_be_positive():
    with pytest.raises(DomainError):
        Fabricacion("MAT-1", TipoProducto.CADENA, 0)


def test_observations_max_length():
    with pytest.raises(DomainError):
        Fabricacion("MAT-1", TipoProducto.CADENA, 1, "x" * 251)


def test_valid_transition():
    order = make_order()
    order.validar()
    assert order.estado == EstadoFabricacion.VALIDADA


def test_cannot_validate_twice():
    order = make_order()
    order.validar()
    with pytest.raises(DomainError):
        order.validar()


def test_start_captures_formula_version():
    order = make_order()
    order.validar()
    order.iniciar({"estado": "APROBADA", "version": "2", "items": [{"codigo": "A"}]})
    assert order.estado == EstadoFabricacion.EN_PROCESO
    assert order.formula_version == "2"
    assert order.formula_snapshot["version"] == "2"


def test_start_requires_approved_formula():
    order = make_order()
    order.validar()
    with pytest.raises(DomainError):
        order.iniciar({"estado": "BORRADOR", "version": "2"})


def test_start_requires_formula_version():
    order = make_order()
    order.validar()
    with pytest.raises(DomainError):
        order.iniciar({"estado": "APROBADA"})


def test_close_and_sync_state():
    order = make_order()
    order.validar()
    order.iniciar({"estado": "APROBADA", "version": "1", "items": []})
    order.cerrar()
    order.marcar_no_sincronizada()
    assert order.estado == EstadoFabricacion.EN_PROCESO
    assert order.sincronizacion == EstadoSincronizacion.NO_SINCRONIZADO
    order.marcar_cerrada()
    assert order.estado == EstadoFabricacion.CERRADA
    assert order.sincronizacion == EstadoSincronizacion.SINCRONIZADO
