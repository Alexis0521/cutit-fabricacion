from app.application.schemas.fabricacion_schema import FabricacionCreate


def test_acepta_los_nombres_del_contrato_json():
    payload = FabricacionCreate.model_validate(
        {
            "tipoProducto": "Cadena",
            "referenciaProducto": "CAD-3/8-050",
            "cantidad": 20,
            "especificaciones": {"paso": "3/8"},
            "insumosTerceros": [{"tipo": "Motosierra", "cantidad": 20}],
            "observaciones": "texto",
        }
    )
    assert payload.tipo_producto == "Cadena"
    assert payload.referencia_material == "CAD-3/8-050"
    assert payload.insumos_terceros == [{"tipo": "Motosierra", "cantidad": 20}]


def test_acepta_los_nombres_internos_y_campos_opcionales_vacios():
    payload = FabricacionCreate(referencia_material="MAT-1", tipo_producto="Cadena", cantidad=1)
    assert payload.referencia_material == "MAT-1"
    assert payload.especificaciones is None
    assert payload.insumos_terceros is None
    assert payload.observaciones is None
