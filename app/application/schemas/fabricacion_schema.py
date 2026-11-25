from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums.estados import (
    EstadoFabricacion,
    EstadoSincronizacion,
    TipoProducto,
)


class FabricacionCreate(BaseModel):
    """Entrada de POST /fabricaciones (HU_CSFAB_01).

    Los campos son permisivos a propósito: las reglas de negocio y sus mensajes
    exactos (422/409) se validan en `app.domain.validators`, no en Pydantic.
    """

    model_config = ConfigDict(populate_by_name=True)

    tipo_producto: Any = Field(default=None, alias="tipoProducto")
    referencia_material: Any = Field(default=None, alias="referenciaProducto")
    cantidad: Any = None
    especificaciones: Any = None
    insumos_terceros: Any = Field(default=None, alias="insumosTerceros")
    observaciones: Any = None


class FabricacionRegistrada(BaseModel):
    mensaje: str
    id: str
    estado: EstadoFabricacion


class FabricacionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cantidad: int | None = Field(default=None, gt=0, strict=True)
    especificaciones: dict[str, Any] | None = None
    especificaciones_tecnicas: str | None = Field(default=None, min_length=1)
    insumos_terceros: list[dict[str, Any]] | None = None
    observaciones: str | None = Field(default=None, max_length=250)

    @field_validator("especificaciones")
    @classmethod
    def especificaciones_dict_no_vacias(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if value is not None and not any(
            item is not None and (not isinstance(item, str) or item.strip())
            for item in value.values()
        ):
            raise ValueError("Las especificaciones técnicas son obligatorias")
        return value

    @field_validator("especificaciones_tecnicas")
    @classmethod
    def especificaciones_texto_no_vacias(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Las especificaciones técnicas son obligatorias")
        return value

    @model_validator(mode="after")
    def validar_cantidad_y_especificaciones_presentes(self) -> "FabricacionUpdate":
        for field in ("cantidad", "especificaciones", "especificaciones_tecnicas"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} no puede ser nulo")
        if not self.model_fields_set:
            raise ValueError("Debe enviar al menos un campo modificable")
        return self


class FabricacionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    referencia_material: str
    tipo_producto: TipoProducto
    cantidad: int
    observaciones: str | None
    estado: EstadoFabricacion
    sincronizacion: EstadoSincronizacion
    formula_version: str | None
    created_at: datetime
    started_at: datetime | None
    closed_at: datetime | None
    sync_attempts: int
    especificaciones: dict[str, Any]
    insumos_terceros: list[dict[str, Any]]


class InicioResult(FabricacionRead):
    mensaje: str


class ModificacionResult(BaseModel):
    mensaje: str
    id: str
    estado: EstadoFabricacion


class Faltante(BaseModel):
    codigoMaterial: str
    requerido: float
    disponible: float
    faltante: float


class ValidacionResult(BaseModel):
    mensaje: str
    id: str
    estado: EstadoFabricacion


class ValidacionError(BaseModel):
    detail: str
    faltantes: list[Faltante] | None = None


class NotificacionCreate(BaseModel):
    referencia_material: str
    tipo_producto: TipoProducto
    cantidad: int = Field(gt=0)
    observaciones: str | None = Field(default="Reposición por alerta de stock", max_length=250)
    especificaciones: dict[str, Any] = Field(default_factory=dict)

class InsumoFormula(BaseModel):
    codigoMaterial: str
    descripcion: str
    cantidadPorUnidad: int | float
    unidadMedida: str


class FormulaRead(BaseModel):
    referenciaProducto: str
    insumos: list[InsumoFormula]
