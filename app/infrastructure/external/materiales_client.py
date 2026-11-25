from urllib.parse import quote

import httpx

from app.core.config import settings


class MaterialesClient:
    async def obtener_material(self, referencia: str) -> dict:
        if settings.external_mode == "mock":
            return {"id": referencia, "formula": {"estado": "APROBADA", "version": "1.0",
                    "items": [{"codigo": "ACERO", "descripcion": "Acero", "cantidad": 100, "unidad": "g"}]}}
        referencia_codificada = quote(referencia, safe="")
        async with httpx.AsyncClient(timeout=settings.external_timeout_seconds) as client:
            response = await client.get(f"{settings.materiales_base_url}/materiales/{referencia_codificada}")
            response.raise_for_status()
            return response.json()

    async def obtener_formula(self, referencia: str) -> dict:
        material = await self.obtener_material(referencia)
        return material.get("formula") or {}
