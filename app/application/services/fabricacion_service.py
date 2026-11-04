from uuid import UUID
from sqlalchemy.orm import Session
from app.core.exceptions import DomainError
from app.domain.entities.fabricacion import Fabricacion
from app.application.schemas.fabricacion_schema import FabricacionCreate
from app.infrastructure.repositories.fabricacion_repository import FabricacionRepository
from app.infrastructure.external.materiales_client import MaterialesClient
from app.infrastructure.external.inventario_client import InventarioClient


class FabricacionService:
    def __init__(self, db: Session):
        self.repo = FabricacionRepository(db)
        self.materiales = MaterialesClient()
        self.inventario = InventarioClient()

    async def registrar(self, data: FabricacionCreate) -> Fabricacion:
        material = await self.materiales.obtener_material(data.referencia_material)
        formula = material.get("formula") or {}
        if formula.get("estado") != "APROBADA":
            raise DomainError("La fórmula del material no está aprobada", 409)
        entity = Fabricacion(**data.model_dump())
        return self.repo.save(entity)

    async def validar(self, fabricacion_id: UUID):
        entity = self._get(fabricacion_id)
        faltantes = await self.inventario.consultar_disponibilidad(
            entity.referencia_material, {}, entity.cantidad
        )
        if faltantes:
            return entity, faltantes
        entity.validar()
        return self.repo.save(entity), []

    async def iniciar(self, fabricacion_id: UUID):
        entity = self._get(fabricacion_id)
        formula = await self.materiales.obtener_formula(entity.referencia_material)
        entity.iniciar(formula)
        return self.repo.save(entity)

    async def formula(self, fabricacion_id: UUID):
        entity = self._get(fabricacion_id)
        if entity.estado.value not in {"En Proceso", "Cerrada"}:
            raise DomainError("La fórmula solo está disponible durante o después de la fabricación", 409)
        formula = entity.formula_snapshot
        if not formula or not formula.get("items"):
            raise DomainError("La fórmula está incompleta", 409)
        return formula

    async def cerrar(self, fabricacion_id: UUID):
        entity = self._get(fabricacion_id)
        entity.cerrar()
        self.repo.save(entity)
        try:
            await self.inventario.descontar(
                str(entity.id), entity.referencia_material, entity.formula_snapshot, entity.cantidad
            )
            entity.marcar_cerrada()
        except Exception:
            entity.marcar_no_sincronizada()
        return self.repo.save(entity)

    async def sincronizar(self, fabricacion_id: UUID):
        entity = self._get(fabricacion_id)
        if entity.sincronizacion.value != "No Sincronizado":
            raise DomainError("La orden no requiere sincronización", 409)
        await self.inventario.descontar(
            str(entity.id), entity.referencia_material, entity.formula_snapshot, entity.cantidad
        )
        entity.marcar_cerrada()
        return self.repo.save(entity)

    def obtener(self, fabricacion_id: UUID):
        return self._get(fabricacion_id)

    def listar(self, page: int, estado: str | None):
        return self.repo.list((page - 1) * 20, 20, estado)

    def _get(self, fabricacion_id: UUID):
        entity = self.repo.get(fabricacion_id)
        if entity is None:
            raise DomainError("Fabricación no encontrada", 404)
        return entity
