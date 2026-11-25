from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.fabricacion import Fabricacion
from app.infrastructure.database.models import FabricacionModel, SecuenciaOrdenModel


class FabricacionRepository:
    def __init__(self, db: Session):
        self.db = db

    def siguiente_id(self) -> str:
        """Reserva el siguiente consecutivo (único, atómico y sin reutilización)."""
        secuencia = SecuenciaOrdenModel()
        self.db.add(secuencia)
        self.db.flush()
        return f"ORD-{secuencia.numero:06d}"

    def save(self, entity: Fabricacion) -> Fabricacion:
        if not entity.id:
            entity.id = self.siguiente_id()
        model = self.db.get(FabricacionModel, entity.id)
        data = {
            "referencia_material": entity.referencia_material,
            "tipo_producto": entity.tipo_producto,
            "cantidad": entity.cantidad,
            "observaciones": entity.observaciones,
            "fabricante_id": entity.fabricante_id,
            "especificaciones_tecnicas": entity.especificaciones_tecnicas,
            "insumos_terceros": entity.insumos_terceros or [],
            "estado": entity.estado,
            "sincronizacion": entity.sincronizacion,
            "formula_version": entity.formula_version,
            "formula_snapshot": entity.formula_snapshot,
            "created_at": entity.created_at,
            "started_at": entity.started_at,
            "closed_at": entity.closed_at,
            "sync_attempts": entity.sync_attempts,
            "especificaciones": entity.especificaciones,
        }
        if model is None:
            model = FabricacionModel(id=entity.id, **data)
            self.db.add(model)
        else:
            for key, value in data.items():
                setattr(model, key, value)
        self.db.commit()
        self.db.refresh(model)
        return self.to_entity(model)

    def get(self, fabricacion_id: str) -> Fabricacion | None:
        model = self.db.get(FabricacionModel, fabricacion_id)
        return self.to_entity(model) if model else None

    def list(self, offset: int, limit: int, estado: str | None = None) -> list[Fabricacion]:
        stmt = select(FabricacionModel)
        if estado:
            stmt = stmt.where(FabricacionModel.estado == estado)
        stmt = stmt.order_by(FabricacionModel.created_at.desc()).offset(offset).limit(limit)
        return [self.to_entity(m) for m in self.db.scalars(stmt).all()]

    @staticmethod
    def to_entity(model: FabricacionModel) -> Fabricacion:
        entity = Fabricacion(
            referencia_material=model.referencia_material,
            tipo_producto=model.tipo_producto,
            cantidad=model.cantidad,
            observaciones=model.observaciones,
            fabricante_id=model.fabricante_id,
            especificaciones_tecnicas=model.especificaciones_tecnicas,
            id=model.id,
            especificaciones=model.especificaciones or {},
            insumos_terceros=model.insumos_terceros or [],
        )
        entity.estado = model.estado
        entity.sincronizacion = model.sincronizacion
        entity.formula_version = model.formula_version
        entity.formula_snapshot = model.formula_snapshot
        entity.created_at = model.created_at
        entity.started_at = model.started_at
        entity.closed_at = model.closed_at
        entity.sync_attempts = model.sync_attempts
        return entity
