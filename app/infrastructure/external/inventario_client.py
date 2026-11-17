import httpx

from app.core.config import settings


class InventarioClient:
    async def consultar_disponibilidad(self, referencia: str, formula: dict, cantidad: int) -> list[dict]:
        if settings.external_mode == "mock":
            return []
        async with httpx.AsyncClient(timeout=settings.external_timeout_seconds) as client:
            response = await client.get(
                f"{settings.inventario_base_url}/inventario/{referencia}",
                params={"cantidad": cantidad},
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("faltantes", [])

    async def descontar(
        self, fabricacion_id: str, referencia: str, formula: dict | None, cantidad: int
    ) -> None:
        if settings.external_mode == "mock":
            return
        async with httpx.AsyncClient(timeout=settings.external_timeout_seconds) as client:
            response = await client.post(
                f"{settings.inventario_base_url}/inventario",
                json={"fabricacion_id": fabricacion_id, "referencia_material": referencia,
                      "formula": formula, "cantidad": cantidad},
                headers={"Idempotency-Key": fabricacion_id},
            )
            response.raise_for_status()
