import math
from decimal import Decimal
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.application.schemas.fabricacion_schema import (
    FabricacionCreate,
    FabricacionUpdate,
)
from app.core.exceptions import DomainError
from app.domain.entities.fabricacion import Fabricacion
from app.domain.enums.estados import EstadoFabricacion
from app.infrastructure.external.inventario_client import InventarioClient
from app.infrastructure.external.materiales_client import MaterialesClient
from app.infrastructure.repositories.fabricacion_repository import FabricacionRepository


class FabricacionService:
    def __init__(self, db: Session):
        self.repo = FabricacionRepository(db)
        self.materiales = MaterialesClient()
        self.inventario = InventarioClient()

    async def registrar(
        self,
        data: FabricacionCreate,
        fabricante_id: str | None = None,
    ) -> Fabricacion:
        material = await self.materiales.obtener_material(data.referencia_material)
        formula = material.get("formula") or {}
        if formula.get("estado") != "APROBADA":
            raise DomainError("La fórmula del material no está aprobada", 409)
        entity = Fabricacion(
            **data.model_dump(),
            fabricante_id=fabricante_id,
        )
        return self.repo.save(entity)

    async def validar(
        self, fabricacion_id: UUID
        ) -> tuple[Fabricacion, list[dict]]:

        entity = self.repo.get(fabricacion_id)

        if entity is None:
            raise DomainError("No se encontró la orden", 404)

        if entity.estado != EstadoFabricacion.REGISTRADA:
            raise DomainError(
                "Solo se pueden validar órdenes en estado Registrada",
                409,
            )

        formula = await self.formula(fabricacion_id)

        faltantes = []
        requerimientos: dict[tuple[str, str], Decimal] = {}

        for insumo in formula["insumos"]:
            codigo = insumo["codigoMaterial"]
            unidad = insumo["unidadMedida"]

            requerido = (
                Decimal(str(insumo["cantidadPorUnidad"]))
                * entity.cantidad
            )

            clave = (codigo, unidad)

            total = requerimientos.get(clave, Decimal(0)) + requerido

            if not math.isfinite(float(total)):
                raise DomainError(
                    "La cantidad requerida de material excede el límite permitido",
                    409,
                )

            requerimientos[clave] = total

        for (codigo, unidad), requerido in requerimientos.items():

            try:
                stock = await self.inventario.consultar_disponibilidad(
                    codigo
                )

                disponible = stock.get("disponible")

                if (
                    isinstance(disponible, bool)
                    or not isinstance(disponible, (int, float))
                    or disponible < 0
                    or (
                        isinstance(disponible, float)
                        and not math.isfinite(disponible)
                    )
                    or stock.get("unidadMedida") != unidad
                ):
                    raise ValueError("Existencias o unidad inválidas")

            except (httpx.HTTPError, ValueError, AttributeError) as exc:
                raise DomainError(
                    "El módulo de Inventario no está disponible por el momento",
                    503,
                ) from exc

            disponible_decimal = Decimal(str(disponible))

            if disponible_decimal < requerido:
                faltantes.append({
                    "codigoMaterial": codigo,
                    "requerido": float(requerido),
                    "disponible": float(disponible_decimal),
                    "faltante": float(requerido - disponible_decimal),
                })

        if faltantes:
            return entity, faltantes

        entity.validar()

        return self.repo.save(entity), []

    def modificar(
        self,
        fabricacion_id: UUID,
        data: FabricacionUpdate,
    ) -> Fabricacion:
        entity = self._get(fabricacion_id)

        if entity.estado not in (
            EstadoFabricacion.REGISTRADA,
            EstadoFabricacion.VALIDADA,
        ):
            raise DomainError(
                "Solo se pueden modificar órdenes Registradas o Validadas",
                409,
            )

        cambios = data.model_dump(exclude_unset=True)
        if not cambios:
            raise DomainError("Debe enviar al menos un campo modificable", 422)

        requiere_revalidacion = any(
            campo in cambios
            and getattr(entity, campo) != cambios[campo]
            for campo in (
                "cantidad",
                "especificaciones_tecnicas",
                "insumos_terceros",
            )
        )

        for campo, valor in cambios.items():
            setattr(entity, campo, valor)

        if (
            entity.estado == EstadoFabricacion.VALIDADA
            and requiere_revalidacion
        ):
            entity.estado = EstadoFabricacion.REGISTRADA

        return self.repo.save(entity)

    async def iniciar(
        self, fabricacion_id: UUID, usuario: dict[str, object]
    ) -> Fabricacion:
        entity = self._get(fabricacion_id)

        rol = usuario.get("role")
        if rol == "FABRICANTE":
            usuario_id = usuario.get("sub")
            if (
                not isinstance(usuario_id, str)
                or usuario_id != entity.fabricante_id
            ):
                raise DomainError(
                    "Solo el fabricante asignado puede iniciar esta orden",
                    403,
                )
        elif rol != "GERENTE_FABRICACION":
            raise DomainError(
                "No tiene autorización para iniciar esta orden",
                403,
            )

        if entity.estado != EstadoFabricacion.VALIDADA:
            raise DomainError(
                "Solo se pueden iniciar órdenes Validadas",
                409,
            )

        try:
            formula = await self.materiales.obtener_formula(
                entity.referencia_material
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise DomainError(
                    "No existe una fórmula para esa referencia",
                    404,
                ) from exc

            raise DomainError(
                "El módulo de Materiales no está disponible por el momento",
                503,
            ) from exc

        except httpx.HTTPError as exc:
            raise DomainError(
                "El módulo de Materiales no está disponible por el momento",
                503,
            ) from exc

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

        except Exception as exc:
            raise DomainError(
                "El módulo de Materiales no está disponible por el momento",
                503,
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
