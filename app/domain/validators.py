from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import DomainError
from app.domain.enums.estados import EstadoFormula, TipoProducto

MAX_OBSERVACIONES = 250

MSG_DATOS_OBLIGATORIOS = "Faltan datos obligatorios"
MSG_TIPO_INVALIDO = "El tipo de producto no es válido"
MSG_REFERENCIA_INVALIDA = "La referencia de producto no es válida"
MSG_CANTIDAD_INVALIDA = "La cantidad debe ser un número entero mayor que cero"
MSG_SIN_ESPECIFICACIONES = "Faltan las especificaciones técnicas"
MSG_OBSERVACIONES_LARGAS = "Las observaciones no pueden superar 250 caracteres"
MSG_OBSERVACIONES_TEXTO = "Las observaciones deben ser texto"
MSG_INSUMOS_INVALIDOS = "Los insumos de terceros no son válidos"
MSG_FORMULA_NO_APROBADA = "La fórmula de la referencia aún no está aprobada"
MSG_FORMULA_RECHAZADA = (
    "La fórmula de la referencia fue rechazada por infracción de patente y no puede fabricarse"
)


@dataclass
class DatosOrden:
    tipo_producto: TipoProducto
    referencia_material: str
    cantidad: int
    especificaciones: dict[str, Any]
    insumos_terceros: list[dict[str, Any]] = field(default_factory=list)
    observaciones: str | None = None


def _vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _es_entero_positivo(valor: Any) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


def _faltantes(
    tipo: Any, referencia: Any, cantidad: Any, especificaciones: Any, exigir_especificaciones: bool
) -> list[dict[str, str]]:
    campos = [
        ("tipoProducto", tipo),
        ("referenciaProducto", referencia),
        ("cantidad", cantidad),
    ]
    if exigir_especificaciones:
        campos.append(("especificaciones", especificaciones))
    return [
        {"campo": nombre, "mensaje": f"El campo {nombre} es obligatorio"}
        for nombre, valor in campos
        if _vacio(valor)
    ]


def _validar_especificaciones(especificaciones: Any) -> dict[str, Any]:
    if not isinstance(especificaciones, dict):
        raise DomainError(MSG_SIN_ESPECIFICACIONES, 422)
    atributos = {k: v for k, v in especificaciones.items() if not _vacio(v)}
    if not atributos:
        raise DomainError(MSG_SIN_ESPECIFICACIONES, 422)
    return atributos


def _validar_insumos(insumos: Any) -> list[dict[str, Any]]:
    if insumos is None:
        return []
    if not isinstance(insumos, list):
        raise DomainError(MSG_INSUMOS_INVALIDOS, 422)
    resultado: list[dict[str, Any]] = []
    for insumo in insumos:
        if (
            not isinstance(insumo, dict)
            or _vacio(insumo.get("tipo"))
            or not isinstance(insumo.get("tipo"), str)
            or not _es_entero_positivo(insumo.get("cantidad"))
        ):
            raise DomainError(MSG_INSUMOS_INVALIDOS, 422)
        resultado.append({"tipo": insumo["tipo"].strip(), "cantidad": insumo["cantidad"]})
    return resultado


def _validar_observaciones(observaciones: Any) -> str | None:
    if observaciones is None:
        return None
    if not isinstance(observaciones, str):
        raise DomainError(MSG_OBSERVACIONES_TEXTO, 422)
    if len(observaciones) > MAX_OBSERVACIONES:
        raise DomainError(MSG_OBSERVACIONES_LARGAS, 422)
    return observaciones


def validar_datos_registro(
    tipo: Any,
    referencia: Any,
    cantidad: Any,
    especificaciones: Any,
    insumos_terceros: Any = None,
    observaciones: Any = None,
    exigir_especificaciones: bool = True,
) -> DatosOrden:
    """Valida el formato de los datos de entrada de HU_CSFAB_01 (sin llamar a Materiales)."""
    faltantes = _faltantes(tipo, referencia, cantidad, especificaciones, exigir_especificaciones)
    if faltantes:
        raise DomainError(MSG_DATOS_OBLIGATORIOS, 422, {"faltantes": faltantes})

    valores_tipo = {t.value for t in TipoProducto}
    if not isinstance(tipo, str) or tipo not in valores_tipo:
        raise DomainError(MSG_TIPO_INVALIDO, 422)
    if not isinstance(referencia, str):
        raise DomainError(MSG_REFERENCIA_INVALIDA, 422)
    if not _es_entero_positivo(cantidad):
        raise DomainError(MSG_CANTIDAD_INVALIDA, 422)

    atributos = _validar_especificaciones(especificaciones) if exigir_especificaciones else (
        especificaciones if isinstance(especificaciones, dict) else {}
    )
    return DatosOrden(
        tipo_producto=TipoProducto(tipo),
        referencia_material=referencia.strip(),
        cantidad=cantidad,
        especificaciones=atributos,
        insumos_terceros=_validar_insumos(insumos_terceros),
        observaciones=_validar_observaciones(observaciones),
    )


def validar_formula_aprobada(estado: Any) -> None:
    """Regla 3.1: solo se fabrica con fórmula APROBADA."""
    if estado == EstadoFormula.APROBADA.value:
        return
    if estado == EstadoFormula.RECHAZADA_POR_INFRACCION.value:
        raise DomainError(MSG_FORMULA_RECHAZADA, 409)
    raise DomainError(MSG_FORMULA_NO_APROBADA, 409)
