import math
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.application.schemas.fabricacion_schema import FabricacionCreate
from app.core.exceptions import DomainError
from app.domain.entities.fabricacion import Fabricacion
from app.infrastructure.external.inventario_client import InventarioClient
from app.infrastructure.external.materiales_client import MaterialesClient
from app.infrastructure.repositories.fabricacion_repository import FabricacionRepository


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

    async def validar(self, fabricacion_id: UUID) -> tuple[Fabricacion, list[dict]]:
        entity = self._get(fabricacion_id)
        faltantes = await self.inventario.consultar_disponibilidad(
            entity.referencia_material, {}, entity.cantidad
        )
        if faltantes:
            return entity, faltantes
        entity.validar()
        return self.repo.save(entity), []

    async def iniciar(self, fabricacion_id: UUID) -> Fabricacion:
        entity = self._get(fabricacion_id)
        formula = await self.materiales.obtener_formula(entity.referencia_material)
        entity.iniciar(formula)
        return self.repo.save(entity)

    async def formula(self, fabricacion_id: UUID) -> dict:
        entity = self._get(fabricacion_id)

        try:
            formula = await self.materiales.obtener_formula(
                entity.referencia_material
            )

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise DomainError(
                    "No existe una fórmula para esa referencia", 404
                ) from exc

            raise DomainError(
                "El módulo de Materiales no está disponible por el momento",
                503
            ) from exc

        except (httpx.RequestError, ValueError) as exc:
            raise DomainError(
                "El módulo de Materiales no está disponible por el momento",
                503
            ) from exc

        if not formula:
            raise DomainError(
                "No existe una fórmula para esa referencia", 404
            )

        if not isinstance(formula, dict):
            raise DomainError("La fórmula está incompleta", 409)

        items = formula.get("items")

        if not isinstance(items, list) or not items:
            raise DomainError("La fórmula está incompleta", 409)

        campos_texto = ["codigo", "descripcion", "unidad"]
        insumos = []

        for insumo in items:

            if not isinstance(insumo, dict):
                raise DomainError("La fórmula está incompleta", 409)

            for campo in campos_texto:
                valor = insumo.get(campo)

                if not isinstance(valor, str) or not valor.strip():
                    raise DomainError("La fórmula está incompleta", 409)

            cantidad = insumo.get("cantidad")

            if (
                isinstance(cantidad, bool)
                or not isinstance(cantidad, (int, float))
                or cantidad <= 0
                or (
                    isinstance(cantidad, float)
                    and not math.isfinite(cantidad)
                )
            ):
                raise DomainError("La fórmula está incompleta", 409)

            insumos.append({
                "codigoMaterial": insumo["codigo"],
                "descripcion": insumo["descripcion"],
                "cantidadPorUnidad": cantidad,
                "unidadMedida": insumo["unidad"]
            })

        return {
            "referenciaProducto": entity.referencia_material,
            "insumos": insumos
        }

    async def cerrar(self, fabricacion_id: UUID) -> Fabricacion:
        entity = self._get(fabricacion_id)
        entity.cerrar()
        self.repo.save(entity)
        try:
            await self.inventario.descontar(
                str(entity.id), entity.referencia_material, entity.formula_snapshot, entity.cantidad
            )
            entity.marcar_cerrada()
        except httpx.HTTPError:
            entity.marcar_no_sincronizada()
        return self.repo.save(entity)

    async def sincronizar(self, fabricacion_id: UUID) -> Fabricacion:
        entity = self._get(fabricacion_id)
        if entity.sincronizacion.value != "No Sincronizado":
            raise DomainError("La orden no requiere sincronización", 409)
        await self.inventario.descontar(
            str(entity.id), entity.referencia_material, entity.formula_snapshot, entity.cantidad
        )
        entity.marcar_cerrada()
        return self.repo.save(entity)

    def obtener(self, fabricacion_id: UUID) -> Fabricacion:
        return self._get(fabricacion_id)

    def listar(self, page: int, estado: str | None) -> list[Fabricacion]:
        return self.repo.list((page - 1) * 20, 20, estado)

    def _get(self, fabricacion_id: UUID) -> Fabricacion:
        entity = self.repo.get(fabricacion_id)
        if entity is None:
            raise DomainError("Fabricación no encontrada", 404)
        return entity
