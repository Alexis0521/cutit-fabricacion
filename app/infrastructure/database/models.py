from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums.estados import (
    EstadoFabricacion,
    EstadoSincronizacion,
    TipoProducto,
)
from app.infrastructure.database.connection import Base


class FabricacionModel(Base):
    __tablename__ = "fabricaciones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    referencia_material: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo_producto: Mapped[TipoProducto] = mapped_column(SAEnum(TipoProducto), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    observaciones: Mapped[str | None] = mapped_column(String(250), nullable=True)
    fabricante_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    especificaciones_tecnicas: Mapped[str | None] = mapped_column(Text, nullable=True)
    insumos_terceros: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON, nullable=True, default=list
    )
    estado: Mapped[EstadoFabricacion] = mapped_column(SAEnum(EstadoFabricacion), nullable=False)
    sincronizacion: Mapped[EstadoSincronizacion] = mapped_column(SAEnum(EstadoSincronizacion), nullable=False)
    formula_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    formula_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_attempts: Mapped[int] = mapped_column(Integer, default=0)
    especificaciones: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class SecuenciaOrdenModel(Base):
    """Contador atómico para generar los identificadores ORD-000123."""

    __tablename__ = "fabricaciones_secuencia"

    numero: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
