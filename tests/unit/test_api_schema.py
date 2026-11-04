import pytest
from pydantic import ValidationError
from app.application.schemas.fabricacion_schema import FabricacionCreate


def test_valid_payload():
    payload = FabricacionCreate(referencia_material="MAT-1", tipo_producto="Cadena", cantidad=1)
    assert payload.cantidad == 1


def test_invalid_quantity():
    with pytest.raises(ValidationError):
        FabricacionCreate(referencia_material="MAT-1", tipo_producto="Cadena", cantidad=0)


def test_invalid_observations():
    with pytest.raises(ValidationError):
        FabricacionCreate(referencia_material="MAT-1", tipo_producto="Cadena", cantidad=1,
                          observaciones="x" * 251)
