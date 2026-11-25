from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Acceso no autorizado",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401,
            detail="Acceso no autorizado",
        ) from exc

    role = payload.get("role")

    if role not in settings.allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="No tiene autorización para realizar esta operación",
        )

    return payload


def require_roles(*roles: str) -> Callable[..., dict[str, Any]]:
    def dependency(
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=403,
                detail="No tiene autorización para realizar esta operación",
            )
        return user

    return dependency