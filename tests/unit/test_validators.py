import pytest

from app.core.exceptions import DomainError
from app.domain.enums.estados import TipoProducto
from app.domain.validators import validar_datos_registro, validar_formula_aprobada

VALIDO = {
    "tipo": "Cadena",
    "referencia": "CAD-3/8-050",
    "cantidad": 20,
    "especificaciones": {"paso": "3/8", "calibre": "0.050"},
    "insumos_terceros": [{"tipo": "Motosierra", "cantidad": 20}],
    "observaciones": "texto",
}


def validar(**cambios):
    return validar_datos_registro(**{**VALIDO, **cambios})


def error_de(**cambios) -> DomainError:
    with pytest.raises(DomainError) as error:
        validar(**cambios)
    return error.value


def test_datos_validos_devuelve_los_datos_normalizados():
    datos = validar(referencia="  CAD-3/8-050 ")
    assert datos.tipo_producto == TipoProducto.CADENA
    assert datos.referencia_material == "CAD-3/8-050"
    assert datos.cantidad == 20
    assert datos.especificaciones == {"paso": "3/8", "calibre": "0.050"}
    assert datos.insumos_terceros == [{"tipo": "Motosierra", "cantidad": 20}]


def test_cuchilla_es_un_tipo_valido():
    assert validar(tipo="Cuchilla").tipo_producto == TipoProducto.CUCHILLA


@pytest.mark.parametrize("tipo", ["cadena", "Motosierra", 1, ["Cadena"]])
def test_tipo_invalido_devuelve_422(tipo):
    error = error_de(tipo=tipo)
    assert (error.status_code, error.message) == (422, "El tipo de producto no es válido")


def test_referencia_que_no_es_texto_devuelve_422():
    error = error_de(referencia=123)
    assert (error.status_code, error.message) == (422, "La referencia de producto no es válida")


@pytest.mark.parametrize("cantidad", [0, -1, 1.5, 20.0, "20", True])
def test_cantidad_invalida_devuelve_422(cantidad):
    error = error_de(cantidad=cantidad)
    assert (error.status_code, error.message) == (
        422,
        "La cantidad debe ser un número entero mayor que cero",
    )


@pytest.mark.parametrize(
    "especificaciones", [{}, {"paso": ""}, {"paso": None, "calibre": "  "}, ["paso"], "paso"]
)
def test_especificaciones_sin_atributos_devuelve_422(especificaciones):
    error = error_de(especificaciones=especificaciones)
    assert (error.status_code, error.message) == (422, "Faltan las especificaciones técnicas")


def test_especificaciones_descarta_atributos_vacios():
    assert validar(especificaciones={"paso": "3/8", "calibre": ""}).especificaciones == {
        "paso": "3/8"
    }


def test_observaciones_de_250_caracteres_son_validas():
    assert len(validar(observaciones="x" * 250).observaciones) == 250


def test_observaciones_de_mas_de_250_caracteres_devuelve_422():
    error = error_de(observaciones="x" * 251)
    assert (error.status_code, error.message) == (
        422,
        "Las observaciones no pueden superar 250 caracteres",
    )


def test_observaciones_que_no_son_texto_devuelve_422():
    error = error_de(observaciones=42)
    assert (error.status_code, error.message) == (422, "Las observaciones deben ser texto")


def test_observaciones_opcionales():
    assert validar(observaciones=None).observaciones is None


@pytest.mark.parametrize("insumos", [None, []])
def test_insumos_de_terceros_son_opcionales(insumos):
    assert validar(insumos_terceros=insumos).insumos_terceros == []


@pytest.mark.parametrize(
    "insumos",
    [
        "Motosierra",
        ["Motosierra"],
        [{"tipo": "Motosierra"}],
        [{"cantidad": 2}],
        [{"tipo": "", "cantidad": 2}],
        [{"tipo": 5, "cantidad": 2}],
        [{"tipo": "Kit", "cantidad": 0}],
        [{"tipo": "Kit", "cantidad": 1.5}],
    ],
)
def test_insumos_de_terceros_invalidos_devuelve_422(insumos):
    error = error_de(insumos_terceros=insumos)
    assert (error.status_code, error.message) == (422, "Los insumos de terceros no son válidos")


def test_faltantes_indican_cada_dato_que_falta():
    error = error_de(tipo=None, referencia="  ", cantidad=None, especificaciones=None)
    assert (error.status_code, error.message) == (422, "Faltan datos obligatorios")
    assert [f["campo"] for f in error.extra["faltantes"]] == [
        "tipoProducto",
        "referenciaProducto",
        "cantidad",
        "especificaciones",
    ]
    assert all(f["mensaje"] for f in error.extra["faltantes"])


def test_faltantes_solo_lista_los_que_faltan():
    error = error_de(cantidad=None)
    assert error.extra["faltantes"] == [
        {"campo": "cantidad", "mensaje": "El campo cantidad es obligatorio"}
    ]


def test_sin_exigir_especificaciones_acepta_su_ausencia():
    datos = validar(especificaciones=None, exigir_especificaciones=False)
    assert datos.especificaciones == {}


def test_formula_aprobada_es_valida():
    validar_formula_aprobada("APROBADA")


@pytest.mark.parametrize("estado", ["BORRADOR", "EVALUANDO_PATENTE", "otro", None])
def test_formula_pendiente_devuelve_409(estado):
    with pytest.raises(DomainError) as error:
        validar_formula_aprobada(estado)
    assert (error.value.status_code, error.value.message) == (
        409,
        "La fórmula de la referencia aún no está aprobada",
    )


def test_formula_rechazada_por_infraccion_devuelve_409():
    with pytest.raises(DomainError) as error:
        validar_formula_aprobada("RECHAZADA_POR_INFRACCION")
    assert error.value.status_code == 409
    assert "rechazada por infracción de patente" in error.value.message
