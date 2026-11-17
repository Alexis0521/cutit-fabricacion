import httpx

from app.core.config import settings


class NotificacionesClient:
    async def notificar(self, evento: str, payload: dict) -> None:
        if settings.external_mode == "mock":
            return
        async with httpx.AsyncClient(timeout=settings.external_timeout_seconds) as client:
            await client.post(
                f"{settings.notificaciones_base_url}/eventos",
                json={"evento": evento, "payload": payload},
            )
