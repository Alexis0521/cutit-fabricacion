from sqlalchemy import String, Integer, DateTime, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from uuid import uuid4
from app.infrastructure.database.connection import Base
from app.domain.enums.estados import TipoProducto, EstadoFabricacion, EstadoSincronizacion


class FabricacionModel(Base):
    __tablename__ = "fabricaciones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    referencia_material: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo_producto: Mapped[TipoProducto] = mapped_column(SAEnum(TipoProducto), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    observaciones: Mapped[str | None] = mapped_column(String(250), nullable=True)
    estado: Mapped[EstadoFabricacion] = mapped_column(SAEnum(EstadoFabricacion), nullable=False)
    sincronizacion: Mapped[EstadoSincronizacion] = mapped_column(SAEnum(EstadoSincronizacion), nullable=False)
    formula_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    formula_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_attempts: Mapped[int] = mapped_column(Integer, default=0)
