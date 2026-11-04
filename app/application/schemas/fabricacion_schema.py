from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.domain.enums.estados import TipoProducto, EstadoFabricacion, EstadoSincronizacion


class FabricacionCreate(BaseModel):
    referencia_material: str = Field(min_length=1, max_length=100)
    tipo_producto: TipoProducto
    cantidad: int = Field(gt=0)
    observaciones: str | None = Field(default=None, max_length=250)


class FabricacionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
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


class Faltante(BaseModel):
    codigo: str
    descripcion: str
    requerido: float
    disponible: float
    diferencia: float


class ValidacionResult(BaseModel):
    disponible: bool
    faltantes: list[Faltante]


class NotificacionCreate(BaseModel):
    referencia_material: str
    tipo_producto: TipoProducto
    cantidad: int = Field(gt=0)
    observaciones: str | None = Field(default="Reposición por alerta de stock", max_length=250)
