from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 409,
        extra: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.extra = extra or {}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        content: dict[str, Any] = {"detail": exc.message}
        content.update(exc.extra)
        return JSONResponse(status_code=exc.status_code, content=content)
